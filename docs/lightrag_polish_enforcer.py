"""
LightRAG Polish Language Enforcement Module for Qwen3

This module provides monkey-patching capabilities to enforce Polish language
responses from Qwen3 models in LightRAG.

USAGE:
======
Add this import at the TOP of your main script, BEFORE importing LightRAG:

    from lightrag_polish_enforcer import patch_lightrag_for_polish
    patch_lightrag_for_polish()

    # Now import and use LightRAG normally
    from lightrag import LightRAG

Or, if you want more control:

    from lightrag_polish_enforcer import (
        enforce_polish_language,
        create_polish_llm_wrapper,
        POLISH_ENTITY_TYPES
    )

"""

import asyncio
import functools
import json
import logging
from typing import Any, Callable

logger = logging.getLogger("lightrag_polish")

# ============================================================================
# POLISH ENTITY TYPES - Use these instead of English types
# ============================================================================

POLISH_ENTITY_TYPES = [
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
]

# Mapping from English to Polish entity types (for normalization)
ENTITY_TYPE_EN_TO_PL = {
    "person": "osoba",
    "creature": "stworzenie",
    "organization": "organizacja",
    "location": "lokalizacja",
    "event": "wydarzenie",
    "concept": "koncepcja",
    "method": "metoda",
    "content": "treść",
    "data": "dane",
    "artifact": "artefakt",
    "natural_object": "obiekt_naturalny",
    "other": "inny",
    # Common variations
    "geo": "lokalizacja",
    "place": "lokalizacja",
    "company": "organizacja",
    "org": "organizacja",
    "human": "osoba",
    "people": "osoba",
    "thing": "artefakt",
    "equipment": "artefakt",
    "tool": "artefakt",
    "category": "koncepcja",
    "product": "artefakt",
    "unknown": "inny",
}


# ============================================================================
# LANGUAGE ENFORCEMENT FUNCTIONS
# ============================================================================

def enforce_polish_language(prompt: str, is_system_prompt: bool = False) -> str:
    """
    Wrap prompts with Polish language enforcement markers for Qwen3.

    Qwen3 responds better when language requirements are:
    1. At the very beginning of the prompt
    2. Repeated before output sections
    3. Using explicit markers like [JĘZYK: POLSKI]

    Args:
        prompt: The original prompt text
        is_system_prompt: Whether this is a system prompt (uses stronger enforcement)

    Returns:
        Modified prompt with Polish language enforcement
    """
    # Check if prompt already has language enforcement
    if "[JĘZYK" in prompt or "JĘZYK:" in prompt or "⚠️ KRYTYCZNE" in prompt:
        return prompt

    if is_system_prompt:
        prefix = """[JĘZYK ODPOWIEDZI: POLSKI]

⚠️ KRYTYCZNE WYMAGANIE JĘZYKOWE ⚠️
WSZYSTKIE odpowiedzi MUSZĄ być WYŁĄCZNIE w języku polskim!
- Opisy encji i relacji: TYLKO po polsku
- Słowa kluczowe: TYLKO po polsku  
- Typy encji: TYLKO po polsku
ZAKAZ używania języka angielskiego!

"""
    else:
        prefix = """[JĘZYK: POLSKI]
WYMAGANIE: Odpowiedź MUSI być w języku polskim!

"""

    return prefix + prompt


def normalize_entity_type_to_polish(entity_type: str) -> str:
    """
    Normalize entity types to Polish.

    Args:
        entity_type: Entity type string (possibly in English)

    Returns:
        Polish entity type
    """
    if not entity_type:
        return "inny"

    normalized = entity_type.lower().strip().replace(" ", "_").replace("-", "_")

    # Check if already in Polish
    if normalized in POLISH_ENTITY_TYPES:
        return normalized

    # Try to map from English
    return ENTITY_TYPE_EN_TO_PL.get(normalized, "inny")


def post_process_extraction_result(result: str) -> str:
    """
    Post-process entity extraction results to fix common English leakage issues.

    This function:
    1. Normalizes entity types to Polish
    2. Logs warnings for detected English content

    Args:
        result: Raw LLM extraction result

    Returns:
        Processed result with normalized entity types
    """
    lines = result.split('\n')
    processed_lines = []

    for line in lines:
        if '<|#|>' in line and line.strip().startswith('entity'):
            parts = line.split('<|#|>')
            if len(parts) >= 3:
                # Normalize entity type (third element)
                original_type = parts[2].strip()
                normalized_type = normalize_entity_type_to_polish(original_type)

                if original_type.lower() != normalized_type:
                    logger.debug(f"Normalized entity type: '{original_type}' -> '{normalized_type}'")

                parts[2] = normalized_type
                line = '<|#|>'.join(parts)

        processed_lines.append(line)

    return '\n'.join(processed_lines)


def check_for_english_content(text: str) -> list[str]:
    """
    Check text for common English words that shouldn't appear in Polish output.

    Returns list of detected English indicators.
    """
    english_indicators = [
        # Common English articles and prepositions
        " the ", " a ", " an ", " is ", " are ", " was ", " were ",
        " has ", " have ", " this ", " that ", " with ", " from ",
        " for ", " and ", " or ", " but ", " not ", " can ", " will ",
        # Common English nouns that might appear in descriptions
        "description", "relationship", "entity", "location", "person",
        "organization", "event", "concept", "method", "data", "artifact",
        "company", "technology", "system", "process", "result", "impact",
        "analysis", "research", "study", "report", "information",
        # Common English verbs
        "represents", "describes", "shows", "indicates", "involves",
        "includes", "contains", "provides", "creates", "manages",
    ]

    text_lower = text.lower()
    detected = []

    for indicator in english_indicators:
        if indicator in text_lower:
            detected.append(indicator.strip())

    return detected


# ============================================================================
# LLM WRAPPER FOR AUTOMATIC LANGUAGE ENFORCEMENT
# ============================================================================

def create_polish_llm_wrapper(
        original_llm_func: Callable,
        language: str = "polski",
        enforce_system_prompt: bool = True,
        log_english_detection: bool = True
) -> Callable:
    """
    Create a wrapper around the LLM function that automatically enforces Polish.

    This wrapper:
    1. Adds Polish language markers to all prompts
    2. Optionally adds enforcement to system prompts
    3. Logs warnings when English is detected in responses

    Args:
        original_llm_func: The original async LLM function
        language: Target language (default: "polski")
        enforce_system_prompt: Whether to modify system prompts
        log_english_detection: Whether to log detected English content

    Returns:
        Wrapped LLM function with Polish enforcement

    Usage:
        enforced_llm = create_polish_llm_wrapper(your_llm_func)
        rag = LightRAG(llm_model_func=enforced_llm, ...)
    """

    @functools.wraps(original_llm_func)
    async def wrapper(prompt: str, system_prompt: str = None, **kwargs):
        # Enforce Polish in the main prompt
        enforced_prompt = enforce_polish_language(prompt, is_system_prompt=False)

        # Optionally enforce in system prompt
        if system_prompt and enforce_system_prompt:
            enforced_system = enforce_polish_language(system_prompt, is_system_prompt=True)
        else:
            enforced_system = system_prompt

        # Call original function
        result = await original_llm_func(
            enforced_prompt,
            system_prompt=enforced_system,
            **kwargs
        )

        # Check for English in response and log warning
        if log_english_detection and isinstance(result, str):
            english_detected = check_for_english_content(result)
            if english_detected:
                logger.warning(
                    f"English content detected in LLM response (expected {language}): "
                    f"{english_detected[:5]}{'...' if len(english_detected) > 5 else ''}"
                )

        return result

    return wrapper


# ============================================================================
# PROMPT PATCHING - Direct modification of PROMPTS dictionary
# ============================================================================

def patch_prompts_for_polish():
    """
    Patch the LightRAG PROMPTS dictionary with Polish-optimized versions.

    This modifies the prompts in-place to add stronger Polish language enforcement.
    Call this BEFORE using LightRAG.
    """
    try:
        from lightrag.prompt import PROMPTS
    except ImportError:
        logger.error("Could not import lightrag.prompt.PROMPTS")
        return False

    # Patch entity extraction system prompt
    original_entity_system = PROMPTS.get("entity_extraction_system_prompt", "")
    if original_entity_system and "[JĘZYK" not in original_entity_system:
        PROMPTS["entity_extraction_system_prompt"] = """[JĘZYK ODPOWIEDZI: POLSKI]

⚠️ BEZWZGLĘDNE WYMAGANIE JĘZYKOWE ⚠️
WSZYSTKIE odpowiedzi MUSZĄ być WYŁĄCZNIE w języku polskim!
- Opisy encji: TYLKO po polsku
- Opisy relacji: TYLKO po polsku
- Słowa kluczowe relacji: TYLKO po polsku
- Typy encji: TYLKO po polsku
ZAKAZ używania języka angielskiego w opisach i słowach kluczowych!

""" + original_entity_system

    # Patch entity extraction user prompt
    original_entity_user = PROMPTS.get("entity_extraction_user_prompt", "")
    if original_entity_user and "[JĘZYK" not in original_entity_user:
        PROMPTS["entity_extraction_user_prompt"] = """[JĘZYK: POLSKI]
⚠️ WYMAGANIE: Wszystkie opisy, typy i słowa kluczowe MUSZĄ być po POLSKU!

""" + original_entity_user

    # Patch continue extraction prompt
    original_continue = PROMPTS.get("entity_continue_extraction_user_prompt", "")
    if original_continue and "[JĘZYK" not in original_continue:
        PROMPTS["entity_continue_extraction_user_prompt"] = """[JĘZYK: POLSKI]
⚠️ WYMAGANIE: Wszystkie opisy, typy i słowa kluczowe MUSZĄ być po POLSKU!

""" + original_continue

    # Patch summarization prompt
    original_summary = PROMPTS.get("summarize_entity_descriptions", "")
    if original_summary and "[JĘZYK" not in original_summary:
        PROMPTS["summarize_entity_descriptions"] = """[JĘZYK: POLSKI]
⚠️ BEZWZGLĘDNE WYMAGANIE: Cała odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

""" + original_summary

    # Patch keywords extraction prompt
    original_keywords = PROMPTS.get("keywords_extraction", "")
    if original_keywords and "[JĘZYK" not in original_keywords:
        PROMPTS["keywords_extraction"] = """[JĘZYK: POLSKI]
⚠️ BEZWZGLĘDNE WYMAGANIE: Wszystkie słowa kluczowe MUSZĄ być w języku polskim! NIE UŻYWAJ ANGIELSKICH SŁÓW KLUCZOWYCH!

""" + original_keywords

    # Patch RAG response prompts
    original_rag = PROMPTS.get("rag_response", "")
    if original_rag and "[JĘZYK" not in original_rag:
        PROMPTS["rag_response"] = """[JĘZYK: POLSKI]
⚠️ WYMAGANIE: Odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

""" + original_rag

    original_naive = PROMPTS.get("naive_rag_response", "")
    if original_naive and "[JĘZYK" not in original_naive:
        PROMPTS["naive_rag_response"] = """[JĘZYK: POLSKI]
⚠️ WYMAGANIE: Odpowiedź MUSI być WYŁĄCZNIE w języku polskim!

""" + original_naive

    logger.info("LightRAG prompts patched for Polish language enforcement")
    return True


# ============================================================================
# MAIN PATCHING FUNCTION
# ============================================================================

def patch_lightrag_for_polish(
        patch_prompts: bool = True,
        wrap_llm: bool = False,
        llm_func_attr: str = "llm_model_func"
):
    """
    Apply all Polish language enforcement patches to LightRAG.

    This function should be called BEFORE creating a LightRAG instance.

    Args:
        patch_prompts: Whether to patch the PROMPTS dictionary
        wrap_llm: Whether to attempt wrapping the LLM function
        llm_func_attr: Attribute name for LLM function in LightRAG

    Usage:
        from lightrag_polish_enforcer import patch_lightrag_for_polish
        patch_lightrag_for_polish()

        from lightrag import LightRAG
        rag = LightRAG(...)
    """
    patches_applied = []

    if patch_prompts:
        if patch_prompts_for_polish():
            patches_applied.append("prompts")

    logger.info(f"Applied Polish language patches: {patches_applied}")
    return patches_applied


# ============================================================================
# HELPER CLASS FOR LIGHTRAG INITIALIZATION
# ============================================================================

class PolishLightRAGConfig:
    """
    Helper class providing recommended configuration for Polish language use.

    Usage:
        config = PolishLightRAGConfig()
        rag = LightRAG(
            addon_params=config.addon_params,
            ...
        )
    """

    def __init__(self):
        self.addon_params = {
            "language": "polski",
            "entity_types": POLISH_ENTITY_TYPES.copy(),
        }

    @staticmethod
    def wrap_llm_function(llm_func: Callable) -> Callable:
        """Wrap an LLM function with Polish enforcement."""
        return create_polish_llm_wrapper(llm_func)

    @staticmethod
    def get_entity_types() -> list[str]:
        """Get the recommended Polish entity types."""
        return POLISH_ENTITY_TYPES.copy()


# ============================================================================
# MODULE-LEVEL INITIALIZATION
# ============================================================================

# Configure logging
logging.basicConfig(level=logging.INFO)


# Print usage instructions when imported
def _print_usage():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║          LightRAG Polish Language Enforcer for Qwen3                 ║
╠══════════════════════════════════════════════════════════════════════╣
║  USAGE:                                                              ║
║                                                                      ║
║  Option 1 - Quick patch (add before LightRAG import):                ║
║    from lightrag_polish_enforcer import patch_lightrag_for_polish    ║
║    patch_lightrag_for_polish()                                       ║
║                                                                      ║
║  Option 2 - Use wrapper and config:                                  ║
║    from lightrag_polish_enforcer import (                            ║
║        create_polish_llm_wrapper,                                    ║
║        PolishLightRAGConfig                                          ║
║    )                                                                 ║
║    config = PolishLightRAGConfig()                                   ║
║    wrapped_llm = create_polish_llm_wrapper(your_llm_func)            ║
║    rag = LightRAG(                                                   ║
║        llm_model_func=wrapped_llm,                                   ║
║        addon_params=config.addon_params                              ║
║    )                                                                 ║
╚══════════════════════════════════════════════════════════════════════╝
""")

# Uncomment to show usage on import:
# _print_usage()