# LightRAG Helm Chart

Helm chart for deploying LightRAG (Retrieval-Augmented Generation) with full Redis Stack storage on OpenShift/OKD.

## Overview

This Helm chart deploys LightRAG with:
- **Redis Stack** for all storage (KV, Vector, Graph, DocStatus)
- **External Qwen3 APIs** for LLM and embeddings
- **No PVC required** - Works in restricted OKD namespaces
- **Multi-replica support** - RedisGraphStorage enables horizontal scaling
- **4096-dimensional embeddings** - High-quality Qwen3-Embedding-8B

## Prerequisites

- Kubernetes 1.19+ or OpenShift/OKD 4.8+
- Helm 3.0+
- Access to external Redis instance
- Access to external Qwen3 API endpoints

## Installation

### Quick Start

```bash
# Install in 'pp' namespace
helm install lightrag ./helm/lightrag -n pp

# Install with production values
helm install lightrag ./helm/lightrag -n pp -f values-prod.yaml
```

### Custom Values

```bash
# Install with custom image
helm install lightrag ./helm/lightrag -n pp \
  --set image.digest=sha256:YOUR_DIGEST

# Install with custom workers
helm install lightrag ./helm/lightrag -n pp \
  --set config.server.workers=8

# Install with external secrets
helm install lightrag ./helm/lightrag -n pp \
  --set secrets.redisPassword=$REDIS_PASSWORD \
  --set secrets.llmApiKey=$LLM_API_KEY \
  --set secrets.embeddingApiKey=$EMBEDDING_API_KEY
```

## Configuration

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.registry` | Docker registry | `artifactory.warta.pl` |
| `image.repository` | Image repository | `github-docker/piotrpawluk/lightrag` |
| `image.digest` | Image digest (recommended) | `sha256:2b57d091...` |
| `image.tag` | Image tag (if not using digest) | `""` |
| `image.pullPolicy` | Pull policy | `IfNotPresent` |
| `image.platform` | Platform | `linux/amd64` |

### Deployment Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `resources.requests.memory` | Memory request | `2Gi` |
| `resources.requests.cpu` | CPU request | `1000m` |
| `resources.limits.memory` | Memory limit | `4Gi` |
| `resources.limits.cpu` | CPU limit | `2000m` |

### Service Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `9621` |

### Route Configuration (OKD)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `route.enabled` | Enable OKD route | `true` |
| `route.host` | Route hostname | `""` (auto-generated) |
| `route.tls.termination` | TLS termination | `edge` |

### Application Configuration

See `values.yaml` for complete configuration options including:
- Server settings (workers, log level, workspace)
- LLM configuration (Qwen3-Next-80B)
- Embedding configuration (Qwen3-Embedding-8B, 4096 dims)
- Redis connection settings
- Storage backend selection
- HNSW index parameters
- Query mode defaults

## Upgrading

```bash
# Upgrade to new version
helm upgrade lightrag ./helm/lightrag -n pp

# Upgrade with new values
helm upgrade lightrag ./helm/lightrag -n pp -f values-prod.yaml

# Upgrade specific image
helm upgrade lightrag ./helm/lightrag -n pp \
  --set image.digest=sha256:NEW_DIGEST
```

## Rollback

```bash
# List release history
helm history lightrag -n pp

# Rollback to previous version
helm rollback lightrag -n pp

# Rollback to specific revision
helm rollback lightrag 2 -n pp
```

## Uninstallation

```bash
helm uninstall lightrag -n pp
```

## Storage Architecture

**All storage in Redis (no PVC needed):**

- **KV Storage** (DB 0): Documents, text chunks, LLM cache
- **DocStatus** (DB 1): Document processing status
- **Vector Storage** (DB 2): 4096-dim embeddings with HNSW indexing
- **Graph Storage** (NEW): Entity-relationship knowledge graph

**External Redis:**
- Host: `ml-redisearch-vector-db-node5.shared-dev.svc.cluster.local`
- Port: 80
- Authentication: Username + password (from secrets)

## Scaling

### Horizontal Scaling

With RedisGraphStorage, you can scale horizontally:

```bash
helm upgrade lightrag ./helm/lightrag -n pp \
  --set replicaCount=3
```

All replicas share the same Redis backend, so no data conflicts.

### Vertical Scaling

```bash
helm upgrade lightrag ./helm/lightrag -n pp \
  --set resources.requests.memory=4Gi \
  --set resources.requests.cpu=2000m \
  --set config.server.workers=8
```

## Monitoring

### Logs

```bash
# Stream logs
oc logs -f deployment/$(helm list -n pp -o json | jq -r '.[0].name')-lightrag -n pp

# Last 100 lines
oc logs deployment/lightrag -n pp --tail=100
```

### Metrics

```bash
# Pod metrics
oc adm top pods -n pp

# Get pod status
helm status lightrag -n pp
```

## Troubleshooting

### Chart Validation

```bash
# Lint the chart
helm lint ./helm/lightrag

# Dry run
helm install lightrag ./helm/lightrag -n pp --dry-run --debug

# Render templates
helm template lightrag ./helm/lightrag -n pp
```

### Common Issues

**Pod not starting:**
```bash
# Check pod events
oc describe pod -l app.kubernetes.io/name=lightrag -n pp

# Check logs
oc logs -l app.kubernetes.io/name=lightrag -n pp
```

**Cannot connect to Redis:**
```bash
# Test from pod
oc exec deployment/lightrag -n pp -- \
  redis-cli -h $REDIS_HOST -p $REDIS_PORT \
  -a $REDIS_PASSWORD --user $REDIS_USERNAME ping
```

## Development

### Local Testing

```bash
# Render templates locally
helm template lightrag ./helm/lightrag

# Validate against Kubernetes API
helm install lightrag ./helm/lightrag -n pp --dry-run --debug
```

### Packaging

```bash
# Package the chart
helm package ./helm/lightrag

# Creates: lightrag-1.0.0.tgz
```

## Support

- LightRAG: https://github.com/HKUDS/LightRAG
- Docker Image: ghcr.io/piotrpawluk/lightrag:latest
- Issues: https://github.com/HKUDS/LightRAG/issues

## License

MIT License - See LightRAG repository for details
