# Custom Prompts Configuration

LightRAG supports loading custom prompts from an external JSON file, enabling ConfigMap-based configuration in Kubernetes/OKD deployments.

## Quick Start

1. Set the environment variable pointing to your prompts file:
   ```bash
   export LIGHTRAG_PROMPTS_FILE=/path/to/prompts.json
   ```

2. Start LightRAG as usual - custom prompts will be loaded automatically.

## Configuration Methods

### Local Development

```bash
# Use the included Polish prompts
export LIGHTRAG_PROMPTS_FILE=docs/prompts.json
lightrag-server
```

### Docker

```bash
docker run -v /path/to/prompts.json:/app/prompts.json \
  -e LIGHTRAG_PROMPTS_FILE=/app/prompts.json \
  lightrag-server
```

### Kubernetes/OKD ConfigMap

1. Create a ConfigMap from the prompts file:
   ```bash
   kubectl create configmap lightrag-prompts --from-file=prompts.json=docs/prompts.json
   ```

2. Mount the ConfigMap in your deployment:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: lightrag
   spec:
     template:
       spec:
         containers:
           - name: lightrag
             env:
               - name: LIGHTRAG_PROMPTS_FILE
                 value: /config/prompts.json
             volumeMounts:
               - name: prompts-config
                 mountPath: /config
                 readOnly: true
         volumes:
           - name: prompts-config
             configMap:
               name: lightrag-prompts
   ```

### Helm Chart

Add to your `values.yaml`:
```yaml
prompts:
  enabled: true
  configMapName: lightrag-prompts
  mountPath: /config/prompts.json
```

## JSON File Format

```json
{
  "_meta": {
    "version": "1.0",
    "language": "Polish",
    "description": "Optional metadata (ignored by loader)"
  },
  "DEFAULT_TUPLE_DELIMITER": "<|#|>",
  "DEFAULT_COMPLETION_DELIMITER": "<|COMPLETE|>",
  "entity_extraction_system_prompt": "...",
  "entity_extraction_user_prompt": "...",
  "rag_response": "...",
  ...
}
```

### Available Prompt Keys

| Key | Type | Description |
|-----|------|-------------|
| `DEFAULT_TUPLE_DELIMITER` | string | Delimiter between tuple fields |
| `DEFAULT_COMPLETION_DELIMITER` | string | Marks extraction completion |
| `language_enforcement_prefix` | string | Prefix for language enforcement |
| `language_enforcement_suffix` | string | Suffix for language enforcement |
| `entity_extraction_system_prompt` | string | System prompt for entity extraction |
| `entity_extraction_user_prompt` | string | User prompt for entity extraction |
| `entity_continue_extraction_user_prompt` | string | Continue extraction prompt |
| `entity_extraction_examples` | list | Few-shot examples for extraction |
| `summarize_entity_descriptions` | string | Entity summarization prompt |
| `fail_response` | string | Default failure response |
| `rag_response` | string | RAG response generation prompt |
| `naive_rag_response` | string | Naive RAG response prompt |
| `kg_query_context` | string | Knowledge graph context template |
| `naive_query_context` | string | Naive query context template |
| `keywords_extraction` | string | Keywords extraction prompt |
| `keywords_extraction_examples` | list | Few-shot examples for keywords |
| `default_entity_types_pl` | list | Default entity types (Polish) |

## Partial Overrides

You don't need to include all keys. Only specified keys are replaced:

```json
{
  "_meta": {"description": "Only override the fail response"},
  "fail_response": "Sorry, I cannot answer this question."
}
```

## Generating prompts.json

To export current prompts to JSON:

```bash
source .venv/bin/activate
python3 -c "
import json
from lightrag.prompt import PROMPTS

output = {
    '_meta': {
        'version': '1.0',
        'language': 'Polish',
        'generated_from': 'lightrag/prompt.py',
        'description': 'LightRAG prompt templates'
    }
}
output.update(PROMPTS)
print(json.dumps(output, ensure_ascii=False, indent=2))
" > docs/prompts.json
```

## Validation

Verify your prompts file is valid:

```bash
# Check JSON syntax
python -c "import json; json.load(open('docs/prompts.json')); print('Valid JSON')"

# Test with loader
LIGHTRAG_PROMPTS_FILE=docs/prompts.json python -c "
from lightrag.prompt import PROMPTS
print(f'Loaded {len(PROMPTS)} prompts')
"
```

## Troubleshooting

### File not found warning
```
WARNING: Prompts file not found: /path/to/prompts.json, using defaults
```
Ensure the file path is correct and accessible.

### Type mismatch warning
```
WARNING: Type mismatch for 'entity_extraction_examples': expected list, got str
```
Check that list-type keys (`entity_extraction_examples`, `keywords_extraction_examples`, `default_entity_types_pl`) contain arrays, not strings.

### Unknown key warning
```
WARNING: Unknown prompt key: my_custom_key
```
Only built-in prompt keys are supported. Custom keys are ignored.
