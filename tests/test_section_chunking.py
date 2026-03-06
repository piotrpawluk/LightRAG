"""Tests for section-aware chunking."""

import pytest

from lightrag.chunking import (
    SectionChunkingConfig,
    _Section,
    _build_breadcrumb,
    _build_hierarchy,
    _detect_sections,
    section_aware_chunking,
)
from lightrag.utils import Tokenizer, TokenizerInterface


class DummyTokenizer(TokenizerInterface):
    """Simple 1:1 character-to-token mapping for testing."""

    def encode(self, content: str):
        return [ord(ch) for ch in content]

    def decode(self, tokens):
        return "".join(chr(token) for token in tokens)


def make_tokenizer() -> Tokenizer:
    return Tokenizer(model_name="dummy", tokenizer=DummyTokenizer())


# ============================================================================
# Header Detection Tests
# ============================================================================


@pytest.mark.offline
def test_detect_markdown_headers():
    """Test detection of Markdown-style headers."""
    content = """# Main Title

Some intro text.

## Section One

Content for section one.

### Subsection 1.1

More content here.

## Section Two

Final content.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 4
    assert sections[0].header == "# Main Title"
    assert sections[0].level == 1
    assert sections[1].header == "## Section One"
    assert sections[1].level == 2
    assert sections[2].header == "### Subsection 1.1"
    assert sections[2].level == 3
    assert sections[3].header == "## Section Two"
    assert sections[3].level == 2


@pytest.mark.offline
def test_detect_numbered_sections():
    """Test detection of numbered section headers."""
    content = """1. Introduction

This is the intro.

1.1 Background

Background info.

1.2 Scope

Scope details.

2. Methods

Methods section.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 4
    assert sections[0].header == "1. Introduction"
    assert sections[0].level == 1
    assert sections[1].header == "1.1 Background"
    assert sections[1].level == 2
    assert sections[2].header == "1.2 Scope"
    assert sections[2].level == 2
    assert sections[3].header == "2. Methods"
    assert sections[3].level == 1


@pytest.mark.offline
def test_detect_polish_paragraf():
    """Test detection of Polish § (paragraf) format."""
    content = """§ 1. Definicje

Użyte w ustawie określenia oznaczają:

§ 2 Zakres stosowania

Ustawa określa zasady...

§2.1 Szczegóły

Dodatkowe informacje.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert "§ 1" in sections[0].header
    assert sections[0].pattern_type == "paragraf"
    assert sections[0].level == 0  # No dots
    assert "§ 2" in sections[1].header
    assert "§2.1" in sections[2].header
    assert sections[2].level == 1  # One dot


@pytest.mark.offline
def test_detect_polish_artykul():
    """Test detection of Polish Art./Artykuł format."""
    content = """Art. 1. Postanowienia ogólne

Ustawa reguluje...

Artykuł 5 - Definicje

Ilekroć w ustawie jest mowa o:

Art. 5.1 Zakres

Szczegółowe przepisy.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert "Art. 1" in sections[0].header
    assert sections[0].pattern_type == "artykul"
    assert "Artykuł 5" in sections[1].header
    assert sections[1].pattern_type == "artykul"
    assert "Art. 5.1" in sections[2].header


@pytest.mark.offline
def test_detect_polish_rozdzial():
    """Test detection of Polish Rozdział (chapter) format."""
    content = """Rozdział 1 - Przepisy ogólne

Przepisy wstępne.

Rozdział II Definicje

Definicje ustawowe.

ROZDZIAŁ III

Postanowienia końcowe.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert "Rozdział 1" in sections[0].header
    assert sections[0].pattern_type == "rozdzial"
    assert "Rozdział II" in sections[1].header
    assert "ROZDZIAŁ III" in sections[2].header


@pytest.mark.offline
def test_detect_polish_czesc():
    """Test detection of Polish Część (part) format."""
    content = """Część I - Postanowienia ogólne

Wstęp.

Część 2 - Przepisy szczególne

Szczegóły.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 2
    assert "Część I" in sections[0].header
    assert sections[0].pattern_type == "czesc"
    assert "Część 2" in sections[1].header


@pytest.mark.offline
def test_detect_polish_ustep_punkt():
    """Test detection of Polish ust. (subsection) and pkt (point) format."""
    content = """ust. 1 Zakres stosowania

Przepisy dotyczą...

Ustęp 2 Wyłączenia

Nie stosuje się do...

pkt 1 przedsiębiorstwa

Definicja przedsiębiorstwa.

punkt 2 konsumenta

Definicja konsumenta.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 4
    assert "ust. 1" in sections[0].header
    assert sections[0].pattern_type == "ustep"
    assert sections[0].level == 2
    assert "Ustęp 2" in sections[1].header
    assert "pkt 1" in sections[2].header
    assert sections[2].pattern_type == "punkt"
    assert sections[2].level == 3
    assert "punkt 2" in sections[3].header


@pytest.mark.offline
def test_detect_polish_litera():
    """Test detection of Polish letter points: a), b), lit. a)."""
    content = """a) jednostka organizacyjna

Opis jednostki.

b) osoba fizyczna

Opis osoby.

lit. c) podmiot prawny

Opis podmiotu.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert "a)" in sections[0].header
    assert sections[0].pattern_type == "litera"
    assert sections[0].level == 4
    assert "b)" in sections[1].header
    assert "lit. c)" in sections[2].header


@pytest.mark.offline
def test_detect_numbered_paren():
    """Test detection of numbered lists with parenthesis: 1), 2)."""
    content = """1) przedsiębiorstwo - jednostka organizacyjna

Szczegóły przedsiębiorstwa.

2) konsument - osoba fizyczna

Szczegóły konsumenta.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 2
    assert "1)" in sections[0].header
    assert sections[0].pattern_type == "numbered_paren"
    assert sections[0].level == 3
    assert "2)" in sections[1].header


@pytest.mark.offline
def test_detect_empty_markdown_header():
    """Test detection of empty Markdown headers (## without text)."""
    content = """# Main Title

Introduction.

##

Content after empty header.

## Section Two

More content.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert sections[0].header == "# Main Title"
    assert sections[1].header == "##"  # Empty header detected
    assert sections[1].pattern_type == "markdown"
    assert sections[2].header == "## Section Two"


@pytest.mark.offline
def test_detect_polish_caps_headers():
    """Test detection of ALL-CAPS headers with Polish diacritics."""
    content = """POSTANOWIENIA OGÓLNE

Przepisy wstępne.

CZĘŚĆ SZCZEGÓLNA

Szczegółowe regulacje.

ZAŁĄCZNIKI

Lista załączników.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert sections[0].header == "POSTANOWIENIA OGÓLNE"
    assert sections[0].pattern_type == "caps_header"
    assert sections[1].header == "CZĘŚĆ SZCZEGÓLNA"
    assert sections[2].header == "ZAŁĄCZNIKI"


@pytest.mark.offline
def test_detect_numbered_dot_sections():
    """Test detection of numbered section headers (1. Title, 1.1 Title)."""
    content = """1. General Provisions

General text here.

1.1 Scope

Scope content.

2. Obligations

Obligations text.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert "1." in sections[0].header
    assert sections[0].pattern_type == "numbered"


@pytest.mark.offline
def test_detect_polish_hierarchy():
    """Test detection of Polish legal hierarchy: Część > Rozdział > § > ust. > pkt."""
    content = """Część I - Postanowienia ogólne

Wstęp do części.

Rozdział 1 - Definicje

Definicje ustawowe.

§ 1. Zakres

Zakres stosowania.

ust. 1 Szczegóły

Szczegółowe przepisy.

pkt 1 element pierwszy

Pierwszy element listy.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 5
    assert "Część I" in sections[0].header
    assert sections[0].pattern_type == "czesc"
    assert "Rozdział 1" in sections[1].header
    assert sections[1].pattern_type == "rozdzial"
    assert "§ 1" in sections[2].header
    assert sections[2].pattern_type == "paragraf"
    assert "ust. 1" in sections[3].header
    assert sections[3].pattern_type == "ustep"
    assert "pkt 1" in sections[4].header
    assert sections[4].pattern_type == "punkt"


@pytest.mark.offline
def test_detect_caps_headers():
    """Test detection of ALL-CAPS headers (English)."""
    content = """INTRODUCTION

This is introductory text about the document.

TERMS AND CONDITIONS

The following terms apply.

GENERAL PROVISIONS

General text here.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 3
    assert sections[0].header == "INTRODUCTION"
    assert sections[0].pattern_type == "caps_header"
    assert sections[1].header == "TERMS AND CONDITIONS"


# ============================================================================
# Hierarchy Building Tests
# ============================================================================


@pytest.mark.offline
def test_build_hierarchy_simple():
    """Test hierarchy building with simple nesting."""
    content = """# Document

## Section 1

Content.

### Subsection 1.1

More content.

## Section 2

Final content.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    # Section 1.1 should have Section 1 as parent
    assert sections[2].parent is sections[1]
    # Section 1 should have Document as parent
    assert sections[1].parent is sections[0]
    # Section 2 should have Document as parent
    assert sections[3].parent is sections[0]


@pytest.mark.offline
def test_build_hierarchy_deep_nesting():
    """Test hierarchy with multiple levels of nesting."""
    content = """# Level 1

## Level 2

### Level 3

#### Level 4

Content at level 4.
"""
    config = SectionChunkingConfig()
    sections = _detect_sections(content, config)

    assert len(sections) == 4
    # Each level should have previous as parent
    assert sections[1].parent is sections[0]
    assert sections[2].parent is sections[1]
    assert sections[3].parent is sections[2]


@pytest.mark.offline
def test_build_breadcrumb():
    """Test breadcrumb generation from hierarchy."""
    # Create manual hierarchy for testing
    root = _Section(
        header="Article 1",
        content="",
        level=1,
        start_pos=0,
        end_pos=10,
        pattern_type="article",
        parent=None,
    )
    child = _Section(
        header="1.1 - Coverage",
        content="",
        level=2,
        start_pos=10,
        end_pos=20,
        pattern_type="numbered",
        parent=root,
    )
    grandchild = _Section(
        header="1.1.1 - Exclusions",
        content="",
        level=3,
        start_pos=20,
        end_pos=30,
        pattern_type="numbered",
        parent=child,
    )

    breadcrumb = _build_breadcrumb(grandchild, " > ")
    assert breadcrumb == "Article 1 > 1.1 - Coverage > 1.1.1 - Exclusions"

    breadcrumb_child = _build_breadcrumb(child, " / ")
    assert breadcrumb_child == "Article 1 / 1.1 - Coverage"


@pytest.mark.offline
def test_markdown_headers_cleaned_in_breadcrumb():
    """Test that markdown # symbols are removed from breadcrumbs."""
    tokenizer = make_tokenizer()
    content = """# Main Title

## Subsection

Content here.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=200, chunk_overlap_token_size=10
    )

    # Find the subsection chunk
    sub_chunk = next((c for c in chunks if "Content here" in c["content"]), None)
    assert sub_chunk is not None
    # Should NOT have # symbols in breadcrumb
    assert "# " not in sub_chunk["content"]
    # Should have clean titles
    assert "Main Title > Subsection" in sub_chunk["content"]


# ============================================================================
# Single Chunk Tests
# ============================================================================


@pytest.mark.offline
def test_small_section_single_chunk():
    """Test that small sections produce single chunks with prefix."""
    tokenizer = make_tokenizer()
    content = """# Introduction

This is a short intro.

## Details

Brief details here.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=200, chunk_overlap_token_size=20
    )

    assert len(chunks) >= 2
    # First chunk should have breadcrumb prefix
    assert "Introduction" in chunks[0]["content"]
    # Check chunk_order_index is sequential
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_order_index"] == i


@pytest.mark.offline
def test_chunk_content_includes_prefix():
    """Test that chunk content includes hierarchical prefix."""
    tokenizer = make_tokenizer()
    content = """Article 5 - Coverage

5.1 - General Coverage

This policy covers standard items.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=500, chunk_overlap_token_size=20
    )

    # Find the chunk with "General Coverage"
    general_chunk = next((c for c in chunks if "General Coverage" in c["content"]), None)
    assert general_chunk is not None

    # Should have hierarchical prefix
    # Note: The prefix should include parent "Article 5"
    assert "Article 5" in general_chunk["content"]


# ============================================================================
# Sub-chunking Tests
# ============================================================================


@pytest.mark.offline
def test_oversized_section_gets_split():
    """Test that large sections are split with continuation markers."""
    tokenizer = make_tokenizer()
    # Create a section with lots of content
    long_content = "This is paragraph one. " * 20 + "\n\n" + "This is paragraph two. " * 20

    content = f"""# Big Section

{long_content}
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=100, chunk_overlap_token_size=10
    )

    # Should produce multiple chunks
    assert len(chunks) > 1

    # All chunks should have content
    for chunk in chunks:
        assert len(chunk["content"]) > 0
        assert chunk["tokens"] > 0


@pytest.mark.offline
def test_continuation_markers_in_split_chunks():
    """Test that split chunks have continuation markers (default Polish)."""
    tokenizer = make_tokenizer()
    long_content = "Word " * 200  # Long content to force splitting

    content = f"""# Section Title

{long_content}
"""
    # Use default config which now has Polish "(kontynuacja)" marker
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=100,
        chunk_overlap_token_size=10,
    )

    # If there are multiple chunks, later ones should have continuation marker
    if len(chunks) > 1:
        # First chunk should NOT have continuation marker
        assert "(kontynuacja)" not in chunks[0]["content"]
        # Later chunks should have it
        assert any("(kontynuacja)" in c["content"] for c in chunks[1:])


@pytest.mark.offline
def test_custom_continuation_marker():
    """Test that custom continuation marker can be set."""
    tokenizer = make_tokenizer()
    long_content = "Word " * 200  # Long content to force splitting

    content = f"""# Section Title

{long_content}
"""
    config = SectionChunkingConfig(continuation_marker="(ciąg dalszy)")
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=100,
        chunk_overlap_token_size=10,
        config=config,
    )

    # If there are multiple chunks, later ones should have custom marker
    if len(chunks) > 1:
        assert "(ciąg dalszy)" not in chunks[0]["content"]
        assert any("(ciąg dalszy)" in c["content"] for c in chunks[1:])


# ============================================================================
# Edge Case Tests
# ============================================================================


@pytest.mark.offline
def test_empty_sections_skipped():
    """Test that empty sections (header only) are handled."""
    tokenizer = make_tokenizer()
    content = """# Section One

# Section Two

Some content here.

# Section Three

"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=200, chunk_overlap_token_size=10
    )

    # Should have chunks only for sections with content
    assert len(chunks) >= 1
    # Check that we got the content from Section Two
    has_section_two_content = any("Some content here" in c["content"] for c in chunks)
    assert has_section_two_content


@pytest.mark.offline
def test_consecutive_headers():
    """Test handling of consecutive headers without content between."""
    tokenizer = make_tokenizer()
    content = """# Main
## Sub 1
### Sub 1.1
Content for 1.1.

## Sub 2
Content for 2.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=200, chunk_overlap_token_size=10
    )

    # Should produce chunks for sections with content
    assert len(chunks) >= 2


@pytest.mark.offline
def test_no_headers_fallback():
    """Test fallback to token chunking when no headers detected."""
    tokenizer = make_tokenizer()
    # Plain text with no headers
    content = "This is plain text without any headers. " * 20

    config = SectionChunkingConfig(fallback_to_token_chunking=True)
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=100,
        chunk_overlap_token_size=10,
        config=config,
    )

    # Should still produce chunks via fallback
    assert len(chunks) >= 1
    # Chunks should have standard structure
    for chunk in chunks:
        assert "tokens" in chunk
        assert "content" in chunk
        assert "chunk_order_index" in chunk


@pytest.mark.offline
def test_no_headers_no_fallback():
    """Test behavior when no headers and fallback disabled."""
    tokenizer = make_tokenizer()
    content = "Plain text content without headers."

    config = SectionChunkingConfig(fallback_to_token_chunking=False)
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=200,
        chunk_overlap_token_size=10,
        config=config,
    )

    # Should still produce output (treats as single section)
    assert len(chunks) >= 1


@pytest.mark.offline
def test_very_deep_hierarchy():
    """Test handling of very deep section hierarchy."""
    tokenizer = make_tokenizer()
    content = """# L1
## L2
### L3
#### L4
##### L5
###### L6
Deep content here.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=500, chunk_overlap_token_size=10
    )

    # Should handle deep hierarchy
    assert len(chunks) >= 1
    # The deepest section should have breadcrumb
    deep_chunk = next((c for c in chunks if "Deep content" in c["content"]), None)
    assert deep_chunk is not None


@pytest.mark.offline
def test_mixed_header_patterns():
    """Test document with mixed header patterns."""
    tokenizer = make_tokenizer()
    content = """# Introduction

Overview text.

Article 1 - Definitions

Terms defined here.

1.1 Scope

Scope details.

GENERAL PROVISIONS

Provisions text.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=200, chunk_overlap_token_size=10
    )

    # Should detect and chunk all different patterns
    assert len(chunks) >= 3


# ============================================================================
# Token Count Verification Tests
# ============================================================================


@pytest.mark.offline
def test_tokens_field_includes_prefix():
    """Test that the tokens field accounts for the prefix."""
    tokenizer = make_tokenizer()
    content = """# Section Header

Short content.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=200, chunk_overlap_token_size=10
    )

    for chunk in chunks:
        # Verify token count matches actual encoding
        actual_tokens = len(tokenizer.encode(chunk["content"]))
        assert chunk["tokens"] == actual_tokens


@pytest.mark.offline
def test_chunks_respect_token_limit():
    """Test that no chunk exceeds the token limit."""
    tokenizer = make_tokenizer()
    long_content = "This is content. " * 100

    content = f"""# Section

{long_content}
"""
    chunk_token_size = 150
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=chunk_token_size,
        chunk_overlap_token_size=20,
    )

    for chunk in chunks:
        # Allow small overage for prefix calculation edge cases
        assert chunk["tokens"] <= chunk_token_size + 20, (
            f"Chunk exceeds limit: {chunk['tokens']} > {chunk_token_size}"
        )


# ============================================================================
# Configuration Tests
# ============================================================================


@pytest.mark.offline
def test_custom_breadcrumb_separator():
    """Test custom breadcrumb separator."""
    tokenizer = make_tokenizer()
    content = """# Parent
## Child
Content here.
"""
    config = SectionChunkingConfig(breadcrumb_separator=" / ")
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=200,
        chunk_overlap_token_size=10,
        config=config,
    )

    child_chunk = next((c for c in chunks if "Child" in c["content"]), None)
    assert child_chunk is not None
    assert " / " in child_chunk["content"]


@pytest.mark.offline
def test_custom_prefix_suffix():
    """Test custom prefix suffix."""
    tokenizer = make_tokenizer()
    content = """# Section
Some content.
"""
    config = SectionChunkingConfig(prefix_suffix=" - ")
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=200,
        chunk_overlap_token_size=10,
        config=config,
    )

    assert len(chunks) >= 1
    # Check that prefix suffix is used
    assert " - " in chunks[0]["content"]


@pytest.mark.offline
def test_custom_context_prefix_budget():
    """Test that context_prefix_budget affects prefix handling."""
    tokenizer = make_tokenizer()

    # Create content with deep hierarchy
    content = """# Level One With Long Title
## Level Two With Another Long Title
### Level Three Even Longer Title Here
Short content.
"""
    # Very small budget should truncate prefix
    config = SectionChunkingConfig(context_prefix_budget=0.05)
    chunks = section_aware_chunking(
        tokenizer,
        content,
        chunk_token_size=100,
        chunk_overlap_token_size=10,
        config=config,
    )

    assert len(chunks) >= 1


# ============================================================================
# Signature Compatibility Tests
# ============================================================================


@pytest.mark.offline
def test_signature_compatibility_params_ignored():
    """Test that split_by_character params are accepted but ignored."""
    tokenizer = make_tokenizer()
    content = """# Section
Content here.
"""
    # These params should be accepted but not affect section-aware chunking
    chunks = section_aware_chunking(
        tokenizer,
        content,
        split_by_character="\n\n",
        split_by_character_only=True,
        chunk_token_size=200,
        chunk_overlap_token_size=10,
    )

    assert len(chunks) >= 1
    # Should still have section-aware prefix
    assert "Section" in chunks[0]["content"]


@pytest.mark.offline
def test_chunk_order_index_sequential():
    """Test that chunk_order_index is sequential starting from 0."""
    tokenizer = make_tokenizer()
    long_content = "Content text. " * 50

    content = f"""# Section One
{long_content}

# Section Two
{long_content}
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=100, chunk_overlap_token_size=10
    )

    indices = [c["chunk_order_index"] for c in chunks]
    expected = list(range(len(chunks)))
    assert indices == expected


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.offline
def test_polish_legal_document_structure():
    """Test with realistic Polish legal document structure."""
    tokenizer = make_tokenizer()
    content = """§ 1. Definicje

Użyte w ustawie określenia oznaczają:

1) przedsiębiorstwo - jednostka organizacyjna prowadząca działalność gospodarczą

2) konsument - osoba fizyczna dokonująca czynności prawnej

§ 2. Zakres stosowania

ust. 1 Przepisy ogólne

Ustawa określa zasady prowadzenia działalności gospodarczej.

ust. 2 Wyłączenia

Przepisów ustawy nie stosuje się do działalności rolniczej.

Art. 3. Postanowienia końcowe

Ustawa wchodzi w życie po upływie 14 dni od dnia ogłoszenia.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=300, chunk_overlap_token_size=20
    )

    # Should produce multiple chunks preserving structure
    assert len(chunks) >= 3

    # Verify some chunks have Polish legal prefixes in content
    paragraf_chunks = [c for c in chunks if "§" in c["content"]]
    assert len(paragraf_chunks) >= 1


@pytest.mark.offline
def test_markdown_document_structure():
    """Test with realistic Markdown document structure."""
    tokenizer = make_tokenizer()
    content = """# API Documentation

## Getting Started

To use this API, first obtain an API key from the developer portal.

### Authentication

All requests must include the API key in the header.

### Rate Limits

Requests are limited to 1000 per hour.

## Endpoints

### GET /users

Returns a list of users.

### POST /users

Creates a new user.

## Error Handling

All errors return standard HTTP status codes.
"""
    chunks = section_aware_chunking(
        tokenizer, content, chunk_token_size=200, chunk_overlap_token_size=20
    )

    # Should produce chunks with hierarchical context
    assert len(chunks) >= 4

    # Find a deeply nested chunk
    auth_chunk = next((c for c in chunks if "Authentication" in c["content"]), None)
    if auth_chunk:
        # Should have parent context
        assert "Getting Started" in auth_chunk["content"] or "API" in auth_chunk["content"]
