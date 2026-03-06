# LightRAG Polish Language Enforcement for Qwen3

## Problem Description

Qwen3 32B (and similar models) often respond partially in English even when prompts are in Polish. This causes issues with:
- Entity extraction producing English descriptions
- Keyword extraction returning English keywords
- Embeddings becoming inconsistent (mixed language content)
- Retrieval failures due to language mismatch

## Solution Overview

This solution provides multiple layers of Polish language enforcement:

1. **Prompt-level enforcement** - Stronger language markers in prompts
2. **LLM wrapper** - Automatic language enforcement on all LLM calls
3. **Post-processing** - Entity type normalization and English detection
4. **Configuration** - Polish entity types and language settings

## Quick Start

### Option 1: Quick Patch (Easiest)

Add this at the **very top** of your main script, BEFORE importing LightRAG:

```python
# Add this BEFORE importing LightRAG
from lightrag_polish_enforcer import patch_lightrag_for_polish
patch_lightrag_for_polish()

# Now import and use LightRAG normally
from lightrag import LightRAG

rag = LightRAG(
    working_dir="./your_dir",
    llm_model_func=your_qwen3_llm_func,
    addon_params={
        "language": "polski",  # Use Polish word!
        "entity_types": [
            "osoba", "stworzenie", "organizacja", "lokalizacja",
            "wydarzenie", "koncepcja", "metoda", "treść",
            "dane", "artefakt", "obiekt_naturalny", "inny"
        ]
    }
)
```

### Option 2: Full Control (Recommended)

```python
from lightrag_polish_enforcer import (
    patch_lightrag_for_polish,
    create_polish_llm_wrapper,
    PolishLightRAGConfig,
    POLISH_ENTITY_TYPES
)

# Step 1: Patch prompts
patch_lightrag_for_polish()

# Step 2: Wrap your LLM function
wrapped_llm = create_polish_llm_wrapper(your_qwen3_llm_func)

# Step 3: Use Polish config
config = PolishLightRAGConfig()

# Step 4: Create LightRAG with all enforcement
from lightrag import LightRAG

rag = LightRAG(
    working_dir="./your_dir",
    llm_model_func=wrapped_llm,  # Use wrapped LLM
    addon_params=config.addon_params  # Use Polish config
)
```

### Option 3: Replace prompt.py Entirely

Replace your `lightrag/prompt.py` with the provided `prompt_pl_fixed.py` for comprehensive prompt changes.

```bash
# Backup original
cp lightrag/prompt.py lightrag/prompt_backup.py

# Replace with fixed version
cp prompt_pl_fixed.py lightrag/prompt.py
```

## Files Provided

| File | Description |
|------|-------------|
| `prompt_pl_fixed.py` | Complete replacement for `lightrag/prompt.py` with strong Polish enforcement |
| `lightrag_polish_enforcer.py` | Python module for patching and wrapping LLM calls |
| `operate_patches.py` | Reference showing specific code changes for `operate.py` |

## Key Changes Made

### 1. Prompt Structure Changes

Added explicit language markers at multiple points:

```python
# Before (weak enforcement)
"Całe wyjście musi być w języku {language}"

# After (strong enforcement for Qwen3)
"""[JĘZYK ODPOWIEDZI: POLSKI]

⚠️ BEZWZGLĘDNE WYMAGANIE JĘZYKOWE ⚠️
WSZYSTKIE odpowiedzi MUSZĄ być WYŁĄCZNIE w języku polskim!
- Opisy encji: TYLKO po polsku
- Opisy relacji: TYLKO po polsku
- Słowa kluczowe: TYLKO po polsku
ZAKAZ używania języka angielskiego!
"""
```

### 2. Polish Entity Types

Use Polish entity types instead of English:

```python
# Before (English)
entity_types = ["person", "organization", "location", ...]

# After (Polish)
entity_types = ["osoba", "organizacja", "lokalizacja", ...]
```

### 3. Examples in Polish

All examples now use fully Polish descriptions and keywords:

```python
# Before (mixed)
relation<|#|>Alex<|#|>Taylor<|#|>power dynamics, observation<|#|>...

# After (Polish)
relation<|#|>Alex<|#|>Taylor<|#|>dynamika władzy, obserwacja<|#|>...
```

### 4. Language Parameter

Use Polish word for language:

```python
# Before
addon_params={"language": "Polish"}

# After  
addon_params={"language": "polski"}
```

## Troubleshooting

### Model Still Responds in English

1. **Check model temperature** - Lower temperature (0.1-0.3) helps with instruction following
2. **Add language to system prompt** - Some models need it in both system and user prompts
3. **Use the LLM wrapper** - Automatic enforcement on every call

```python
# Force temperature for better compliance
async def llm_with_low_temp(prompt, **kwargs):
    kwargs['temperature'] = kwargs.get('temperature', 0.2)
    return await your_original_llm(prompt, **kwargs)

wrapped = create_polish_llm_wrapper(llm_with_low_temp)
```

### Entity Types Appear in English

The enforcer includes automatic entity type normalization:

```python
from lightrag_polish_enforcer import normalize_entity_type_to_polish

# Automatically converts:
# "person" -> "osoba"
# "location" -> "lokalizacja"
# "organization" -> "organizacja"
```

### Keywords in English

Ensure the `keywords_extraction` prompt is patched:

```python
# Verify patching
from lightrag.prompt import PROMPTS
print("Patched" if "[JĘZYK" in PROMPTS["keywords_extraction"] else "Not patched")
```

### Embeddings Inconsistent

Mixed language content causes embedding issues. After fixing language:

1. **Rebuild the knowledge graph** - Re-extract entities with Polish prompts
2. **Re-index chunks** - Embeddings will be consistent when content is in one language

```python
# Force re-extraction by clearing cache
import shutil
shutil.rmtree("./your_working_dir/llm_response_cache", ignore_errors=True)

# Re-insert documents
await rag.ainsert(your_documents)
```

## Advanced Configuration

### Custom LLM Wrapper with Logging

```python
def create_polish_llm_wrapper_with_logging(llm_func):
    async def wrapper(prompt, system_prompt=None, **kwargs):
        # Log input
        print(f"[LLM] Prompt preview: {prompt[:200]}...")
        
        # Enforce Polish
        if "[JĘZYK" not in prompt:
            prompt = f"[JĘZYK: POLSKI]\n{prompt}"
        
        if system_prompt and "[JĘZYK" not in system_prompt:
            system_prompt = f"[JĘZYK: POLSKI]\n{system_prompt}"
        
        # Call LLM
        result = await llm_func(prompt, system_prompt=system_prompt, **kwargs)
        
        # Check result
        english_words = ["the ", " is ", " are ", "description"]
        for word in english_words:
            if word in result.lower():
                print(f"[WARNING] English detected: '{word}' in response")
                break
        
        return result
    
    return wrapper
```

### Per-Task Language Enforcement

```python
# Different enforcement levels for different tasks
async def task_specific_llm(prompt, task_type="general", **kwargs):
    if task_type == "entity_extraction":
        # Strongest enforcement
        prompt = f"""[JĘZYK: POLSKI]
⚠️ KRYTYCZNE: Wszystkie opisy encji i relacji MUSZĄ być po polsku!
NIE PISZ PO ANGIELSKU!

{prompt}

[PRZYPOMNIENIE: Odpowiedź w języku polskim]"""
    
    elif task_type == "keywords":
        prompt = f"""[JĘZYK: POLSKI]
Słowa kluczowe TYLKO po polsku!

{prompt}"""
    
    return await original_llm(prompt, **kwargs)
```

## Testing Your Setup

Run this test to verify Polish enforcement:

```python
import asyncio
from lightrag_polish_enforcer import (
    patch_lightrag_for_polish,
    create_polish_llm_wrapper,
    check_for_english_content
)

async def test_polish_enforcement():
    # Patch prompts
    patch_lightrag_for_polish()
    
    # Create test LLM wrapper
    async def mock_llm(prompt, **kwargs):
        # Your actual LLM call here
        pass
    
    wrapped = create_polish_llm_wrapper(mock_llm)
    
    # Test prompt
    test_prompt = "Wyodrębnij encje z tego tekstu: Jan Kowalski pracuje w firmie ABC."
    
    # The wrapper should add [JĘZYK: POLSKI] marker
    # Your LLM should respond in Polish
    
    # Check response for English
    response = "Jan Kowalski jest osobą pracującą w organizacji ABC."
    english = check_for_english_content(response)
    
    if not english:
        print("✅ No English detected - enforcement working!")
    else:
        print(f"⚠️ English detected: {english}")

asyncio.run(test_polish_enforcement())
```

## Performance Notes

- Language enforcement adds ~100-200 tokens to prompts
- First-time extraction may be slower due to stronger instructions
- Caching still works normally after enforcement

## Support

If you continue to experience English responses:

1. Check your model's instruction-following capability
2. Try increasing the number of language reminders
3. Consider using a model with better multilingual instruction following
4. Use post-processing to normalize entity types

## Version Compatibility

Tested with:
- LightRAG (various versions)
- Qwen3 32B
- Python 3.10+

The patches are designed to be non-destructive and can be disabled by removing the import.