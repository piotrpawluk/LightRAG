"""Section-aware chunking for LightRAG.

This module provides a section-aware chunking strategy that preserves document
hierarchy by detecting headers (Markdown, numbered sections, legal formats)
and prepending breadcrumb context to each chunk.

Example:
    >>> from lightrag.chunking import section_aware_chunking, SectionChunkingConfig
    >>> from functools import partial
    >>>
    >>> # Basic usage
    >>> rag = LightRAG(chunking_func=section_aware_chunking)
    >>>
    >>> # With custom config
    >>> config = SectionChunkingConfig(context_prefix_budget=0.20)
    >>> rag = LightRAG(chunking_func=partial(section_aware_chunking, config=config))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lightrag.utils import Tokenizer

# Default section patterns for header detection (Polish legal documents)
# Each tuple: (compiled_pattern, pattern_type, level_extractor)
# level_extractor: function that returns hierarchy level from match
# Polish legal hierarchy: Część > Rozdział > Art./§ > ust. > pkt > lit.
# Note: Use [ \t] instead of \s where newlines shouldn't match (between header and content)
DEFAULT_SECTION_PATTERNS: list[tuple[re.Pattern, str, Any]] = [
    # Markdown headers: # Title, ## (with or without text)
    (re.compile(r"^(#{1,6})([ \t]*)([^\n]*)$", re.MULTILINE), "markdown", lambda m: len(m.group(1))),
    # § (Paragraf) - Polish legal: § 1, §1, § 1., § 1.1
    (
        re.compile(r"^(§[ \t]*\d+(?:\.\d+)*\.?)[ \t]*[-:\.]?[ \t]*([^\n]*)$", re.MULTILINE),
        "paragraf",
        lambda m: m.group(1).count("."),  # Level based on dots: §1 = 0, §1.1 = 1
    ),
    # Art./Artykuł - Polish article: Art. 1, Artykuł 5, Art. 5.1
    (
        re.compile(
            r"^(Art(?:ykuł)?\.?[ \t]*\d+(?:\.\d+)*)[ \t]*[-:\.]?[ \t]*([^\n]*)$",
            re.MULTILINE | re.IGNORECASE,
        ),
        "artykul",
        lambda m: m.group(1).count("."),
    ),
    # Rozdział - Polish chapter: Rozdział 1, Rozdział I, ROZDZIAŁ II
    (
        re.compile(
            r"^((?:Rozdział|ROZDZIAŁ)[ \t]+[\dIVXLCDM]+)[ \t]*[-:\.]?[ \t]*([^\n]*)$", re.MULTILINE
        ),
        "rozdzial",
        lambda m: 1,
    ),
    # Część - Polish part: Część I, Część 1
    (
        re.compile(
            r"^((?:Część|CZĘŚĆ)[ \t]+[\dIVXLCDM]+)[ \t]*[-:\.]?[ \t]*([^\n]*)$", re.MULTILINE
        ),
        "czesc",
        lambda m: 1,
    ),
    # Ustęp/ust. - Polish subsection: ust. 1, Ustęp 2
    (
        re.compile(
            r"^((?:Ustęp|ust\.?)[ \t]*\d+)[ \t]*[-:\.]?[ \t]*([^\n]*)$", re.MULTILINE | re.IGNORECASE
        ),
        "ustep",
        lambda m: 2,
    ),
    # Punkt/pkt - Polish point: pkt 1, punkt 2, pkt. 1
    (
        re.compile(
            r"^((?:punkt|pkt)\.?[ \t]*\d+)[ \t]*[-:\.]?[ \t]*([^\n]*)$", re.MULTILINE | re.IGNORECASE
        ),
        "punkt",
        lambda m: 3,
    ),
    # Numbered lists with parenthesis: 1), 2), etc.
    (
        re.compile(r"^(\d+\))[ \t]+([^\n]+)$", re.MULTILINE),
        "numbered_paren",
        lambda m: 3,
    ),
    # Letter points: a), b), lit. a)
    (
        re.compile(r"^((?:lit\.?[ \t]*)?[a-z]\))[ \t]*([^\n]*)$", re.MULTILINE | re.IGNORECASE),
        "litera",
        lambda m: 4,
    ),
    # Numbered sections: 1. Title, 1.1 Title
    (
        re.compile(r"^(\d+(?:\.\d+)*\.?)[ \t]+([^\n]+)$", re.MULTILINE),
        "numbered",
        lambda m: m.group(1).count(".") + 1,
    ),
    # ALL-CAPS headers (common in legal docs) - with Polish diacritics (space only, not \s)
    (re.compile(r"^([A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ ]{4,})$", re.MULTILINE), "caps_header", lambda m: 1),
]


@dataclass
class SectionChunkingConfig:
    """Configuration for section-aware chunking.

    Attributes:
        section_patterns: Custom patterns for header detection.
            Each tuple: (regex_pattern_string, pattern_type).
            If None, uses DEFAULT_SECTION_PATTERNS.
        context_prefix_budget: Fraction of chunk_token_size reserved for breadcrumb prefix.
            Default 0.15 (15%) allows for moderate hierarchy depth.
        min_chunk_tokens: Minimum viable chunk size. Chunks smaller than this
            are merged with adjacent content.
        breadcrumb_separator: String used to join hierarchy levels in prefix.
            Example: "Article 5 > 5.2 - Title"
        prefix_suffix: String appended after breadcrumb, before content.
            Example with ": " suffix: "Article 5 > 5.2: content..."
        preserve_paragraphs: When True, prefers splitting at paragraph boundaries
            (\n\n) rather than mid-paragraph.
        continuation_marker: Marker added to sub-chunks when a section is split.
            Example: "Article 5 (continued 2/3): ..."
        fallback_to_token_chunking: When True and no headers detected, falls back
            to standard token-based chunking.
    """

    section_patterns: list[tuple[str, str]] | None = None
    context_prefix_budget: float = 0.15
    min_chunk_tokens: int = 50
    breadcrumb_separator: str = " > "
    prefix_suffix: str = ": "
    preserve_paragraphs: bool = True
    continuation_marker: str = "(kontynuacja)"
    fallback_to_token_chunking: bool = True

    # Compiled patterns cache (populated on first use)
    _compiled_patterns: list[tuple[re.Pattern, str, Any]] = field(
        default_factory=list, repr=False, compare=False
    )

    def get_patterns(self) -> list[tuple[re.Pattern, str, Any]]:
        """Get compiled regex patterns for header detection."""
        if self._compiled_patterns:
            return self._compiled_patterns

        if self.section_patterns is None:
            self._compiled_patterns = DEFAULT_SECTION_PATTERNS
        else:
            # Compile custom patterns
            self._compiled_patterns = []
            for pattern_str, pattern_type in self.section_patterns:
                compiled = re.compile(pattern_str, re.MULTILINE | re.IGNORECASE)
                # Default level extractor based on dots in match
                level_fn = lambda m: m.group(1).count(".") + 1
                self._compiled_patterns.append((compiled, pattern_type, level_fn))

        return self._compiled_patterns


@dataclass
class _Section:
    """Internal representation of a document section."""

    header: str  # The header text (e.g., "Article 5 - Coverage")
    content: str  # Section content (excluding header)
    level: int  # Hierarchy level (1 = top level)
    start_pos: int  # Character position in original document
    end_pos: int  # End position
    pattern_type: str  # Which pattern matched (for debugging)
    parent: _Section | None = None  # Parent section reference


def _detect_sections(content: str, config: SectionChunkingConfig) -> list[_Section]:
    """Parse document and identify section headers with their hierarchy.

    Args:
        content: Full document text
        config: Chunking configuration

    Returns:
        List of _Section objects ordered by position
    """
    patterns = config.get_patterns()
    sections: list[_Section] = []

    # Find all header matches with their positions
    header_matches: list[tuple[int, int, str, int, str]] = []  # (start, end, header, level, type)

    for pattern, pattern_type, level_fn in patterns:
        for match in pattern.finditer(content):
            header_text = match.group(0).strip()
            level = level_fn(match)
            header_matches.append((match.start(), match.end(), header_text, level, pattern_type))

    # Sort by position (earlier first)
    header_matches.sort(key=lambda x: x[0])

    # Remove overlapping matches (keep first match at each position)
    filtered_matches: list[tuple[int, int, str, int, str]] = []
    last_end = -1
    for start, end, header, level, ptype in header_matches:
        if start >= last_end:
            filtered_matches.append((start, end, header, level, ptype))
            last_end = end

    # Build sections with content between headers
    for i, (start, end, header, level, ptype) in enumerate(filtered_matches):
        # Content runs from end of this header to start of next header (or document end)
        if i + 1 < len(filtered_matches):
            content_end = filtered_matches[i + 1][0]
        else:
            content_end = len(content)

        section_content = content[end:content_end].strip()

        sections.append(
            _Section(
                header=header,
                content=section_content,
                level=level,
                start_pos=start,
                end_pos=content_end,
                pattern_type=ptype,
                parent=None,
            )
        )

    # Build parent references based on hierarchy levels
    _build_hierarchy(sections)

    return sections


def _build_hierarchy(sections: list[_Section]) -> None:
    """Establish parent-child relationships based on hierarchy levels.

    Modifies sections in-place to set parent references.
    """
    if not sections:
        return

    # Stack of potential parents at each level
    level_stack: dict[int, _Section] = {}

    for section in sections:
        # Find closest ancestor with lower level
        parent = None
        for check_level in range(section.level - 1, 0, -1):
            if check_level in level_stack:
                parent = level_stack[check_level]
                break

        section.parent = parent
        level_stack[section.level] = section

        # Clear deeper levels (they can't be parents of subsequent sections)
        levels_to_clear = [lvl for lvl in level_stack if lvl > section.level]
        for lvl in levels_to_clear:
            del level_stack[lvl]


def _clean_header_for_breadcrumb(header: str, pattern_type: str) -> str:
    """Clean up header text for breadcrumb display.

    Removes markdown syntax (# symbols) but preserves meaningful text.
    """
    if pattern_type == "markdown":
        # Remove leading # symbols and whitespace
        return re.sub(r"^#+\s*", "", header)
    return header


def _build_breadcrumb(section: _Section, separator: str) -> str:
    """Build hierarchical breadcrumb prefix for a section.

    Example: "Article 5 > 5.2 - Exclusions"
    """
    parts: list[str] = []
    current: _Section | None = section

    while current is not None:
        clean_header = _clean_header_for_breadcrumb(current.header, current.pattern_type)
        parts.append(clean_header)
        current = current.parent

    # Reverse to get root-to-leaf order
    parts.reverse()
    return separator.join(parts)


def _sub_chunk_content(
    tokenizer: Tokenizer,
    content: str,
    prefix: str,
    chunk_token_size: int,
    overlap_tokens: int,
    preserve_paragraphs: bool,
    continuation_marker: str,
    prefix_suffix: str,
) -> list[dict[str, Any]]:
    """Split oversized content into multiple chunks with context prefix.

    Args:
        tokenizer: Tokenizer instance
        content: Content to split
        prefix: Breadcrumb prefix for context
        chunk_token_size: Maximum tokens per chunk
        overlap_tokens: Token overlap between chunks
        preserve_paragraphs: Try to split at paragraph boundaries
        continuation_marker: Marker for subsequent chunks
        prefix_suffix: String after prefix, before content

    Returns:
        List of chunk dictionaries
    """
    chunks: list[dict[str, Any]] = []

    # Calculate available tokens for content
    prefix_tokens = len(tokenizer.encode(prefix + prefix_suffix))
    continuation_tokens = len(tokenizer.encode(f" {continuation_marker} 2/2"))
    available_tokens = chunk_token_size - prefix_tokens - continuation_tokens

    if available_tokens < 50:
        # Prefix too long, just use minimal prefix
        available_tokens = chunk_token_size - 20

    # Try paragraph-aware splitting first
    if preserve_paragraphs:
        paragraphs = content.split("\n\n")
        current_paragraphs: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = len(tokenizer.encode(para))

            if current_tokens + para_tokens <= available_tokens:
                current_paragraphs.append(para)
                current_tokens += para_tokens
            else:
                # Emit current batch
                if current_paragraphs:
                    chunk_content = "\n\n".join(current_paragraphs)
                    chunks.append({"content": chunk_content, "tokens": current_tokens})

                # Handle oversized single paragraph
                if para_tokens > available_tokens:
                    # Fall back to token-based splitting for this paragraph
                    para_chunks = _token_split(
                        tokenizer, para, available_tokens, overlap_tokens
                    )
                    chunks.extend(para_chunks)
                    current_paragraphs = []
                    current_tokens = 0
                else:
                    current_paragraphs = [para]
                    current_tokens = para_tokens

        # Don't forget remaining content
        if current_paragraphs:
            chunk_content = "\n\n".join(current_paragraphs)
            chunks.append({"content": chunk_content, "tokens": current_tokens})
    else:
        # Pure token-based splitting
        chunks = _token_split(tokenizer, content, available_tokens, overlap_tokens)

    # Add prefix and continuation markers to all chunks
    total_chunks = len(chunks)
    result: list[dict[str, Any]] = []

    for i, chunk in enumerate(chunks):
        if i == 0:
            full_prefix = prefix + prefix_suffix
        else:
            full_prefix = f"{prefix} {continuation_marker} {i + 1}/{total_chunks}{prefix_suffix}"

        full_content = full_prefix + chunk["content"]
        full_tokens = len(tokenizer.encode(full_content))

        result.append({"content": full_content, "tokens": full_tokens})

    return result


def _token_split(
    tokenizer: Tokenizer, content: str, chunk_tokens: int, overlap_tokens: int
) -> list[dict[str, Any]]:
    """Split content by token count with overlap."""
    tokens = tokenizer.encode(content)
    chunks: list[dict[str, Any]] = []

    if len(tokens) <= chunk_tokens:
        return [{"content": content, "tokens": len(tokens)}]

    step = max(1, chunk_tokens - overlap_tokens)

    for start in range(0, len(tokens), step):
        end = min(start + chunk_tokens, len(tokens))
        chunk_content = tokenizer.decode(tokens[start:end])
        chunks.append({"content": chunk_content.strip(), "tokens": end - start})

        if end >= len(tokens):
            break

    return chunks


def _fallback_token_chunking(
    tokenizer: Tokenizer,
    content: str,
    chunk_token_size: int,
    chunk_overlap_token_size: int,
) -> list[dict[str, Any]]:
    """Standard token-based chunking (fallback when no sections detected)."""
    tokens = tokenizer.encode(content)
    results: list[dict[str, Any]] = []

    step = max(1, chunk_token_size - chunk_overlap_token_size)

    for index, start in enumerate(range(0, len(tokens), step)):
        end = min(start + chunk_token_size, len(tokens))
        chunk_content = tokenizer.decode(tokens[start:end])
        results.append(
            {
                "tokens": end - start,
                "content": chunk_content.strip(),
                "chunk_order_index": index,
            }
        )

        if end >= len(tokens):
            break

    return results


def section_aware_chunking(
    tokenizer: Tokenizer,
    content: str,
    split_by_character: str | None = None,
    split_by_character_only: bool = False,
    chunk_overlap_token_size: int = 100,
    chunk_token_size: int = 1200,
    *,
    config: SectionChunkingConfig | None = None,
) -> list[dict[str, Any]]:
    """Section-aware chunking that preserves document hierarchy.

    This function detects section headers (Markdown, numbered, legal formats)
    and chunks content while preserving hierarchical context via breadcrumb
    prefixes.

    Args:
        tokenizer: Tokenizer instance for token counting
        content: Document text to chunk
        split_by_character: Ignored (kept for signature compatibility)
        split_by_character_only: Ignored (kept for signature compatibility)
        chunk_overlap_token_size: Token overlap between chunks
        chunk_token_size: Maximum tokens per chunk (including prefix)
        config: Optional SectionChunkingConfig for customization

    Returns:
        List of chunk dictionaries with keys:
        - tokens: Number of tokens in chunk
        - content: Chunk text with breadcrumb prefix
        - chunk_order_index: Sequential chunk index

    Example:
        >>> chunks = section_aware_chunking(tokenizer, doc_text, chunk_token_size=500)
        >>> # Output: [{"tokens": 45, "content": "Article 5 > 5.1: ...", "chunk_order_index": 0}, ...]
    """
    if config is None:
        config = SectionChunkingConfig()

    # Detect sections in document
    sections = _detect_sections(content, config)

    # If no sections found, optionally fall back to token chunking
    if not sections:
        if config.fallback_to_token_chunking:
            return _fallback_token_chunking(
                tokenizer, content, chunk_token_size, chunk_overlap_token_size
            )
        else:
            # Treat entire document as single section
            sections = [
                _Section(
                    header="",
                    content=content,
                    level=1,
                    start_pos=0,
                    end_pos=len(content),
                    pattern_type="none",
                    parent=None,
                )
            ]

    results: list[dict[str, Any]] = []
    chunk_index = 0

    # Calculate prefix budget in tokens
    max_prefix_tokens = int(chunk_token_size * config.context_prefix_budget)

    for section in sections:
        # Build breadcrumb prefix
        breadcrumb = _build_breadcrumb(section, config.breadcrumb_separator)

        # Truncate prefix if too long
        prefix_tokens = len(tokenizer.encode(breadcrumb + config.prefix_suffix))
        if prefix_tokens > max_prefix_tokens and breadcrumb:
            # Truncate breadcrumb (keep end, it's most specific)
            tokens_list = tokenizer.encode(breadcrumb)
            keep_tokens = max(10, max_prefix_tokens - len(tokenizer.encode(config.prefix_suffix)))
            breadcrumb = "..." + tokenizer.decode(tokens_list[-keep_tokens:]).strip()

        # Skip empty sections
        if not section.content.strip():
            continue

        # Calculate content with prefix
        if breadcrumb:
            full_prefix = breadcrumb + config.prefix_suffix
        else:
            full_prefix = ""

        content_tokens = len(tokenizer.encode(section.content))
        prefix_token_count = len(tokenizer.encode(full_prefix))
        total_tokens = content_tokens + prefix_token_count

        # Check if section fits in one chunk
        if total_tokens <= chunk_token_size:
            full_content = full_prefix + section.content
            results.append(
                {
                    "tokens": total_tokens,
                    "content": full_content.strip(),
                    "chunk_order_index": chunk_index,
                }
            )
            chunk_index += 1
        else:
            # Section needs to be split
            sub_chunks = _sub_chunk_content(
                tokenizer=tokenizer,
                content=section.content,
                prefix=breadcrumb,
                chunk_token_size=chunk_token_size,
                overlap_tokens=chunk_overlap_token_size,
                preserve_paragraphs=config.preserve_paragraphs,
                continuation_marker=config.continuation_marker,
                prefix_suffix=config.prefix_suffix,
            )

            for sub_chunk in sub_chunks:
                results.append(
                    {
                        "tokens": sub_chunk["tokens"],
                        "content": sub_chunk["content"].strip(),
                        "chunk_order_index": chunk_index,
                    }
                )
                chunk_index += 1

    # Handle edge case: all sections were empty
    if not results and content.strip():
        return _fallback_token_chunking(
            tokenizer, content, chunk_token_size, chunk_overlap_token_size
        )

    return results
