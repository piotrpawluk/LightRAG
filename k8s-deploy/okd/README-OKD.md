# LightRAG Deployment on OKD (OpenShift)

Complete guide for deploying LightRAG with Redis Stack storage and external Qwen3 APIs on OpenShift Kubernetes Distribution (OKD).

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              LightRAG on OKD                        │
├─────────────────────────────────────────────────────┤
│  Namespace: lightrag-prod                           │
│                                                      │
│  ┌────────────────┐  ┌─────────────────────────┐   │
│  │  Deployment    │  │  PersistentVolumeClaim  │   │
│  │  (1 replica)   │  │  10Gi (NetworkX data)   │   │
│  └────────────────┘  └─────────────────────────┘   │
│  ┌────────────────┐  ┌─────────────────────────┐   │
│  │  Service       │  │  Route (HTTPS)          │   │
│  │  ClusterIP     │  │  External Access        │   │
│  └────────────────┘  └─────────────────────────┘   │
│                                                      │
│  External Dependencies:                             │
│  - Redis: shared-dev namespace                      │
│  - LLM API: ml-llm-v-srv-v45-cp1-tst-node1         │
│  - Embedding API: ml-ssm-l-srv-v16-cp2-tst-node5   │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

1. **OpenShift CLI (oc)**
   ```bash
   # Verify installation
   oc version
   ```

2. **Cluster Access**
   ```bash
   # Login to OKD cluster
   oc login https://your-okd-cluster.com
   ```

3. **Permissions**
   - Create namespace
   - Create/manage secrets
   - Create deployments, services, routes
   - Create persistent volume claims

## Quick Start

```bash
# 1. Navigate to manifests directory
cd k8s-deploy/okd

# 2. Apply all manifests (using kustomize)
oc apply -k .

# 3. Wait for deployment
oc get pods -n lightrag-prod -w

# 4. Get route URL
oc get route lightrag -n lightrag-prod

# 5. Test health
curl https://$(oc get route lightrag -n lightrag-prod -o jsonpath='{.spec.host}')/health
```

## Step-by-Step Deployment

### Step 1: Create Namespace

```bash
oc apply -f namespace.yaml
```

Verify:
```bash
oc get namespace lightrag-prod
```

### Step 2: Create Secrets

⚠️ **Important**: Review and update `secret.yaml` with your actual credentials before applying!

```bash
oc apply -f secret.yaml
```

Verify:
```bash
oc get secret lightrag-secrets -n lightrag-prod
```

### Step 3: Create ConfigMap

```bash
oc apply -f configmap.yaml
```

Verify:
```bash
oc get configmap lightrag-config -n lightrag-prod
oc describe configmap lightrag-config -n lightrag-prod
```

### Step 4: Create PersistentVolumeClaim

```bash
oc apply -f pvc.yaml
```

Verify:
```bash
oc get pvc -n lightrag-prod
# Wait for STATUS: Bound
```

### Step 5: Deploy LightRAG

```bash
oc apply -f deployment.yaml
```

Monitor deployment:
```bash
# Watch pod status
oc get pods -n lightrag-prod -w

# View logs
oc logs -f deployment/lightrag -n lightrag-prod
```

### Step 6: Create Service

```bash
oc apply -f service.yaml
```

Verify:
```bash
oc get service lightrag -n lightrag-prod
```

### Step 7: Create Route

```bash
oc apply -f route.yaml
```

Get external URL:
```bash
oc get route lightrag -n lightrag-prod
# Note the HOST column for external access
```

## Configuration

### Environment Variables

All configuration is managed through **ConfigMap** (non-sensitive) and **Secret** (sensitive):

**ConfigMap** (`configmap.yaml`):
- Server settings (HOST, PORT, WORKERS)
- LLM/Embedding endpoints and models
- Redis connection details
- Storage configuration
- HNSW parameters

**Secret** (`secret.yaml`):
- Redis password
- LLM API key
- Embedding API key

### Updating Configuration

**Update ConfigMap:**
```bash
# Edit configmap
oc edit configmap lightrag-config -n lightrag-prod

# Or update from file
oc apply -f configmap.yaml

# Restart deployment to pick up changes
oc rollout restart deployment/lightrag -n lightrag-prod
```

**Update Secret:**
```bash
# Edit secret
oc edit secret lightrag-secrets -n lightrag-prod

# Or update from file
oc apply -f secret.yaml

# Restart deployment
oc rollout restart deployment/lightrag -n lightrag-prod
```

## Accessing the Application

### Internal Access (from within cluster)

```bash
# HTTP service URL
http://lightrag.lightrag-prod.svc.cluster.local:9621

# Test from another pod
oc run test-pod --image=curlimages/curl -it --rm -- \
  curl http://lightrag.lightrag-prod.svc.cluster.local:9621/health
```

### External Access (via Route)

```bash
# Get route URL
ROUTE_URL=$(oc get route lightrag -n lightrag-prod -o jsonpath='{.spec.host}')
echo "LightRAG URL: https://$ROUTE_URL"

# Test health endpoint
curl https://$ROUTE_URL/health

# Insert document
curl -X POST https://$ROUTE_URL/insert \
  -H 'Content-Type: application/json' \
  -d '{"text": "Your document text"}'

# Query
curl -X POST https://$ROUTE_URL/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Your question", "mode": "hybrid"}'
```

## Scaling

### Vertical Scaling (Resources)

Edit `deployment.yaml` and adjust:
```yaml
resources:
  requests:
    memory: "4Gi"   # Increase from 2Gi
    cpu: "2000m"    # Increase from 1000m
  limits:
    memory: "8Gi"   # Increase from 4Gi
    cpu: "4000m"    # Increase from 2000m
```

Apply changes:
```bash
oc apply -f deployment.yaml
```

### Horizontal Scaling (Replicas)

⚠️ **Note**: NetworkX graph storage is file-based and not multi-pod safe. For horizontal scaling:

**Option 1**: Use ReadWriteMany PVC
```yaml
# pvc.yaml
spec:
  accessModes:
    - ReadWriteMany  # Changed from ReadWriteOnce
```

**Option 2**: Switch to Redis for graph storage
```yaml
# configmap.yaml
data:
  LIGHTRAG_GRAPH_STORAGE: "RedisGraphStorage"  # If supported
  # Or use Neo4j, Memgraph
```

Then scale:
```bash
oc scale deployment/lightrag --replicas=3 -n lightrag-prod
```

## Monitoring

### Pod Status

```bash
# List pods
oc get pods -n lightrag-prod

# Describe pod
oc describe pod <pod-name> -n lightrag-prod

# Watch pods
oc get pods -n lightrag-prod -w
```

### Logs

```bash
# Tail logs
oc logs -f deployment/lightrag -n lightrag-prod

# Last 100 lines
oc logs deployment/lightrag -n lightrag-prod --tail=100

# Previous pod (if crashed)
oc logs deployment/lightrag -n lightrag-prod --previous

# All pods
oc logs -l app=lightrag -n lightrag-prod
```

### Resource Usage

```bash
# Pod metrics
oc adm top pods -n lightrag-prod

# Node metrics
oc adm top nodes
```

### Events

```bash
# Recent events
oc get events -n lightrag-prod --sort-by='.lastTimestamp'

# Watch events
oc get events -n lightrag-prod -w

# Filter warnings
oc get events -n lightrag-prod --field-selector type=Warning
```

## Troubleshooting

### Pod Not Starting

**Check pod status:**
```bash
oc get pods -n lightrag-prod
oc describe pod <pod-name> -n lightrag-prod
```

**Common issues:**
- ImagePullBackOff: Check image digest and Artifactory access
- CrashLoopBackOff: Check logs for errors
- Pending: Check PVC binding and resource quotas

### Cannot Connect to Redis

**Test from pod:**
```bash
oc exec -it deployment/lightrag -n lightrag-prod -- sh
# Inside pod:
redis-cli -h ml-redisearch-vector-db-node5.shared-dev.svc.cluster.local \
  -p 80 -a U6q7jeA9leOIwYMhAwZkPWRHw4SDmTGBMZXJXcsHlHW7oQUY \
  --user user2 ping
```

**Check network connectivity:**
```bash
oc exec deployment/lightrag -n lightrag-prod -- \
  curl -v telnet://ml-redisearch-vector-db-node5.shared-dev.svc.cluster.local:80
```

### Cannot Reach External APIs

**Test LLM API:**
```bash
oc exec deployment/lightrag -n lightrag-prod -- \
  curl -I https://ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl/v1
```

**Test Embedding API:**
```bash
oc exec deployment/lightrag -n lightrag-prod -- \
  curl -I https://ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl/v1
```

**Check DNS:**
```bash
oc exec deployment/lightrag -n lightrag-prod -- \
  nslookup ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl
```

### PVC Not Binding

```bash
# Check PVC status
oc get pvc lightrag-data -n lightrag-prod

# Check available storage classes
oc get storageclass

# Describe PVC for events
oc describe pvc lightrag-data -n lightrag-prod
```

**Fix**: Update `pvc.yaml` with correct `storageClassName`

### Module Import Errors

If you see `ModuleNotFoundError` for redis modules:
- Ensure you're using the latest image digest
- Pull fresh image from GHCR (not cached Artifactory version)
- Verify image tag in deployment.yaml

## Backup and Restore

### Backup NetworkX Graph Data

```bash
# Create backup job
oc run backup --image=busybox --rm -it -- sh -c \
  "tar czf - /app/data" > lightrag-backup-$(date +%Y%m%d).tar.gz \
  --overrides='{"spec":{"containers":[{"name":"backup","image":"busybox","volumeMounts":[{"name":"data","mountPath":"/app/data"}]}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"lightrag-data"}}]}}'
```

### Restore from Backup

```bash
# Create restore job
cat lightrag-backup-YYYYMMDD.tar.gz | \
  oc run restore --image=busybox --rm -it -- sh -c \
  "tar xzf - -C /" \
  --overrides='{"spec":{"containers":[{"name":"restore","image":"busybox","volumeMounts":[{"name":"data","mountPath":"/app/data"}]}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"lightrag-data"}}]}}'
```

## Updating the Application

### Rolling Update

```bash
# Update image digest in deployment.yaml
# Then apply:
oc apply -f deployment.yaml

# Monitor rollout
oc rollout status deployment/lightrag -n lightrag-prod

# View rollout history
oc rollout history deployment/lightrag -n lightrag-prod
```

### Rollback

```bash
# Rollback to previous version
oc rollout undo deployment/lightrag -n lightrag-prod

# Rollback to specific revision
oc rollout undo deployment/lightrag --to-revision=2 -n lightrag-prod
```

## Security Best Practices

1. **Secrets Management**
   - Never commit `secret.yaml` to git
   - Use External Secrets Operator for production
   - Rotate credentials regularly

2. **Network Policies**
   - Restrict ingress to specific namespaces
   - Limit egress to required endpoints only

3. **Resource Limits**
   - Always set resource requests and limits
   - Prevent resource exhaustion

4. **RBAC**
   - Use least privilege principle
   - Create service accounts with minimal permissions

5. **Image Security**
   - Use digest (not tag) for image references
   - Scan images for vulnerabilities
   - Use private registry (Artifactory)

## Cleanup

```bash
# Delete all resources
oc delete -k k8s-deploy/okd/

# Or delete namespace (removes everything)
oc delete namespace lightrag-prod
```

## Advanced Configuration

### Custom Storage Class

```yaml
# pvc.yaml
spec:
  storageClassName: fast-ssd  # Your storage class
```

### Enable Prometheus Metrics

Add annotations to deployment:
```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9621"
    prometheus.io/path: "/metrics"
```

### Add Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: lightrag-hpa
  namespace: lightrag-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: lightrag
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Support

For issues or questions:
- Check logs: `oc logs -f deployment/lightrag -n lightrag-prod`
- Check events: `oc get events -n lightrag-prod`
- LightRAG GitHub: https://github.com/HKUDS/LightRAG

## License

This deployment configuration is part of the LightRAG project (MIT License).
