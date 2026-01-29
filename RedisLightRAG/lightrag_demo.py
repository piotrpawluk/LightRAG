#!/usr/bin/env python3
"""
LightRAG with Qwen 3 - Example Usage Script

This script demonstrates how to interact with LightRAG using Qwen 3 models
for both LLM and embeddings, with Redis vector store and NetworkX graph store.
"""

import requests
import json
import time
from typing import List, Dict, Any


class LightRAGClient:
    """Client for interacting with LightRAG API"""
    
    def __init__(self, base_url: str = "http://localhost:9621"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def health_check(self) -> Dict[str, Any]:
        """Check if LightRAG service is healthy"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            return {"status": "healthy", "response": response.json()}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def insert_document(self, text: str) -> Dict[str, Any]:
        """Insert a single document into LightRAG"""
        try:
            response = self.session.post(
                f"{self.base_url}/insert",
                json={"text": text}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def batch_insert(self, texts: List[str]) -> Dict[str, Any]:
        """Insert multiple documents at once"""
        try:
            response = self.session.post(
                f"{self.base_url}/batch_insert",
                json={"texts": texts}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def query(
        self, 
        query: str, 
        mode: str = "hybrid",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Query LightRAG with different retrieval modes
        
        Args:
            query: The question or query text
            mode: One of 'naive', 'local', 'global', 'hybrid', 'mix'
            top_k: Number of results to retrieve
        """
        try:
            response = self.session.post(
                f"{self.base_url}/query",
                json={
                    "query": query,
                    "mode": mode,
                    "top_k": top_k
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def compare_query_modes(self, query: str) -> Dict[str, Any]:
        """Compare results across different query modes"""
        modes = ["naive", "local", "global", "hybrid", "mix"]
        results = {}
        
        for mode in modes:
            print(f"Querying with {mode} mode...")
            result = self.query(query, mode=mode)
            results[mode] = result
            time.sleep(0.5)  # Small delay between requests
        
        return results


def demo_basic_usage():
    """Demonstrate basic LightRAG usage"""
    print("=" * 60)
    print("LightRAG with Qwen 3 - Basic Usage Demo")
    print("=" * 60)
    
    client = LightRAGClient()
    
    # Health check
    print("\n1. Health Check")
    print("-" * 60)
    health = client.health_check()
    print(json.dumps(health, indent=2))
    
    if health["status"] != "healthy":
        print("\n⚠️  Service is not healthy. Please check the logs.")
        return
    
    # Insert sample documents
    print("\n2. Inserting Documents")
    print("-" * 60)
    
    documents = [
        """LightRAG is a graph-enhanced Retrieval-Augmented Generation system that 
        combines vector search with knowledge graph capabilities. It extracts entities 
        and relationships from documents to build a comprehensive knowledge graph.""",
        
        """Qwen 3 is a state-of-the-art language model supporting over 100 languages. 
        The embedding model achieves top performance on the MTEB multilingual leaderboard 
        with a score of 70.58.""",
        
        """Redis Stack provides vector search capabilities with HNSW and FLAT indexes. 
        It offers in-memory performance with persistence options, making it ideal for 
        real-time RAG applications.""",
        
        """NetworkX is a Python library for creating, manipulating, and studying complex 
        networks and graphs. In LightRAG, it serves as the default graph storage backend 
        for managing entity relationships.""",
        
        """Docker Compose orchestrates multi-container applications. This setup includes 
        Ollama for model serving, Redis for vector storage, and LightRAG for the RAG 
        pipeline, all running in isolated containers."""
    ]
    
    print(f"Inserting {len(documents)} documents...")
    result = client.batch_insert(documents)
    print(json.dumps(result, indent=2))
    
    # Wait for processing
    print("\nWaiting for documents to be processed...")
    time.sleep(5)
    
    # Query examples
    print("\n3. Querying with Different Modes")
    print("-" * 60)
    
    queries = [
        "What is LightRAG and how does it work?",
        "Explain the role of Redis in this setup",
        "What are the capabilities of Qwen 3?",
    ]
    
    for i, query_text in enumerate(queries, 1):
        print(f"\nQuery {i}: {query_text}")
        print("-" * 60)
        
        # Try hybrid mode (recommended)
        result = client.query(query_text, mode="hybrid")
        
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Answer: {result.get('answer', 'No answer provided')}")
            
            if 'context' in result:
                print(f"\nContext items retrieved: {len(result['context'])}")


def demo_query_mode_comparison():
    """Compare different query modes"""
    print("\n" + "=" * 60)
    print("LightRAG Query Mode Comparison")
    print("=" * 60)
    
    client = LightRAGClient()
    
    query = "How does graph-based retrieval enhance RAG systems?"
    print(f"\nQuery: {query}")
    print("-" * 60)
    
    results = client.compare_query_modes(query)
    
    for mode, result in results.items():
        print(f"\n{mode.upper()} Mode Result:")
        if "error" in result:
            print(f"  Error: {result['error']}")
        else:
            answer = result.get('answer', 'No answer')
            print(f"  {answer[:200]}...")  # First 200 chars


def demo_advanced_usage():
    """Demonstrate advanced features"""
    print("\n" + "=" * 60)
    print("LightRAG Advanced Usage")
    print("=" * 60)
    
    client = LightRAGClient()
    
    # Insert domain-specific documents
    print("\n1. Building Domain Knowledge Base")
    print("-" * 60)
    
    ml_documents = [
        """Machine learning embeddings convert text into dense vector representations. 
        The Qwen 3 Embedding model uses a dual-encoder architecture to create 
        1024-dimensional vectors that capture semantic meaning.""",
        
        """Vector similarity search uses distance metrics like cosine similarity to find 
        semantically related documents. Redis implements HNSW (Hierarchical Navigable 
        Small World) for efficient approximate nearest neighbor search.""",
        
        """Knowledge graphs represent information as nodes (entities) and edges 
        (relationships). Graph-based retrieval can traverse these connections to discover 
        multi-hop relationships that pure vector search might miss.""",
        
        """RAG systems combine retrieval with generation. First, relevant context is 
        retrieved from a knowledge base. Then, an LLM generates an answer using both 
        the query and retrieved context.""",
    ]
    
    print(f"Inserting {len(ml_documents)} ML/AI domain documents...")
    result = client.batch_insert(ml_documents)
    print(f"Status: {result.get('status', 'unknown')}")
    
    time.sleep(5)
    
    # Complex queries
    print("\n2. Complex Queries")
    print("-" * 60)
    
    complex_queries = [
        "Compare vector similarity search with graph-based retrieval",
        "Explain the complete RAG pipeline from query to answer",
        "How do embeddings enable semantic search?",
    ]
    
    for query_text in complex_queries:
        print(f"\nQuery: {query_text}")
        result = client.query(query_text, mode="mix", top_k=15)
        
        if "error" not in result:
            answer = result.get('answer', '')
            print(f"Answer ({len(answer)} chars): {answer[:150]}...")


def main():
    """Main execution"""
    print("\n🚀 Starting LightRAG Demo with Qwen 3 Models")
    print("=" * 60)
    
    try:
        # Basic usage demo
        demo_basic_usage()
        
        # Query mode comparison
        demo_query_mode_comparison()
        
        # Advanced usage
        demo_advanced_usage()
        
        print("\n" + "=" * 60)
        print("✅ Demo completed successfully!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
