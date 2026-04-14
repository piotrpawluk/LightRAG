import os
import logging
import asyncio
import time
from typing import Any, final, Union
from dataclasses import dataclass
import pipmaster as pm
import configparser
from contextlib import asynccontextmanager
import threading

import numpy as np

if not pm.is_installed("redis"):
    pm.install("redis")

# aioredis is a depricated library, replaced with redis
from redis.asyncio import Redis, ConnectionPool  # type: ignore
from redis.exceptions import RedisError, ConnectionError, TimeoutError, ResponseError  # type: ignore
from redis.commands.search.field import TagField, VectorField, TextField, NumericField  # type: ignore
from redis.commands.search.index_definition import IndexDefinition, IndexType  # type: ignore
from redis.commands.search.query import Query  # type: ignore
from lightrag.utils import logger, get_pinyin_sort_key, compute_mdhash_id, _cooperative_yield

from lightrag.base import (
    BaseKVStorage,
    BaseVectorStorage,
    BaseGraphStorage,
    DocStatusStorage,
    DocStatus,
    DocProcessingStatus,
)
from lightrag.types import KnowledgeGraph, KnowledgeGraphNode, KnowledgeGraphEdge
from ..kg.shared_storage import get_data_init_lock
import json

# Import tenacity for retry logic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

config = configparser.ConfigParser()
config.read("config.ini", "utf-8")

# Constants for Redis connection pool with environment variable support
MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "200"))
SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "30.0"))
SOCKET_CONNECT_TIMEOUT = float(os.getenv("REDIS_CONNECT_TIMEOUT", "10.0"))
RETRY_ATTEMPTS = int(os.getenv("REDIS_RETRY_ATTEMPTS", "3"))

# Constants for Redis Vector Storage
REDIS_VECTOR_DIM_KEY = "redis_vdb_dim"
REDIS_HNSW_M = int(os.getenv("REDIS_HNSW_M", "16"))
REDIS_HNSW_EF_CONSTRUCTION = int(os.getenv("REDIS_HNSW_EF_CONSTRUCTION", "256"))

# Key prefix for multi-instance isolation (allows multiple LightRAG instances to share the same Redis)
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "").strip()

# Edge fields that should be converted to numeric types when retrieved from Redis
# Redis stores all values as strings, so we need to convert these back to their proper types
NUMERIC_EDGE_FIELDS = {"weight"}

# Tenacity retry decorator for Redis operations
redis_retry = retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=(
        retry_if_exception_type(ConnectionError)
        | retry_if_exception_type(TimeoutError)
        | retry_if_exception_type(RedisError)
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


class RedisConnectionManager:
    """Shared Redis connection pool manager to avoid creating multiple pools for the same Redis URI"""

    _pools = {}
    _pool_refs = {}  # Track reference count for each pool
    _lock = threading.Lock()

    @classmethod
    def get_pool(cls, redis_url: str) -> ConnectionPool:
        """Get or create a connection pool for the given Redis URL"""
        with cls._lock:
            if redis_url not in cls._pools:
                cls._pools[redis_url] = ConnectionPool.from_url(
                    redis_url,
                    max_connections=MAX_CONNECTIONS,
                    decode_responses=True,
                    socket_timeout=SOCKET_TIMEOUT,
                    socket_connect_timeout=SOCKET_CONNECT_TIMEOUT,
                )
                cls._pool_refs[redis_url] = 0
                logger.info(f"Created shared Redis connection pool for {redis_url}")

            # Increment reference count
            cls._pool_refs[redis_url] += 1
            logger.debug(
                f"Redis pool {redis_url} reference count: {cls._pool_refs[redis_url]}"
            )

        return cls._pools[redis_url]

    @classmethod
    def release_pool(cls, redis_url: str):
        """Release a reference to the connection pool"""
        with cls._lock:
            if redis_url in cls._pool_refs:
                cls._pool_refs[redis_url] -= 1
                logger.debug(
                    f"Redis pool {redis_url} reference count: {cls._pool_refs[redis_url]}"
                )

                # If no more references, close the pool
                if cls._pool_refs[redis_url] <= 0:
                    try:
                        cls._pools[redis_url].disconnect()
                        logger.info(
                            f"Closed Redis connection pool for {redis_url} (no more references)"
                        )
                    except Exception as e:
                        logger.error(f"Error closing Redis pool for {redis_url}: {e}")
                    finally:
                        del cls._pools[redis_url]
                        del cls._pool_refs[redis_url]

    @classmethod
    def close_all_pools(cls):
        """Close all connection pools (for cleanup)"""
        with cls._lock:
            for url, pool in cls._pools.items():
                try:
                    pool.disconnect()
                    logger.info(f"Closed Redis connection pool for {url}")
                except Exception as e:
                    logger.error(f"Error closing Redis pool for {url}: {e}")
            cls._pools.clear()
            cls._pool_refs.clear()


@final
@dataclass
class RedisKVStorage(BaseKVStorage):
    def __post_init__(self):
        # Check for REDIS_WORKSPACE environment variable first (higher priority)
        # This allows administrators to force a specific workspace for all Redis storage instances
        redis_workspace = os.environ.get("REDIS_WORKSPACE")
        if redis_workspace and redis_workspace.strip():
            # Use environment variable value, overriding the passed workspace parameter
            effective_workspace = redis_workspace.strip()
            logger.info(
                f"Using REDIS_WORKSPACE environment variable: '{effective_workspace}' (overriding '{self.workspace}/{self.namespace}')"
            )
        else:
            # Use the workspace parameter passed during initialization
            effective_workspace = self.workspace
            if effective_workspace:
                logger.debug(
                    f"Using passed workspace parameter: '{effective_workspace}'"
                )

        # Build final_namespace with workspace prefix for data isolation
        # Keep original namespace unchanged for type detection logic
        if effective_workspace:
            base_namespace = f"{effective_workspace}_{self.namespace}"
        else:
            base_namespace = self.namespace
            self.workspace = ""

        # Apply global key prefix for multi-instance isolation
        if REDIS_KEY_PREFIX:
            self.final_namespace = f"{REDIS_KEY_PREFIX}:{base_namespace}"
            logger.debug(
                f"Final namespace with key prefix: '{self.final_namespace}'"
            )
        else:
            self.final_namespace = base_namespace
            logger.debug(f"Final namespace: '{self.final_namespace}'")

        self._redis_url = os.environ.get(
            "REDIS_URI", config.get("redis", "uri", fallback="redis://localhost:6379")
        )
        self._pool = None
        self._redis = None
        self._initialized = False

        try:
            # Use shared connection pool
            self._pool = RedisConnectionManager.get_pool(self._redis_url)
            self._redis = Redis(connection_pool=self._pool)
            logger.info(
                f"[{self.workspace}] Initialized Redis KV storage for {self.namespace} using shared connection pool"
            )
        except Exception as e:
            # Clean up on initialization failure
            if self._redis_url:
                RedisConnectionManager.release_pool(self._redis_url)
            logger.error(
                f"[{self.workspace}] Failed to initialize Redis KV storage: {e}"
            )
            raise

    async def initialize(self):
        """Initialize Redis connection and migrate legacy cache structure if needed"""
        async with get_data_init_lock():
            if self._initialized:
                return

            # Test connection
            try:
                async with self._get_redis_connection() as redis:
                    await redis.ping()
                    logger.info(
                        f"[{self.workspace}] Connected to Redis for namespace {self.namespace}"
                    )
                    self._initialized = True
            except Exception as e:
                logger.error(f"[{self.workspace}] Failed to connect to Redis: {e}")
                # Clean up on connection failure
                await self.close()
                raise

            # Migrate legacy cache structure if this is a cache namespace
            if self.namespace.endswith("_cache"):
                try:
                    await self._migrate_legacy_cache_structure()
                except Exception as e:
                    logger.error(
                        f"[{self.workspace}] Failed to migrate legacy cache structure: {e}"
                    )
                    # Don't fail initialization for migration errors, just log them

    @asynccontextmanager
    async def _get_redis_connection(self):
        """Safe context manager for Redis operations."""
        if not self._redis:
            raise ConnectionError("Redis connection not initialized")

        try:
            # Use the existing Redis instance with shared pool
            yield self._redis
        except ConnectionError as e:
            logger.error(
                f"[{self.workspace}] Redis connection error in {self.namespace}: {e}"
            )
            raise
        except RedisError as e:
            logger.error(
                f"[{self.workspace}] Redis operation error in {self.namespace}: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Unexpected error in Redis operation for {self.namespace}: {e}"
            )
            raise

    async def close(self):
        """Close the Redis connection and release pool reference to prevent resource leaks."""
        if hasattr(self, "_redis") and self._redis:
            try:
                await self._redis.close()
                logger.debug(
                    f"[{self.workspace}] Closed Redis connection for {self.namespace}"
                )
            except Exception as e:
                logger.error(f"[{self.workspace}] Error closing Redis connection: {e}")
            finally:
                self._redis = None

        # Release the pool reference (will auto-close pool if no more references)
        if hasattr(self, "_redis_url") and self._redis_url:
            RedisConnectionManager.release_pool(self._redis_url)
            self._pool = None
            logger.debug(
                f"[{self.workspace}] Released Redis connection pool reference for {self.namespace}"
            )

    async def __aenter__(self):
        """Support for async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure Redis resources are cleaned up when exiting context."""
        await self.close()

    @redis_retry
    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        async with self._get_redis_connection() as redis:
            try:
                data = await redis.get(f"{self.final_namespace}:{id}")
                if data:
                    result = json.loads(data)
                    # Ensure time fields are present, provide default values for old data
                    result.setdefault("create_time", 0)
                    result.setdefault("update_time", 0)
                    return result
                return None
            except json.JSONDecodeError as e:
                logger.error(f"[{self.workspace}] JSON decode error for id {id}: {e}")
                raise

    @redis_retry
    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        async with self._get_redis_connection() as redis:
            try:
                pipe = redis.pipeline()
                for id in ids:
                    pipe.get(f"{self.final_namespace}:{id}")
                results = await pipe.execute()

                processed_results = []
                for result in results:
                    if result:
                        data = json.loads(result)
                        # Ensure time fields are present for all documents
                        data.setdefault("create_time", 0)
                        data.setdefault("update_time", 0)
                        processed_results.append(data)
                    else:
                        processed_results.append(None)

                return processed_results
            except json.JSONDecodeError as e:
                logger.error(f"[{self.workspace}] JSON decode error in batch get: {e}")
                raise

    async def filter_keys(self, keys: set[str]) -> set[str]:
        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            keys_list = list(keys)  # Convert set to list for indexing
            for key in keys_list:
                pipe.exists(f"{self.final_namespace}:{key}")
            results = await pipe.execute()

            existing_ids = {keys_list[i] for i, exists in enumerate(results) if exists}
            return set(keys) - existing_ids

    @redis_retry
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        if not data:
            return

        import time

        current_time = int(time.time())  # Get current Unix timestamp

        async with self._get_redis_connection() as redis:
            try:
                # Check which keys already exist to determine create vs update
                pipe = redis.pipeline()
                for i, k in enumerate(data.keys(), start=1):
                    pipe.exists(f"{self.final_namespace}:{k}")
                    await _cooperative_yield(i)
                exists_results = await pipe.execute()

                # Add timestamps to data
                for i, (k, v) in enumerate(data.items(), start=1):
                    # For text_chunks namespace, ensure llm_cache_list field exists
                    if self.namespace.endswith("text_chunks"):
                        if "llm_cache_list" not in v:
                            v["llm_cache_list"] = []

                    # Add timestamps based on whether key exists
                    if exists_results[i - 1]:  # Key exists, only update update_time
                        v["update_time"] = current_time
                    else:  # New key, set both create_time and update_time
                        v["create_time"] = current_time
                        v["update_time"] = current_time

                    v["_id"] = k
                    await _cooperative_yield(i)

                # Store the data
                pipe = redis.pipeline()
                for i, (k, v) in enumerate(data.items(), start=1):
                    pipe.set(f"{self.final_namespace}:{k}", json.dumps(v))
                    await _cooperative_yield(i)
                await pipe.execute()

            except json.JSONDecodeError as e:
                logger.error(f"[{self.workspace}] JSON decode error during upsert: {e}")
                raise

    async def index_done_callback(self) -> None:
        # Redis handles persistence automatically
        pass

    async def is_empty(self) -> bool:
        """Check if the storage is empty for the current workspace and namespace

        Returns:
            bool: True if storage is empty, False otherwise
        """
        pattern = f"{self.final_namespace}:*"
        try:
            async with self._get_redis_connection() as redis:
                # Use scan to check if any keys exist
                async for key in redis.scan_iter(match=pattern, count=1):
                    return False  # Found at least one key
                return True  # No keys found
        except Exception as e:
            logger.error(f"[{self.workspace}] Error checking if storage is empty: {e}")
            return True

    async def delete(self, ids: list[str]) -> None:
        """Delete specific records from storage by their IDs"""
        if not ids:
            return

        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            for id in ids:
                pipe.delete(f"{self.final_namespace}:{id}")

            results = await pipe.execute()
            deleted_count = sum(results)
            logger.info(
                f"[{self.workspace}] Deleted {deleted_count} of {len(ids)} entries from {self.namespace}"
            )

    async def drop(self) -> dict[str, str]:
        """Drop the storage by removing all keys under the current namespace.

        Returns:
            dict[str, str]: Status of the operation with keys 'status' and 'message'
        """
        async with self._get_redis_connection() as redis:
            try:
                # Use SCAN to find all keys with the namespace prefix
                pattern = f"{self.final_namespace}:*"
                cursor = 0
                deleted_count = 0

                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=1000)
                    if keys:
                        # Delete keys in batches
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.delete(key)
                        results = await pipe.execute()
                        deleted_count += sum(results)

                    if cursor == 0:
                        break

                logger.info(
                    f"[{self.workspace}] Dropped {deleted_count} keys from {self.namespace}"
                )
                return {
                    "status": "success",
                    "message": f"{deleted_count} keys dropped",
                }

            except Exception as e:
                logger.error(
                    f"[{self.workspace}] Error dropping keys from {self.namespace}: {e}"
                )
                return {"status": "error", "message": str(e)}

    async def _migrate_legacy_cache_structure(self):
        """Migrate legacy nested cache structure to flattened structure for Redis

        Redis already stores data in a flattened way, but we need to check for
        legacy keys that might contain nested JSON structures and migrate them.

        Early exit if any flattened key is found (indicating migration already done).
        """
        from lightrag.utils import generate_cache_key

        async with self._get_redis_connection() as redis:
            # Get all keys for this namespace
            keys = await redis.keys(f"{self.final_namespace}:*")

            if not keys:
                return

            # Check if we have any flattened keys already - if so, skip migration
            has_flattened_keys = False
            keys_to_migrate = []

            for key in keys:
                # Extract the ID part (after namespace:)
                key_id = key.split(":", 1)[1]

                # Check if already in flattened format (contains exactly 2 colons for mode:cache_type:hash)
                if ":" in key_id and len(key_id.split(":")) == 3:
                    has_flattened_keys = True
                    break  # Early exit - migration already done

                # Get the data to check if it's a legacy nested structure
                data = await redis.get(key)
                if data:
                    try:
                        parsed_data = json.loads(data)
                        # Check if this looks like a legacy cache mode with nested structure
                        if isinstance(parsed_data, dict) and all(
                            isinstance(v, dict) and "return" in v
                            for v in parsed_data.values()
                        ):
                            keys_to_migrate.append((key, key_id, parsed_data))
                    except json.JSONDecodeError:
                        continue

            # If we found any flattened keys, assume migration is already done
            if has_flattened_keys:
                logger.debug(
                    f"[{self.workspace}] Found flattened cache keys in {self.namespace}, skipping migration"
                )
                return

            if not keys_to_migrate:
                return

            # Perform migration
            pipe = redis.pipeline()
            migration_count = 0

            for old_key, mode, nested_data in keys_to_migrate:
                # Delete the old key
                pipe.delete(old_key)

                # Create new flattened keys
                for cache_hash, cache_entry in nested_data.items():
                    cache_type = cache_entry.get("cache_type", "extract")
                    flattened_key = generate_cache_key(mode, cache_type, cache_hash)
                    full_key = f"{self.final_namespace}:{flattened_key}"
                    pipe.set(full_key, json.dumps(cache_entry))
                    migration_count += 1

            await pipe.execute()

            if migration_count > 0:
                logger.info(
                    f"[{self.workspace}] Migrated {migration_count} legacy cache entries to flattened structure in Redis"
                )


@final
@dataclass
class RedisDocStatusStorage(DocStatusStorage):
    """Redis implementation of document status storage"""

    def __post_init__(self):
        # Check for REDIS_WORKSPACE environment variable first (higher priority)
        # This allows administrators to force a specific workspace for all Redis storage instances
        redis_workspace = os.environ.get("REDIS_WORKSPACE")
        if redis_workspace and redis_workspace.strip():
            # Use environment variable value, overriding the passed workspace parameter
            effective_workspace = redis_workspace.strip()
            logger.info(
                f"Using REDIS_WORKSPACE environment variable: '{effective_workspace}' (overriding '{self.workspace}/{self.namespace}')"
            )
        else:
            # Use the workspace parameter passed during initialization
            effective_workspace = self.workspace
            if effective_workspace:
                logger.debug(
                    f"Using passed workspace parameter: '{effective_workspace}'"
                )

        # Build final_namespace with workspace prefix for data isolation
        # Keep original namespace unchanged for type detection logic
        if effective_workspace:
            base_namespace = f"{effective_workspace}_{self.namespace}"
        else:
            base_namespace = self.namespace
            self.workspace = "_"

        # Apply global key prefix for multi-instance isolation
        if REDIS_KEY_PREFIX:
            self.final_namespace = f"{REDIS_KEY_PREFIX}:{base_namespace}"
            logger.debug(
                f"[{self.workspace}] Final namespace with key prefix: '{self.final_namespace}'"
            )
        else:
            self.final_namespace = base_namespace
            logger.debug(
                f"[{self.workspace}] Final namespace: '{self.final_namespace}'"
            )

        self._redis_url = os.environ.get(
            "REDIS_URI", config.get("redis", "uri", fallback="redis://localhost:6379")
        )
        self._pool = None
        self._redis = None
        self._initialized = False

        try:
            # Use shared connection pool
            self._pool = RedisConnectionManager.get_pool(self._redis_url)
            self._redis = Redis(connection_pool=self._pool)
            logger.info(
                f"[{self.workspace}] Initialized Redis doc status storage for {self.namespace} using shared connection pool"
            )
        except Exception as e:
            # Clean up on initialization failure
            if self._redis_url:
                RedisConnectionManager.release_pool(self._redis_url)
            logger.error(
                f"[{self.workspace}] Failed to initialize Redis doc status storage: {e}"
            )
            raise

    async def initialize(self):
        """Initialize Redis connection"""
        async with get_data_init_lock():
            if self._initialized:
                return

            try:
                async with self._get_redis_connection() as redis:
                    await redis.ping()
                    logger.info(
                        f"[{self.workspace}] Connected to Redis for doc status namespace {self.namespace}"
                    )
                    self._initialized = True
            except Exception as e:
                logger.error(
                    f"[{self.workspace}] Failed to connect to Redis for doc status: {e}"
                )
                # Clean up on connection failure
                await self.close()
                raise

    @asynccontextmanager
    async def _get_redis_connection(self):
        """Safe context manager for Redis operations."""
        if not self._redis:
            raise ConnectionError("Redis connection not initialized")

        try:
            # Use the existing Redis instance with shared pool
            yield self._redis
        except ConnectionError as e:
            logger.error(
                f"[{self.workspace}] Redis connection error in doc status {self.namespace}: {e}"
            )
            raise
        except RedisError as e:
            logger.error(
                f"[{self.workspace}] Redis operation error in doc status {self.namespace}: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Unexpected error in Redis doc status operation for {self.namespace}: {e}"
            )
            raise

    async def close(self):
        """Close the Redis connection and release pool reference to prevent resource leaks."""
        if hasattr(self, "_redis") and self._redis:
            try:
                await self._redis.close()
                logger.debug(
                    f"[{self.workspace}] Closed Redis connection for doc status {self.namespace}"
                )
            except Exception as e:
                logger.error(f"[{self.workspace}] Error closing Redis connection: {e}")
            finally:
                self._redis = None

        # Release the pool reference (will auto-close pool if no more references)
        if hasattr(self, "_redis_url") and self._redis_url:
            RedisConnectionManager.release_pool(self._redis_url)
            self._pool = None
            logger.debug(
                f"[{self.workspace}] Released Redis connection pool reference for doc status {self.namespace}"
            )

    async def __aenter__(self):
        """Support for async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure Redis resources are cleaned up when exiting context."""
        await self.close()

    async def filter_keys(self, keys: set[str]) -> set[str]:
        """Return keys that should be processed (not in storage or not successfully processed)"""
        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            keys_list = list(keys)
            for key in keys_list:
                pipe.exists(f"{self.final_namespace}:{key}")
            results = await pipe.execute()

            existing_ids = {keys_list[i] for i, exists in enumerate(results) if exists}
            return set(keys) - existing_ids

    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        ordered_results: list[dict[str, Any] | None] = []
        async with self._get_redis_connection() as redis:
            try:
                pipe = redis.pipeline()
                for id in ids:
                    pipe.get(f"{self.final_namespace}:{id}")
                results = await pipe.execute()

                for result_data in results:
                    if result_data:
                        try:
                            ordered_results.append(json.loads(result_data))
                        except json.JSONDecodeError as e:
                            logger.error(
                                f"[{self.workspace}] JSON decode error in get_by_ids: {e}"
                            )
                            raise
                    else:
                        ordered_results.append(None)
            except Exception as e:
                logger.error(f"[{self.workspace}] Error in get_by_ids: {e}")
                raise
        return ordered_results

    async def get_status_counts(self) -> dict[str, int]:
        """Get counts of documents in each status"""
        counts = {status.value: 0 for status in DocStatus}
        async with self._get_redis_connection() as redis:
            try:
                # Use SCAN to iterate through all keys in the namespace
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(
                        cursor, match=f"{self.final_namespace}:*", count=1000
                    )
                    if keys:
                        # Get all values in batch
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.get(key)
                        values = await pipe.execute()

                        # Count statuses
                        for value in values:
                            if value:
                                try:
                                    doc_data = json.loads(value)
                                    status = doc_data.get("status")
                                    if status in counts:
                                        counts[status] += 1
                                except json.JSONDecodeError:
                                    continue

                    if cursor == 0:
                        break
            except Exception as e:
                logger.error(f"[{self.workspace}] Error getting status counts: {e}")

        return counts

    async def get_docs_by_status(
        self, status: DocStatus
    ) -> dict[str, DocProcessingStatus]:
        """Get all documents with a specific status"""
        return await self.get_docs_by_statuses([status])

    async def get_docs_by_statuses(
        self, statuses: list[DocStatus]
    ) -> dict[str, DocProcessingStatus]:
        """Get all documents matching any of the given statuses in a single SCAN pass.

        Redis has no server-side multi-value filter, so documents must be fetched
        and filtered in Python.  This override performs a single SCAN + pipeline
        GET over the keyspace, filtering against a set of status values.  The
        previous pattern of N separate get_docs_by_status() calls would do N full
        SCANs (one per status), so this reduces keyspace traversal from N passes to one.
        """
        if not statuses:
            return {}
        status_values = {s.value for s in statuses}
        result = {}
        async with self._get_redis_connection() as redis:
            try:
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(
                        cursor, match=f"{self.final_namespace}:*", count=1000
                    )
                    if keys:
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.get(key)
                        values = await pipe.execute()

                        for key, value in zip(keys, values):
                            if not value:
                                continue
                            try:
                                doc_data = json.loads(value)
                                if doc_data.get("status") not in status_values:
                                    continue
                                doc_id = key.split(":", 1)[1]
                                data = doc_data.copy()
                                data.pop("content", None)
                                if "file_path" not in data:
                                    data["file_path"] = "no-file-path"
                                if "metadata" not in data:
                                    data["metadata"] = {}
                                if "error_msg" not in data:
                                    data["error_msg"] = None
                                result[doc_id] = DocProcessingStatus(**data)
                            except (json.JSONDecodeError, KeyError) as e:
                                logger.error(
                                    f"[{self.workspace}] Error processing document {key}: {e}"
                                )
                                continue

                    if cursor == 0:
                        break
            except Exception as e:
                logger.error(
                    f"[{self.workspace}] SCAN interrupted while fetching docs by statuses "
                    f"— result is incomplete ({len(result)} documents collected): {e!r}"
                )
                raise

        return result

    async def get_docs_by_track_id(
        self, track_id: str
    ) -> dict[str, DocProcessingStatus]:
        """Get all documents with a specific track_id"""
        result = {}
        async with self._get_redis_connection() as redis:
            try:
                # Use SCAN to iterate through all keys in the namespace
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(
                        cursor, match=f"{self.final_namespace}:*", count=1000
                    )
                    if keys:
                        # Get all values in batch
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.get(key)
                        values = await pipe.execute()

                        # Filter by track_id and create DocProcessingStatus objects
                        for key, value in zip(keys, values):
                            if value:
                                try:
                                    doc_data = json.loads(value)
                                    if doc_data.get("track_id") == track_id:
                                        # Extract document ID from key
                                        doc_id = key.split(":", 1)[1]

                                        # Make a copy of the data to avoid modifying the original
                                        data = doc_data.copy()
                                        # Remove deprecated content field if it exists
                                        data.pop("content", None)
                                        # If file_path is not in data, use document id as file path
                                        if "file_path" not in data:
                                            data["file_path"] = "no-file-path"
                                        # Ensure new fields exist with default values
                                        if "metadata" not in data:
                                            data["metadata"] = {}
                                        if "error_msg" not in data:
                                            data["error_msg"] = None

                                        result[doc_id] = DocProcessingStatus(**data)
                                except (json.JSONDecodeError, KeyError) as e:
                                    logger.error(
                                        f"[{self.workspace}] Error processing document {key}: {e}"
                                    )
                                    continue

                    if cursor == 0:
                        break
            except Exception as e:
                logger.error(f"[{self.workspace}] Error getting docs by track_id: {e}")

        return result

    async def index_done_callback(self) -> None:
        """Redis handles persistence automatically"""
        pass

    async def is_empty(self) -> bool:
        """Check if the storage is empty for the current workspace and namespace

        Returns:
            bool: True if storage is empty, False otherwise
        """
        pattern = f"{self.final_namespace}:*"
        try:
            async with self._get_redis_connection() as redis:
                # Use scan to check if any keys exist
                async for key in redis.scan_iter(match=pattern, count=1):
                    return False  # Found at least one key
                return True  # No keys found
        except Exception as e:
            logger.error(f"[{self.workspace}] Error checking if storage is empty: {e}")
            return True

    @redis_retry
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        """Insert or update document status data"""
        if not data:
            return

        logger.debug(
            f"[{self.workspace}] Inserting {len(data)} records to {self.namespace}"
        )
        async with self._get_redis_connection() as redis:
            try:
                # Ensure chunks_list field exists for new documents
                for i, (doc_id, doc_data) in enumerate(data.items(), start=1):
                    if "chunks_list" not in doc_data:
                        doc_data["chunks_list"] = []
                    await _cooperative_yield(i)

                pipe = redis.pipeline()
                for i, (k, v) in enumerate(data.items(), start=1):
                    pipe.set(f"{self.final_namespace}:{k}", json.dumps(v))
                    await _cooperative_yield(i)
                await pipe.execute()
            except json.JSONDecodeError as e:
                logger.error(f"[{self.workspace}] JSON decode error during upsert: {e}")
                raise

    @redis_retry
    async def get_by_id(self, id: str) -> Union[dict[str, Any], None]:
        async with self._get_redis_connection() as redis:
            try:
                data = await redis.get(f"{self.final_namespace}:{id}")
                return json.loads(data) if data else None
            except json.JSONDecodeError as e:
                logger.error(f"[{self.workspace}] JSON decode error for id {id}: {e}")
                raise

    async def delete(self, doc_ids: list[str]) -> None:
        """Delete specific records from storage by their IDs"""
        if not doc_ids:
            return

        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            for doc_id in doc_ids:
                pipe.delete(f"{self.final_namespace}:{doc_id}")

            results = await pipe.execute()
            deleted_count = sum(results)
            logger.info(
                f"[{self.workspace}] Deleted {deleted_count} of {len(doc_ids)} doc status entries from {self.namespace}"
            )

    async def get_docs_paginated(
        self,
        status_filter: DocStatus | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_field: str = "updated_at",
        sort_direction: str = "desc",
    ) -> tuple[list[tuple[str, DocProcessingStatus]], int]:
        """Get documents with pagination support

        Args:
            status_filter: Filter by document status, None for all statuses
            page: Page number (1-based)
            page_size: Number of documents per page (10-200)
            sort_field: Field to sort by ('created_at', 'updated_at', 'id')
            sort_direction: Sort direction ('asc' or 'desc')

        Returns:
            Tuple of (list of (doc_id, DocProcessingStatus) tuples, total_count)
        """
        # Validate parameters
        if page < 1:
            page = 1
        if page_size < 10:
            page_size = 10
        elif page_size > 200:
            page_size = 200

        if sort_field not in ["created_at", "updated_at", "id", "file_path"]:
            sort_field = "updated_at"

        if sort_direction.lower() not in ["asc", "desc"]:
            sort_direction = "desc"

        # For Redis, we need to load all data and sort/filter in memory
        all_docs = []
        total_count = 0

        async with self._get_redis_connection() as redis:
            try:
                # Use SCAN to iterate through all keys in the namespace
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(
                        cursor, match=f"{self.final_namespace}:*", count=1000
                    )
                    if keys:
                        # Get all values in batch
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.get(key)
                        values = await pipe.execute()

                        # Process documents
                        for key, value in zip(keys, values):
                            if value:
                                try:
                                    doc_data = json.loads(value)

                                    # Apply status filter
                                    if (
                                        status_filter is not None
                                        and doc_data.get("status")
                                        != status_filter.value
                                    ):
                                        continue

                                    # Extract document ID from key
                                    doc_id = key.split(":", 1)[1]

                                    # Prepare document data
                                    data = doc_data.copy()
                                    data.pop("content", None)
                                    if "file_path" not in data:
                                        data["file_path"] = "no-file-path"
                                    if "metadata" not in data:
                                        data["metadata"] = {}
                                    if "error_msg" not in data:
                                        data["error_msg"] = None

                                    # Calculate sort key for sorting (but don't add to data)
                                    if sort_field == "id":
                                        sort_key = doc_id
                                    elif sort_field == "file_path":
                                        # Use pinyin sorting for file_path field to support Chinese characters
                                        file_path_value = data.get(sort_field, "")
                                        sort_key = get_pinyin_sort_key(file_path_value)
                                    else:
                                        sort_key = data.get(sort_field, "")

                                    doc_status = DocProcessingStatus(**data)
                                    all_docs.append((doc_id, doc_status, sort_key))

                                except (json.JSONDecodeError, KeyError) as e:
                                    logger.error(
                                        f"[{self.workspace}] Error processing document {key}: {e}"
                                    )
                                    continue

                    if cursor == 0:
                        break

            except Exception as e:
                logger.error(f"[{self.workspace}] Error getting paginated docs: {e}")
                return [], 0

        # Sort documents using the separate sort key
        reverse_sort = sort_direction.lower() == "desc"
        all_docs.sort(key=lambda x: x[2], reverse=reverse_sort)

        # Remove sort key from tuples and keep only (doc_id, doc_status)
        all_docs = [(doc_id, doc_status) for doc_id, doc_status, _ in all_docs]

        total_count = len(all_docs)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_docs = all_docs[start_idx:end_idx]

        return paginated_docs, total_count

    async def get_all_status_counts(self) -> dict[str, int]:
        """Get counts of documents in each status for all documents

        Returns:
            Dictionary mapping status names to counts, including 'all' field
        """
        counts = await self.get_status_counts()

        # Add 'all' field with total count
        total_count = sum(counts.values())
        counts["all"] = total_count

        return counts

    async def get_doc_by_file_path(self, file_path: str) -> Union[dict[str, Any], None]:
        """Get document by file path

        Args:
            file_path: The file path to search for

        Returns:
            Union[dict[str, Any], None]: Document data if found, None otherwise
            Returns the same format as get_by_id method
        """
        async with self._get_redis_connection() as redis:
            try:
                # Use SCAN to iterate through all keys in the namespace
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(
                        cursor, match=f"{self.final_namespace}:*", count=1000
                    )
                    if keys:
                        # Get all values in batch
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.get(key)
                        values = await pipe.execute()

                        # Check each document for matching file_path
                        for value in values:
                            if value:
                                try:
                                    doc_data = json.loads(value)
                                    if doc_data.get("file_path") == file_path:
                                        return doc_data
                                except json.JSONDecodeError as e:
                                    logger.error(
                                        f"[{self.workspace}] JSON decode error in get_doc_by_file_path: {e}"
                                    )
                                    continue

                    if cursor == 0:
                        break

                return None
            except Exception as e:
                logger.error(f"[{self.workspace}] Error in get_doc_by_file_path: {e}")
                return None

    async def drop(self) -> dict[str, str]:
        """Drop all document status data from storage and clean up resources"""
        try:
            async with self._get_redis_connection() as redis:
                # Use SCAN to find all keys with the namespace prefix
                pattern = f"{self.final_namespace}:*"
                cursor = 0
                deleted_count = 0

                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=1000)
                    if keys:
                        # Delete keys in batches
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.delete(key)
                        results = await pipe.execute()
                        deleted_count += sum(results)

                    if cursor == 0:
                        break

                logger.info(
                    f"[{self.workspace}] Dropped {deleted_count} doc status keys from {self.namespace}"
                )
                return {"status": "success", "message": "data dropped"}
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Error dropping doc status {self.namespace}: {e}"
            )
            return {"status": "error", "message": str(e)}


# Constants for entity prefixes (consistent with other implementations)
ENTITY_PREFIX = "ent-"
RELATION_PREFIX = "rel-"


@final
@dataclass
class RedisVectorStorage(BaseVectorStorage):
    """
    Redis Stack Vector Storage implementation using RediSearch module.

    Uses HNSW indexing with COSINE distance metric for vector similarity search.
    Requires Redis Stack (redis/redis-stack) with RediSearch module.
    """

    def __init__(
        self, namespace, global_config, embedding_func, workspace=None, meta_fields=None
    ):
        super().__init__(
            namespace=namespace,
            workspace=workspace or "",
            global_config=global_config,
            embedding_func=embedding_func,
            meta_fields=meta_fields or set(),
        )
        self.__post_init__()

    def __post_init__(self):
        # Handle workspace prefix for proper isolation
        workspace_from_env = os.environ.get("REDIS_WORKSPACE")
        if workspace_from_env:
            self.workspace = workspace_from_env
            base_namespace = f"{workspace_from_env}_{self.namespace}"
        elif self.workspace:
            base_namespace = f"{self.workspace}_{self.namespace}"
        else:
            base_namespace = self.namespace
            self.workspace = ""

        # Apply global key prefix for multi-instance isolation
        if REDIS_KEY_PREFIX:
            self.final_namespace = f"{REDIS_KEY_PREFIX}:{base_namespace}"
            logger.debug(
                f"Final namespace with key prefix: '{self.final_namespace}'"
            )
        else:
            self.final_namespace = base_namespace
            logger.debug(f"Final namespace: '{self.final_namespace}'")

        self.effective_workspace = self.workspace or "default"

        # Redis connection setup
        self._redis_url = os.environ.get(
            "REDIS_URI", config.get("redis", "uri", fallback="redis://localhost:6379")
        )
        self._pool = None
        self._redis = None
        self._initialized = False
        self._max_batch_size = self.global_config["embedding_batch_num"]

        # Index name for RediSearch
        self._index_name = f"idx:{self.final_namespace}"

        try:
            # Use shared connection pool but with binary mode for vectors
            # Note: We create a separate pool for vector storage because vectors need decode_responses=False
            self._pool = ConnectionPool.from_url(
                self._redis_url,
                max_connections=MAX_CONNECTIONS,
                socket_timeout=SOCKET_TIMEOUT,
                socket_connect_timeout=SOCKET_CONNECT_TIMEOUT,
                decode_responses=False,  # Binary mode required for vector data
            )
            self._redis = Redis(connection_pool=self._pool)
            logger.info(
                f"[{self.workspace}] Initialized Redis Vector storage for {self.namespace} with binary connection pool"
            )
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Failed to initialize Redis Vector storage: {e}"
            )
            raise

    async def initialize(self):
        """Initialize Redis connection and create index if needed"""
        async with get_data_init_lock():
            if self._initialized:
                return

            # Test connection
            try:
                await self._redis.ping()
                logger.info(
                    f"[{self.workspace}] Connected to Redis for vector namespace {self.namespace}"
                )
            except Exception as e:
                logger.error(f"[{self.workspace}] Failed to connect to Redis: {e}")
                await self.close()
                raise

            # Check if index exists
            try:
                await self._redis.ft(self._index_name).info()
                logger.info(
                    f"[{self.workspace}] RediSearch index '{self._index_name}' already exists"
                )
                # Validate dimension if index exists
                await self._validate_dimension()
            except ResponseError as e:
                if "Unknown index name" in str(e) or "Unknown Index name" in str(e):
                    logger.info(
                        f"[{self.workspace}] Index '{self._index_name}' does not exist, will be created on first upsert"
                    )
                else:
                    logger.error(
                        f"[{self.workspace}] Error checking index '{self._index_name}': {e}"
                    )
                    raise

            self._initialized = True

    async def _create_index(self, dimension: int):
        """Create RediSearch index with HNSW vector field"""
        try:
            schema = self._get_schema_for_namespace(dimension)
            index_definition = IndexDefinition(
                prefix=[f"{self.final_namespace}:"],
                index_type=IndexType.HASH,
            )

            await self._redis.ft(self._index_name).create_index(
                fields=schema, definition=index_definition
            )

            # Store dimension for validation
            await self._redis.set(
                f"{self.final_namespace}:{REDIS_VECTOR_DIM_KEY}", str(dimension)
            )

            logger.info(
                f"[{self.workspace}] Created RediSearch index '{self._index_name}' with dimension {dimension}"
            )
        except ResponseError as e:
            if "Index already exists" in str(e):
                logger.debug(
                    f"[{self.workspace}] Index '{self._index_name}' already exists"
                )
            else:
                raise

    def _get_schema_for_namespace(self, dimension: int) -> list:
        """Get RediSearch schema based on namespace type"""
        base_fields = [
            TagField("id", separator="|"),
            TagField("workspace_id", separator="|"),
            NumericField("created_at"),
            TextField("file_path", no_stem=True),
            VectorField(
                "vector",
                "HNSW",
                {
                    "TYPE": "FLOAT32",
                    "DIM": dimension,
                    "DISTANCE_METRIC": "COSINE",
                    "M": REDIS_HNSW_M,
                    "EF_CONSTRUCTION": REDIS_HNSW_EF_CONSTRUCTION,
                },
            ),
        ]

        # Add namespace-specific fields
        if "entities" in self.namespace:
            base_fields.append(TextField("entity_name", no_stem=True))
        elif "relationships" in self.namespace:
            base_fields.append(TagField("src_id", separator="|"))
            base_fields.append(TagField("tgt_id", separator="|"))
        elif "chunks" in self.namespace:
            base_fields.append(TagField("full_doc_id", separator="|"))

        return base_fields

    async def _validate_dimension(self):
        """Validate stored dimension matches current embedding function"""
        try:
            stored_dim = await self._redis.get(
                f"{self.final_namespace}:{REDIS_VECTOR_DIM_KEY}"
            )
            if stored_dim:
                stored_dim = int(stored_dim.decode() if isinstance(stored_dim, bytes) else stored_dim)
                current_dim = self.embedding_func.embedding_dim
                if stored_dim != current_dim:
                    raise ValueError(
                        f"Embedding dimension mismatch: stored={stored_dim}, current={current_dim}. "
                        f"Clear the Redis data or use the same embedding model."
                    )
        except ValueError:
            raise
        except Exception as e:
            logger.warning(
                f"[{self.workspace}] Could not validate dimension: {e}"
            )

    @asynccontextmanager
    async def _get_redis_connection(self):
        """Safe context manager for Redis operations."""
        if not self._redis:
            raise ConnectionError("Redis connection not initialized")

        try:
            yield self._redis
        except ConnectionError as e:
            logger.error(
                f"[{self.workspace}] Redis connection error in {self.namespace}: {e}"
            )
            raise
        except RedisError as e:
            logger.error(
                f"[{self.workspace}] Redis operation error in {self.namespace}: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Unexpected error in Redis operation for {self.namespace}: {e}"
            )
            raise

    @redis_retry
    async def upsert(self, data: dict[str, dict[str, Any]]) -> None:
        """Insert or update vectors in Redis"""
        if not data:
            return

        logger.debug(f"[{self.workspace}] Inserting {len(data)} vectors to {self.namespace}")

        current_time = int(time.time())

        # Prepare data for embedding
        contents = [v["content"] for v in data.values()]
        logger.info(f"[{self.namespace}] EMBED-START: {len(contents)} items, batch_size={self._max_batch_size}")

        batches = [
            contents[i : i + self._max_batch_size]
            for i in range(0, len(contents), self._max_batch_size)
        ]
        logger.info(f"[{self.namespace}] EMBED-BATCHES: {len(batches)} batches created, sizes={[len(b) for b in batches]}")

        # Compute embeddings
        logger.info(f"[{self.namespace}] EMBED-GATHER-START: Submitting {len(batches)} tasks to worker queue")
        gather_start = time.time()

        embedding_tasks = [self.embedding_func(batch) for batch in batches]
        embeddings_list = await asyncio.gather(*embedding_tasks)

        gather_elapsed = time.time() - gather_start
        logger.info(f"[{self.namespace}] EMBED-GATHER-DONE: {len(embeddings_list)} results in {gather_elapsed:.2f}s")

        embeddings = np.concatenate(embeddings_list)
        logger.info(f"[{self.namespace}] EMBED-CONCAT: Final shape={embeddings.shape}")

        # Get dimension from first embedding and ensure index exists
        dimension = embeddings.shape[1]
        try:
            await self._redis.ft(self._index_name).info()
        except ResponseError as e:
            if "Unknown index name" in str(e) or "Unknown Index name" in str(e):
                await self._create_index(dimension)
            else:
                raise

        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()

            for i, (k, v) in enumerate(data.items()):
                key = f"{self.final_namespace}:{k}"

                # Convert embedding to bytes
                vector_bytes = embeddings[i].astype(np.float32).tobytes()

                # Build hash data
                hash_data = {
                    b"id": k.encode() if isinstance(k, str) else k,
                    b"workspace_id": self.effective_workspace.encode(),
                    b"created_at": str(current_time).encode(),
                    b"vector": vector_bytes,
                }

                # Add meta fields
                for field in self.meta_fields:
                    if field in v and v[field] is not None:
                        value = v[field]
                        if isinstance(value, str):
                            hash_data[field.encode()] = value.encode()
                        else:
                            hash_data[field.encode()] = str(value).encode()

                pipe.hset(key, mapping=hash_data)

            await pipe.execute()

        logger.debug(
            f"[{self.workspace}] Successfully upserted {len(data)} vectors to {self.namespace}"
        )

    @redis_retry
    async def query(
        self, query: str, top_k: int, query_embedding: list[float] = None
    ) -> list[dict[str, Any]]:
        """Query vectors using KNN search with workspace filtering"""
        try:
            if query_embedding is not None:
                embedding = np.array(query_embedding, dtype=np.float32)
            else:
                embedding_result = await self.embedding_func([query], _priority=5)
                embedding = np.array(embedding_result[0], dtype=np.float32)

            # Build KNN query with workspace filter
            query_str = f"(@workspace_id:{{{self.effective_workspace}}})=>[KNN {top_k} @vector $vec AS distance]"

            q = (
                Query(query_str)
                .return_fields("id", "created_at", "distance", "file_path", "entity_name", "src_id", "tgt_id", "full_doc_id")
                .sort_by("distance")
                .dialect(2)
            )

            async with self._get_redis_connection() as redis:
                results = await redis.ft(self._index_name).search(
                    q, query_params={"vec": embedding.tobytes()}
                )

            output = []
            for doc in results.docs:
                # Parse result document
                result_dict = {
                    "id": doc.id.split(":")[-1] if ":" in doc.id else doc.id,
                    "distance": float(doc.distance) if hasattr(doc, "distance") else 0.0,
                }

                # Decode bytes to string for all fields
                for field in ["created_at", "file_path", "entity_name", "src_id", "tgt_id", "full_doc_id"]:
                    if hasattr(doc, field):
                        value = getattr(doc, field)
                        if value is not None:
                            if isinstance(value, bytes):
                                result_dict[field] = value.decode()
                            else:
                                result_dict[field] = str(value)

                # Filter by cosine threshold (COSINE distance: 0 = identical, 2 = opposite)
                # Convert cosine distance to similarity: similarity = 1 - distance
                if result_dict["distance"] <= (1 - self.cosine_better_than_threshold):
                    output.append(result_dict)

            return output

        except ResponseError as e:
            if "Unknown index name" in str(e) or "Unknown Index name" in str(e):
                logger.warning(
                    f"[{self.workspace}] Index '{self._index_name}' not found, returning empty results"
                )
                return []
            raise
        except Exception as e:
            logger.error(f"[{self.workspace}] Error during vector query: {e}")
            return []

    @redis_retry
    async def delete(self, ids: list[str]) -> None:
        """Delete vectors by their IDs"""
        if not ids:
            return

        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            for id in ids:
                key = f"{self.final_namespace}:{id}"
                pipe.delete(key)
            await pipe.execute()

        logger.debug(
            f"[{self.workspace}] Deleted {len(ids)} vectors from {self.namespace}"
        )

    @redis_retry
    async def delete_entity(self, entity_name: str) -> None:
        """Delete an entity by its name"""
        try:
            # Generate entity ID using same function as storage
            entity_id = compute_mdhash_id(entity_name, prefix=ENTITY_PREFIX)
            await self.delete([entity_id])
            logger.debug(f"[{self.workspace}] Deleted entity '{entity_name}'")
        except Exception as e:
            logger.error(f"[{self.workspace}] Error deleting entity '{entity_name}': {e}")

    @redis_retry
    async def delete_entity_relation(self, entity_name: str) -> None:
        """Delete all relations associated with an entity"""
        try:
            # Query for relations where entity is source or target
            query_str = f"(@workspace_id:{{{self.effective_workspace}}}) (@src_id:{{{entity_name}}} | @tgt_id:{{{entity_name}}})"

            q = Query(query_str).return_fields("id").no_content().dialect(2)

            async with self._get_redis_connection() as redis:
                results = await redis.ft(self._index_name).search(q)

                if results.docs:
                    ids_to_delete = [
                        doc.id.split(":")[-1] if ":" in doc.id else doc.id
                        for doc in results.docs
                    ]
                    await self.delete(ids_to_delete)
                    logger.debug(
                        f"[{self.workspace}] Deleted {len(ids_to_delete)} relations for entity '{entity_name}'"
                    )
                else:
                    logger.debug(
                        f"[{self.workspace}] No relations found for entity '{entity_name}'"
                    )
        except ResponseError as e:
            if "Unknown index name" in str(e) or "Unknown Index name" in str(e):
                logger.debug(
                    f"[{self.workspace}] Index not found, no relations to delete for '{entity_name}'"
                )
            else:
                logger.error(
                    f"[{self.workspace}] Error deleting relations for '{entity_name}': {e}"
                )
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Error deleting relations for '{entity_name}': {e}"
            )

    @redis_retry
    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get vector data by its ID (excluding vector field)"""
        try:
            async with self._get_redis_connection() as redis:
                key = f"{self.final_namespace}:{id}"
                data = await redis.hgetall(key)

                if not data:
                    return None

                # Convert bytes to appropriate types, exclude vector
                result = {}
                for k, v in data.items():
                    key_str = k.decode() if isinstance(k, bytes) else k
                    if key_str == "vector":
                        continue  # Skip vector data
                    if isinstance(v, bytes):
                        result[key_str] = v.decode()
                    else:
                        result[key_str] = v

                # Convert created_at to int if present
                if "created_at" in result:
                    result["created_at"] = int(result["created_at"])

                return result
        except Exception as e:
            logger.error(f"[{self.workspace}] Error getting vector by id '{id}': {e}")
            return None

    @redis_retry
    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """Get multiple vector data by their IDs"""
        if not ids:
            return []

        try:
            async with self._get_redis_connection() as redis:
                pipe = redis.pipeline()
                for id in ids:
                    key = f"{self.final_namespace}:{id}"
                    pipe.hgetall(key)
                results = await pipe.execute()

                output = []
                for result in results:
                    if not result:
                        output.append(None)
                        continue

                    # Convert bytes to appropriate types, exclude vector
                    item = {}
                    for k, v in result.items():
                        key_str = k.decode() if isinstance(k, bytes) else k
                        if key_str == "vector":
                            continue
                        if isinstance(v, bytes):
                            item[key_str] = v.decode()
                        else:
                            item[key_str] = v

                    if "created_at" in item:
                        item["created_at"] = int(item["created_at"])

                    output.append(item)

                return output
        except Exception as e:
            logger.error(f"[{self.workspace}] Error getting vectors by ids: {e}")
            return [None] * len(ids)

    @redis_retry
    async def get_vectors_by_ids(self, ids: list[str]) -> dict[str, list[float]]:
        """Get vectors by their IDs, returning ID to vector mapping"""
        if not ids:
            return {}

        try:
            async with self._get_redis_connection() as redis:
                pipe = redis.pipeline()
                for id in ids:
                    key = f"{self.final_namespace}:{id}"
                    pipe.hget(key, "vector")
                results = await pipe.execute()

                vectors_dict = {}
                for id, vector_bytes in zip(ids, results):
                    if vector_bytes:
                        # Convert bytes back to float list
                        vector = np.frombuffer(vector_bytes, dtype=np.float32).tolist()
                        vectors_dict[id] = vector

                return vectors_dict
        except Exception as e:
            logger.error(f"[{self.workspace}] Error getting vectors by ids: {e}")
            return {}

    async def index_done_callback(self) -> None:
        """No-op: Redis handles persistence automatically"""
        pass

    async def drop(self) -> dict[str, str]:
        """Drop all vector data from storage"""
        try:
            async with self._get_redis_connection() as redis:
                # Drop the index with all associated documents
                try:
                    await redis.ft(self._index_name).dropindex(delete_documents=True)
                    logger.info(
                        f"[{self.workspace}] Dropped index '{self._index_name}' and all documents"
                    )
                except ResponseError as e:
                    if "Unknown index name" not in str(e) and "Unknown Index name" not in str(e):
                        raise
                    logger.debug(
                        f"[{self.workspace}] Index '{self._index_name}' did not exist"
                    )

                # Also clean up dimension key
                await redis.delete(f"{self.final_namespace}:{REDIS_VECTOR_DIM_KEY}")

                return {"status": "success", "message": "data dropped"}
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Error dropping vector storage {self.namespace}: {e}"
            )
            return {"status": "error", "message": str(e)}

    async def close(self):
        """Close the Redis connection and release resources"""
        if hasattr(self, "_redis") and self._redis:
            try:
                await self._redis.close()
                logger.debug(
                    f"[{self.workspace}] Closed Redis connection for {self.namespace}"
                )
            except Exception as e:
                logger.error(f"[{self.workspace}] Error closing Redis connection: {e}")
            finally:
                self._redis = None

        if hasattr(self, "_pool") and self._pool:
            try:
                await self._pool.disconnect()
            except Exception as e:
                logger.debug(
                    f"[{self.workspace}] Error disconnecting pool: {e}"
                )
            finally:
                self._pool = None

    async def __aenter__(self):
        """Support for async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure Redis resources are cleaned up when exiting context."""
        await self.close()


@final
@dataclass
class RedisGraphStorage(BaseGraphStorage):
    """
    Redis-based graph storage using hashes for nodes/edges and sets for adjacency lists.

    Stores knowledge graph (entities and relationships) in Redis:
    - Nodes as Redis hashes: {namespace}:node:{node_id} → properties
    - Edges as Redis hashes: {namespace}:edge:{src}:{tgt} → properties
    - Adjacency as Redis sets: {namespace}:node:{node_id}:edges → set of neighbors
    - Indexes as sets: {namespace}:nodes, {namespace}:edges:all
    """

    def __init__(self, namespace, global_config, embedding_func, workspace=None):
        super().__init__(
            namespace=namespace,
            workspace=workspace or "",
            global_config=global_config,
            embedding_func=embedding_func,
        )
        self.__post_init__()

    def __post_init__(self):
        # Handle workspace prefix for proper isolation
        workspace_from_env = os.environ.get("REDIS_WORKSPACE")
        if workspace_from_env:
            self.workspace = workspace_from_env
            base_namespace = f"{workspace_from_env}_{self.namespace}"
        elif self.workspace:
            base_namespace = f"{self.workspace}_{self.namespace}"
        else:
            base_namespace = self.namespace
            self.workspace = ""

        # Apply global key prefix for multi-instance isolation
        if REDIS_KEY_PREFIX:
            self.final_namespace = f"{REDIS_KEY_PREFIX}:{base_namespace}"
            logger.debug(
                f"Final namespace with key prefix: '{self.final_namespace}'"
            )
        else:
            self.final_namespace = base_namespace
            logger.debug(f"Final namespace: '{self.final_namespace}'")

        # Redis connection setup
        self._redis_url = os.environ.get(
            "REDIS_URI", config.get("redis", "uri", fallback="redis://localhost:6379")
        )
        self._pool = None
        self._redis = None
        self._initialized = False

        try:
            # Use shared connection pool
            self._pool = RedisConnectionManager.get_pool(self._redis_url)
            self._redis = Redis(connection_pool=self._pool)
            logger.info(
                f"[{self.workspace}] Initialized Redis Graph storage for {self.namespace} using shared connection pool"
            )
        except Exception as e:
            # Clean up on initialization failure
            if self._redis_url:
                RedisConnectionManager.release_pool(self._redis_url)
            logger.error(
                f"[{self.workspace}] Failed to initialize Redis Graph storage: {e}"
            )
            raise

    async def initialize(self):
        """Initialize Redis connection"""
        async with get_data_init_lock():
            if self._initialized:
                return

            # Test connection
            try:
                async with self._get_redis_connection() as redis:
                    await redis.ping()
                    logger.info(
                        f"[{self.workspace}] Connected to Redis for graph namespace {self.namespace}"
                    )
                    self._initialized = True
            except Exception as e:
                logger.error(f"[{self.workspace}] Failed to connect to Redis: {e}")
                await self.close()
                raise

    @asynccontextmanager
    async def _get_redis_connection(self):
        """Safe context manager for Redis operations."""
        if not self._redis:
            raise ConnectionError("Redis connection not initialized")

        try:
            yield self._redis
        except ConnectionError as e:
            logger.error(
                f"[{self.workspace}] Redis connection error in {self.namespace}: {e}"
            )
            raise
        except RedisError as e:
            logger.error(
                f"[{self.workspace}] Redis operation error in {self.namespace}: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Unexpected error in Redis operation for {self.namespace}: {e}"
            )
            raise

    @redis_retry
    async def has_node(self, node_id: str) -> bool:
        """Check if a node exists"""
        async with self._get_redis_connection() as redis:
            return bool(await redis.exists(f"{self.final_namespace}:node:{node_id}"))

    @redis_retry
    async def has_edge(self, source_node_id: str, target_node_id: str) -> bool:
        """Check if an edge exists"""
        async with self._get_redis_connection() as redis:
            return bool(await redis.exists(f"{self.final_namespace}:edge:{source_node_id}:{target_node_id}"))

    @redis_retry
    async def node_degree(self, node_id: str) -> int:
        """Get the degree (number of edges) of a node"""
        async with self._get_redis_connection() as redis:
            degree = await redis.scard(f"{self.final_namespace}:node:{node_id}:edges")
            return degree if degree is not None else 0

    @redis_retry
    async def edge_degree(self, src_id: str, tgt_id: str) -> int:
        """Get the total degree of an edge (sum of source and target node degrees)"""
        src_degree = await self.node_degree(src_id)
        tgt_degree = await self.node_degree(tgt_id)
        return src_degree + tgt_degree

    @redis_retry
    async def get_node(self, node_id: str) -> dict[str, str] | None:
        """Get node properties"""
        async with self._get_redis_connection() as redis:
            data = await redis.hgetall(f"{self.final_namespace}:node:{node_id}")
            if not data:
                return None
            # Convert bytes to strings
            return {k.decode() if isinstance(k, bytes) else k:
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in data.items()}

    @redis_retry
    async def get_edge(self, source_node_id: str, target_node_id: str) -> dict[str, Any] | None:
        """Get edge properties"""
        async with self._get_redis_connection() as redis:
            data = await redis.hgetall(f"{self.final_namespace}:edge:{source_node_id}:{target_node_id}")
            if not data:
                return None
            # Convert bytes to strings and restore numeric types for known fields
            result = {}
            for k, v in data.items():
                key = k.decode() if isinstance(k, bytes) else k
                value = v.decode() if isinstance(v, bytes) else v
                # Convert known numeric fields back to their proper types
                if key in NUMERIC_EDGE_FIELDS:
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        pass  # Keep as string if conversion fails
                result[key] = value
            return result

    @redis_retry
    async def get_node_edges(self, source_node_id: str) -> list[tuple[str, str]] | None:
        """Get all edges for a node"""
        if not await self.has_node(source_node_id):
            return None

        async with self._get_redis_connection() as redis:
            neighbors = await redis.smembers(f"{self.final_namespace}:node:{source_node_id}:edges")
            # Convert bytes to strings and return as tuples
            edges = []
            for neighbor in neighbors:
                neighbor_str = neighbor.decode() if isinstance(neighbor, bytes) else neighbor
                edges.append((source_node_id, neighbor_str))
            return edges

    @redis_retry
    async def upsert_node(self, node_id: str, node_data: dict[str, str]) -> None:
        """Insert or update a node"""
        async with self._get_redis_connection() as redis:
            # Convert all values to strings and encode for Redis
            encoded_data = {k.encode() if isinstance(k, str) else k:
                           str(v).encode() if isinstance(v, str) else str(v).encode()
                           for k, v in node_data.items()}

            pipe = redis.pipeline()
            # Store node properties
            pipe.hset(f"{self.final_namespace}:node:{node_id}", mapping=encoded_data)
            # Add to nodes index
            pipe.sadd(f"{self.final_namespace}:nodes", node_id)
            await pipe.execute()

    @redis_retry
    async def upsert_edge(self, source_node_id: str, target_node_id: str, edge_data: dict[str, str]) -> None:
        """Insert or update an edge (undirected)"""
        async with self._get_redis_connection() as redis:
            # Convert all values to strings and encode for Redis
            encoded_data = {k.encode() if isinstance(k, str) else k:
                           str(v).encode() if isinstance(v, str) else str(v).encode()
                           for k, v in edge_data.items()}

            pipe = redis.pipeline()
            # Store edge properties
            pipe.hset(f"{self.final_namespace}:edge:{source_node_id}:{target_node_id}", mapping=encoded_data)
            # Update adjacency lists (both directions for undirected graph)
            pipe.sadd(f"{self.final_namespace}:node:{source_node_id}:edges", target_node_id)
            pipe.sadd(f"{self.final_namespace}:node:{target_node_id}:edges", source_node_id)
            # Add to edges index
            pipe.sadd(f"{self.final_namespace}:edges:all", f"{source_node_id}:{target_node_id}")
            await pipe.execute()

    @redis_retry
    async def delete_node(self, node_id: str) -> None:
        """Delete a node and its associated edges"""
        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            # Remove node
            pipe.delete(f"{self.final_namespace}:node:{node_id}")
            # Remove adjacency list
            pipe.delete(f"{self.final_namespace}:node:{node_id}:edges")
            # Remove from nodes index
            pipe.srem(f"{self.final_namespace}:nodes", node_id)
            await pipe.execute()

    @redis_retry
    async def remove_nodes(self, nodes: list[str]) -> None:
        """Delete multiple nodes"""
        if not nodes:
            return

        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            for node_id in nodes:
                pipe.delete(f"{self.final_namespace}:node:{node_id}")
                pipe.delete(f"{self.final_namespace}:node:{node_id}:edges")
                pipe.srem(f"{self.final_namespace}:nodes", node_id)
            await pipe.execute()

        logger.debug(f"[{self.workspace}] Removed {len(nodes)} nodes from graph")

    @redis_retry
    async def remove_edges(self, edges: list[tuple[str, str]]) -> None:
        """Delete multiple edges"""
        if not edges:
            return

        async with self._get_redis_connection() as redis:
            pipe = redis.pipeline()
            for src_id, tgt_id in edges:
                # Remove edge properties
                pipe.delete(f"{self.final_namespace}:edge:{src_id}:{tgt_id}")
                # Remove from adjacency lists (both directions)
                pipe.srem(f"{self.final_namespace}:node:{src_id}:edges", tgt_id)
                pipe.srem(f"{self.final_namespace}:node:{tgt_id}:edges", src_id)
                # Remove from edges index
                pipe.srem(f"{self.final_namespace}:edges:all", f"{src_id}:{tgt_id}")
            await pipe.execute()

        logger.debug(f"[{self.workspace}] Removed {len(edges)} edges from graph")

    @redis_retry
    async def get_all_labels(self) -> list[str]:
        """Get all node IDs sorted alphabetically"""
        async with self._get_redis_connection() as redis:
            nodes = await redis.smembers(f"{self.final_namespace}:nodes")
            # Convert bytes to strings and sort
            node_list = [n.decode() if isinstance(n, bytes) else n for n in nodes]
            return sorted(node_list)

    @redis_retry
    async def get_all_nodes(self) -> list[dict]:
        """Get all nodes with their properties"""
        async with self._get_redis_connection() as redis:
            # Get all node IDs
            node_ids = await redis.smembers(f"{self.final_namespace}:nodes")

            if not node_ids:
                return []

            # Fetch all nodes using pipeline
            pipe = redis.pipeline()
            for node_id in node_ids:
                node_id_str = node_id.decode() if isinstance(node_id, bytes) else node_id
                pipe.hgetall(f"{self.final_namespace}:node:{node_id_str}")
            results = await pipe.execute()

            # Format results
            nodes = []
            for node_id, props in zip(node_ids, results):
                node_id_str = node_id.decode() if isinstance(node_id, bytes) else node_id
                if props:
                    node_dict = {k.decode() if isinstance(k, bytes) else k:
                                v.decode() if isinstance(v, bytes) else v
                                for k, v in props.items()}
                    node_dict["id"] = node_id_str
                    nodes.append(node_dict)

            return nodes

    @redis_retry
    async def get_all_edges(self) -> list[dict]:
        """Get all edges with their properties"""
        async with self._get_redis_connection() as redis:
            # Get all edge keys
            edge_keys = await redis.smembers(f"{self.final_namespace}:edges:all")

            if not edge_keys:
                return []

            # Fetch all edges using pipeline
            pipe = redis.pipeline()
            for edge_key in edge_keys:
                edge_key_str = edge_key.decode() if isinstance(edge_key, bytes) else edge_key
                src_id, tgt_id = edge_key_str.split(":", 1)
                pipe.hgetall(f"{self.final_namespace}:edge:{src_id}:{tgt_id}")
            results = await pipe.execute()

            # Format results
            edges = []
            for edge_key, props in zip(edge_keys, results):
                edge_key_str = edge_key.decode() if isinstance(edge_key, bytes) else edge_key
                src_id, tgt_id = edge_key_str.split(":", 1)
                if props:
                    edge_dict = {k.decode() if isinstance(k, bytes) else k:
                                v.decode() if isinstance(v, bytes) else v
                                for k, v in props.items()}
                    edge_dict["source"] = src_id
                    edge_dict["target"] = tgt_id
                    edges.append(edge_dict)

            return edges

    @redis_retry
    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        """Get most connected nodes by degree"""
        async with self._get_redis_connection() as redis:
            # Get all node IDs
            node_ids = await redis.smembers(f"{self.final_namespace}:nodes")

            if not node_ids:
                return []

            # Get degrees using pipeline
            pipe = redis.pipeline()
            for node_id in node_ids:
                node_id_str = node_id.decode() if isinstance(node_id, bytes) else node_id
                pipe.scard(f"{self.final_namespace}:node:{node_id_str}:edges")
            degrees = await pipe.execute()

            # Create (node_id, degree) pairs
            node_degrees = []
            for node_id, degree in zip(node_ids, degrees):
                node_id_str = node_id.decode() if isinstance(node_id, bytes) else node_id
                node_degrees.append((node_id_str, degree if degree is not None else 0))

            # Sort by degree (descending) then alphabetically
            node_degrees.sort(key=lambda x: (-x[1], x[0]))

            # Return top N node IDs
            return [node_id for node_id, _ in node_degrees[:limit]]

    @redis_retry
    async def search_labels(self, query: str, limit: int = 50) -> list[str]:
        """Search node labels with fuzzy matching"""
        async with self._get_redis_connection() as redis:
            # Get all node IDs
            node_ids = await redis.smembers(f"{self.final_namespace}:nodes")

            if not node_ids:
                return []

            # Convert to strings
            node_list = [n.decode() if isinstance(n, bytes) else n for n in node_ids]

            # Fuzzy matching algorithm (from NetworkX implementation)
            query_lower = query.lower()
            matches = []

            for node_str in node_list:
                node_lower = node_str.lower()

                # Skip if no match
                if query_lower not in node_lower:
                    continue

                # Calculate relevance score
                score = 0
                # Exact match gets highest score
                if node_lower == query_lower:
                    score = 1000
                # Prefix match gets high score
                elif node_lower.startswith(query_lower):
                    score = 500
                # Contains match gets base score
                else:
                    score = 100 - len(node_str)
                    # Bonus for word boundary matches
                    if f" {query_lower}" in node_lower or f"_{query_lower}" in node_lower:
                        score += 50

                matches.append((node_str, score))

            # Sort by relevance score (desc) then alphabetically
            matches.sort(key=lambda x: (-x[1], x[0]))

            # Return top matches
            return [match[0] for match in matches[:limit]]

    @redis_retry
    async def get_knowledge_graph(
        self, node_label: str, max_depth: int = 3, max_nodes: int = None
    ) -> KnowledgeGraph:
        """Get connected subgraph using BFS"""
        # Get max_nodes from global_config if not provided
        if max_nodes is None:
            max_nodes = self.global_config.get("max_graph_nodes", 1000)
        else:
            max_nodes = min(max_nodes, self.global_config.get("max_graph_nodes", 1000))

        result = KnowledgeGraph()

        async with self._get_redis_connection() as redis:
            # Handle special case for "*" label (all nodes)
            if node_label == "*":
                # Get all nodes with their degrees
                node_ids = await redis.smembers(f"{self.final_namespace}:nodes")
                node_list = [n.decode() if isinstance(n, bytes) else n for n in node_ids]

                # Get degrees using pipeline
                pipe = redis.pipeline()
                for node_id in node_list:
                    pipe.scard(f"{self.final_namespace}:node:{node_id}:edges")
                degrees = await pipe.execute()

                # Sort by degree
                node_degrees = [(nid, deg if deg is not None else 0)
                               for nid, deg in zip(node_list, degrees)]
                node_degrees.sort(key=lambda x: x[1], reverse=True)

                # Check if truncated
                if len(node_degrees) > max_nodes:
                    result.is_truncated = True
                    logger.info(
                        f"[{self.workspace}] Graph truncated: {len(node_degrees)} nodes, limited to {max_nodes}"
                    )

                limited_nodes = [nid for nid, _ in node_degrees[:max_nodes]]
            else:
                # Check if starting node exists
                if not await self.has_node(node_label):
                    logger.warning(f"[{self.workspace}] Node {node_label} not found")
                    return KnowledgeGraph()

                # BFS with degree prioritization
                bfs_nodes = []
                visited = set()

                # Get initial node degree
                init_degree = await self.node_degree(node_label)
                queue = [(node_label, 0, init_degree)]

                while queue and len(bfs_nodes) < max_nodes:
                    current_depth = queue[0][1]

                    # Collect all nodes at current depth
                    current_level = []
                    while queue and queue[0][1] == current_depth:
                        current_level.append(queue.pop(0))

                    # Sort by degree (highest first)
                    current_level.sort(key=lambda x: x[2], reverse=True)

                    # Process nodes at this level
                    for node, depth, _ in current_level:
                        if node in visited or len(bfs_nodes) >= max_nodes:
                            continue

                        visited.add(node)
                        bfs_nodes.append(node)

                        # Add neighbors to queue if within depth limit
                        if depth < max_depth:
                            neighbors = await redis.smembers(f"{self.final_namespace}:node:{node}:edges")
                            for neighbor in neighbors:
                                neighbor_str = neighbor.decode() if isinstance(neighbor, bytes) else neighbor
                                if neighbor_str not in visited:
                                    neighbor_degree = await self.node_degree(neighbor_str)
                                    queue.append((neighbor_str, depth + 1, neighbor_degree))

                limited_nodes = bfs_nodes

            # Fetch nodes and edges for the subgraph
            # Get node data
            pipe = redis.pipeline()
            for node_id in limited_nodes:
                pipe.hgetall(f"{self.final_namespace}:node:{node_id}")
            node_data_list = await pipe.execute()

            # Build KnowledgeGraph nodes
            for node_id, props in zip(limited_nodes, node_data_list):
                if props:
                    node_props = {k.decode() if isinstance(k, bytes) else k:
                                 v.decode() if isinstance(v, bytes) else v
                                 for k, v in props.items()}
                    kg_node = KnowledgeGraphNode(
                        id=node_id,
                        labels=[node_id],
                        properties=node_props
                    )
                    result.nodes.append(kg_node)

            # Get edges between nodes in subgraph
            limited_set = set(limited_nodes)
            seen_edges = set()

            for node_id in limited_nodes:
                neighbors = await redis.smembers(f"{self.final_namespace}:node:{node_id}:edges")
                for neighbor in neighbors:
                    neighbor_str = neighbor.decode() if isinstance(neighbor, bytes) else neighbor
                    if neighbor_str in limited_set:
                        # Avoid duplicates (undirected graph)
                        edge_key = tuple(sorted([node_id, neighbor_str]))
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)

                            # Get edge properties
                            edge_props = await redis.hgetall(f"{self.final_namespace}:edge:{node_id}:{neighbor_str}")
                            props_dict = {k.decode() if isinstance(k, bytes) else k:
                                         v.decode() if isinstance(v, bytes) else v
                                         for k, v in edge_props.items()} if edge_props else {}

                            kg_edge = KnowledgeGraphEdge(
                                id=f"{node_id}-{neighbor_str}",
                                source=node_id,
                                target=neighbor_str,
                                type=props_dict.get("relationship"),
                                properties=props_dict
                            )
                            result.edges.append(kg_edge)

            return result

    @redis_retry
    async def drop(self) -> dict[str, str]:
        """Drop all graph data"""
        try:
            async with self._get_redis_connection() as redis:
                # Scan and delete all keys with namespace prefix
                pattern = f"{self.final_namespace}:*"
                cursor = 0
                deleted_count = 0

                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=1000)
                    if keys:
                        pipe = redis.pipeline()
                        for key in keys:
                            pipe.delete(key)
                        results = await pipe.execute()
                        deleted_count += sum(results)

                    if cursor == 0:
                        break

                logger.info(
                    f"[{self.workspace}] Dropped {deleted_count} graph keys from {self.namespace}"
                )
                return {"status": "success", "message": "data dropped"}
        except Exception as e:
            logger.error(
                f"[{self.workspace}] Error dropping graph storage {self.namespace}: {e}"
            )
            return {"status": "error", "message": str(e)}

    async def index_done_callback(self) -> None:
        """No-op: Redis handles persistence automatically"""
        pass

    async def close(self):
        """Close the Redis connection and release pool reference"""
        if hasattr(self, "_redis") and self._redis:
            try:
                await self._redis.close()
                logger.debug(
                    f"[{self.workspace}] Closed Redis connection for {self.namespace}"
                )
            except Exception as e:
                logger.error(f"[{self.workspace}] Error closing Redis connection: {e}")
            finally:
                self._redis = None

        # Release the pool reference
        if hasattr(self, "_redis_url") and self._redis_url:
            RedisConnectionManager.release_pool(self._redis_url)
            self._pool = None
            logger.debug(
                f"[{self.workspace}] Released Redis connection pool reference for {self.namespace}"
            )

    async def __aenter__(self):
        """Support for async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure Redis resources are cleaned up when exiting context."""
        await self.close()
