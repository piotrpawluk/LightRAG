"""
LightRAG Polish Language Enforcement Patches for Qwen3

This file contains the necessary code modifications to ensure Qwen3
responds consistently in Polish during entity extraction, summarization,
and keyword extraction.

Apply these changes to your operate.py file.
"""


# ============================================================================
# SECTION 1: Add these helper functions near the top of operate.py
# ============================================================================

def enforce_polish_language(prompt: str, is_system_prompt: bool = False) -> str:
    """
    Wrap prompts with Polish language enforcement markers for Qwen3.

    Qwen3 responds better when language requirements are:
    1. At the very beginning of the prompt
    2. Repeated before output sections
    3. Using explicit markers like [JĘZYK: POLSKI]
    """
    prefix = "[JĘZYK: POLSKI]\n"

    if is_system_prompt:
        # For system prompts, add stronger enforcement
        prefix = """[JĘZYK ODPOWIEDZI: POLSKI]
⚠️ KRYTYCZNE: Wszystkie odpowiedzi MUSZĄ być w języku polskim!
NIE UŻYWAJ języka angielskiego w opisach, słowach kluczowych ani typach!

"""

    # Check if prompt already has language enforcement
    if "[JĘZYK" in prompt or "JĘZYK:" in prompt:
        return prompt

    return prefix + prompt


def post_process_polish_response(response: str, expected_language: str = "polski") -> str:
    """
    Post-process LLM response to detect and log language issues.
    This helps with debugging but doesn't fix the response.

    For actual fixing, you would need a translation step or re-prompting.
    """
    # Common English words that shouldn't appear in Polish output
    english_indicators = [
        " the ", " is ", " are ", " was ", " were ", " has ", " have ",
        " this ", " that ", " with ", " from ", " for ", " and ", " or ",
        "description", "relationship", "entity", "location", "person",
        "organization", "event", "concept", "method", "data", "artifact"
    ]

    response_lower = response.lower()
    detected_english = []

    for indicator in english_indicators:
        if indicator in response_lower:
            detected_english.append(indicator.strip())

    if detected_english:
        from lightrag.utils import logger
        logger.warning(
            f"Potential English detected in response (expected {expected_language}): "
            f"{detected_english[:5]}..."  # Log first 5 indicators
        )

    return response


# ============================================================================
# SECTION 2: Modify the _summarize_descriptions function
# Add language enforcement wrapper around the LLM call
# ============================================================================

# Find this function in operate.py and modify it:

async def _summarize_descriptions_MODIFIED(
        description_type: str,
        description_name: str,
        description_list: list[str],
        global_config: dict,
        llm_response_cache=None,
) -> str:
    """
    MODIFIED VERSION: Added Polish language enforcement for Qwen3
    """
    from functools import partial
    from lightrag.prompt import PROMPTS
    from lightrag.constants import DEFAULT_SUMMARY_LANGUAGE
    from lightrag.utils import (
        truncate_list_by_token_size,
        use_llm_func_with_cache,
    )
    import json

    use_llm_func = global_config["llm_model_func"]
    use_llm_func = partial(use_llm_func, _priority=8)

    language = global_config["addon_params"].get("language", DEFAULT_SUMMARY_LANGUAGE)
    summary_length_recommended = global_config["summary_length_recommended"]

    prompt_template = PROMPTS["summarize_entity_descriptions"]

    tokenizer = global_config["tokenizer"]
    summary_context_size = global_config["summary_context_size"]

    json_descriptions = [{"Description": desc} for desc in description_list]

    truncated_json_descriptions = truncate_list_by_token_size(
        json_descriptions,
        key=lambda x: json.dumps(x, ensure_ascii=False),
        max_token_size=summary_context_size,
        tokenizer=tokenizer,
    )

    joined_descriptions = "\n".join(
        json.dumps(desc, ensure_ascii=False) for desc in truncated_json_descriptions
    )

    context_base = dict(
        description_type=description_type,
        description_name=description_name,
        description_list=joined_descriptions,
        summary_length=summary_length_recommended,
        language=language,
    )

    use_prompt = prompt_template.format(**context_base)

    # ========== ADD THIS: Language enforcement for Qwen3 ==========
    use_prompt = enforce_polish_language(use_prompt)
    # ==============================================================

    summary, _ = await use_llm_func_with_cache(
        use_prompt,
        use_llm_func,
        llm_response_cache=llm_response_cache,
        cache_type="summary",
    )

    # ========== ADD THIS: Post-process check ==========
    summary = post_process_polish_response(summary, language)
    # ==================================================

    # ... rest of the function remains the same
    return summary


# ============================================================================
# SECTION 3: Modify the _process_single_content function inside extract_entities
# Add language enforcement to entity extraction prompts
# ============================================================================

# Inside the extract_entities function, find _process_single_content and modify:

async def _process_single_content_MODIFIED(chunk_key_dp):
    """
    MODIFIED VERSION: Shows where to add Polish language enforcement
    """
    # ... existing code ...

    # After creating the prompts, add enforcement:
    entity_extraction_system_prompt = PROMPTS[
        "entity_extraction_system_prompt"
    ].format(**context_base)

    # ========== ADD THIS: Enforce Polish for system prompt ==========
    entity_extraction_system_prompt = enforce_polish_language(
        entity_extraction_system_prompt,
        is_system_prompt=True
    )
    # ================================================================

    entity_extraction_user_prompt = PROMPTS["entity_extraction_user_prompt"].format(
        **{**context_base, "input_text": content}
    )

    # ========== ADD THIS: Enforce Polish for user prompt ==========
    entity_extraction_user_prompt = enforce_polish_language(entity_extraction_user_prompt)
    # ==============================================================

    # ... rest of the function remains the same


# ============================================================================
# SECTION 4: Modify extract_keywords_only function
# Add language enforcement for keyword extraction
# ============================================================================

async def extract_keywords_only_MODIFIED(
        text: str,
        param,
        global_config: dict[str, str],
        hashing_kv=None,
):
    """
    MODIFIED VERSION: Added Polish language enforcement for Qwen3
    """
    from functools import partial
    from lightrag.prompt import PROMPTS
    from lightrag.constants import DEFAULT_SUMMARY_LANGUAGE
    from lightrag.utils import (
        compute_args_hash,
        handle_cache,
        save_to_cache,
        CacheData,
        remove_think_tags,
    )
    import json
    import json_repair

    examples = "\n".join(PROMPTS["keywords_extraction_examples"])
    language = global_config["addon_params"].get("language", DEFAULT_SUMMARY_LANGUAGE)

    # Handle cache
    normalized_text = " ".join(text.lower().split())
    args_hash = compute_args_hash(
        param.mode,
        normalized_text,
        language,
    )
    cached_result = await handle_cache(
        hashing_kv, args_hash, text, param.mode, cache_type="keywords"
    )
    if cached_result is not None:
        cached_response, _ = cached_result
        try:
            keywords_data = json_repair.loads(cached_response)
            return keywords_data.get("high_level_keywords", []), keywords_data.get(
                "low_level_keywords", []
            )
        except (json.JSONDecodeError, KeyError):
            pass

    kw_prompt = PROMPTS["keywords_extraction"].format(
        query=text,
        examples=examples,
        language=language,
    )

    # ========== ADD THIS: Enforce Polish language ==========
    kw_prompt = enforce_polish_language(kw_prompt)
    # =======================================================

    if param.model_func:
        use_model_func = param.model_func
    else:
        use_model_func = global_config["llm_model_func"]
        use_model_func = partial(use_model_func, _priority=5)

    result = await use_model_func(kw_prompt, keyword_extraction=True)

    result = remove_think_tags(result)

    # ========== ADD THIS: Post-process check ==========
    result = post_process_polish_response(result, language)
    # ==================================================

    try:
        keywords_data = json_repair.loads(result)
        if not keywords_data:
            return [], []
    except json.JSONDecodeError:
        return [], []

    hl_keywords = keywords_data.get("high_level_keywords", [])
    ll_keywords = keywords_data.get("low_level_keywords", [])

    # ... rest of caching logic ...

    return hl_keywords, ll_keywords


# ============================================================================
# SECTION 5: Alternative approach - Wrapper for LLM function
# This can be added to lightrag.py or utils.py to wrap ALL LLM calls
# ============================================================================

def create_polish_enforced_llm_wrapper(original_llm_func, language: str = "polski"):
    """
    Create a wrapper around the LLM function that enforces Polish language.

    Usage in lightrag.py __init__:
        self.llm_model_func = create_polish_enforced_llm_wrapper(
            self.llm_model_func,
            language=self.addon_params.get("language", "polski")
        )
    """
    import asyncio
    from functools import wraps

    @wraps(original_llm_func)
    async def wrapper(prompt, system_prompt=None, **kwargs):
        # Add language enforcement prefix to prompt
        enforced_prompt = f"[JĘZYK: POLSKI]\n{prompt}"

        # If system_prompt is provided, enforce there too
        if system_prompt:
            if "[JĘZYK" not in system_prompt:
                system_prompt = f"""[JĘZYK ODPOWIEDZI: POLSKI]
⚠️ WSZYSTKIE odpowiedzi MUSZĄ być w języku polskim!

{system_prompt}"""

        # Call original function
        result = await original_llm_func(enforced_prompt, system_prompt=system_prompt, **kwargs)

        return result

    return wrapper


# ============================================================================
# SECTION 6: Configuration changes for global_config
# Add these to your LightRAG initialization
# ============================================================================

RECOMMENDED_ADDON_PARAMS_FOR_POLISH = {
    "language": "polski",  # Use "polski" not "Polish" for better compliance
    "entity_types": [
        "osoba",
        "stworzenie",
        "organizacja",
        "lokalizacja",
        "wydarzenie",
        "koncepcja",
        "metoda",
        "treść",
        "dane",
        "artefakt",
        "obiekt_naturalny",
        "inny"
    ],
}

# ============================================================================
# SECTION 7: Quick integration guide
# ============================================================================

"""
QUICK INTEGRATION GUIDE FOR POLISH LANGUAGE ENFORCEMENT:

1. Replace your prompt.py with prompt_pl_fixed.py

2. Add the helper functions (enforce_polish_language, post_process_polish_response)
   to the top of operate.py after imports

3. Modify _summarize_descriptions to wrap prompts with enforce_polish_language()

4. Modify _process_single_content in extract_entities to wrap prompts

5. Modify extract_keywords_only to wrap prompts

6. Update your LightRAG initialization:

   rag = LightRAG(
       working_dir="./your_dir",
       llm_model_func=your_llm_func,
       addon_params={
           "language": "polski",  # Use Polish word for language
           "entity_types": [
               "osoba", "stworzenie", "organizacja", "lokalizacja",
               "wydarzenie", "koncepcja", "metoda", "treść",
               "dane", "artefakt", "obiekt_naturalny", "inny"
           ]
       }
   )

7. (OPTIONAL) For maximum enforcement, use the LLM wrapper:

   from your_patches import create_polish_enforced_llm_wrapper

   enforced_llm = create_polish_enforced_llm_wrapper(your_llm_func, "polski")

   rag = LightRAG(
       llm_model_func=enforced_llm,
       ...
   )
"""