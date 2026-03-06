"""Test that keywords_extraction_examples have properly escaped curly braces."""
import pytest
from lightrag.prompt import PROMPTS


def test_keywords_extraction_examples_format():
    """
    Verify that PROMPTS["keywords_extraction_examples"] can be safely
    passed to str.format() without raising KeyError.

    This tests the fix for the bug where unescaped { and } in JSON examples
    were interpreted as format placeholders.
    """
    # Simulate what operate.py does at line 3319
    examples = "\n".join(PROMPTS["keywords_extraction_examples"])

    # This should NOT raise KeyError: '\n "high_level_keywords"'
    # Simulate what operate.py does at line 3347
    result = PROMPTS["keywords_extraction"].format(
        query="Klient posiada tartak, jakie ubezpieczenie?",
        examples=examples,
        language="Polish",
    )

    # Verify the result contains expected content
    assert "high_level_keywords" in result
    assert "low_level_keywords" in result
    assert "tartak" in result  # From the test query

    # Verify JSON examples are present with proper braces (not doubled)
    assert '"high_level_keywords":' in result or '"high_level_keywords": [' in result


def test_examples_contain_all_four_examples():
    """Verify all 4 examples are present."""
    examples = "\n".join(PROMPTS["keywords_extraction_examples"])

    assert "Przykład 1:" in examples
    assert "Przykład 2:" in examples
    assert "Przykład 3:" in examples
    assert "Przykład 4:" in examples
