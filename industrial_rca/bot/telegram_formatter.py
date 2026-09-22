"""
Telegram message formatting utilities for Industrial RCA Bot.
Converts Markdown outputs from LLMs (DeepSeek) into clean, valid Telegram HTML.
"""

import re
import html
from typing import List


def format_telegram_response(text: str) -> str:
    """
    Converts LLM markdown output into pristine, valid Telegram HTML.
    
    Transforms:
    - Code blocks (```lang ... ```) -> <pre>...</pre>
    - Inline code (`code`) -> <code>code</code>
    - Headers (### Header) -> <b>Header</b>
    - Bold (**bold** or __bold__) -> <b>bold</b>
    - Italics (*italic* or _italic_) -> <i>italic</i>
    - Lists (- item or * item) -> • item
    - Unescaped <, >, & -> &lt;, &gt;, &amp;
    """
    if not text:
        return ""

    text = str(text).replace("\r\n", "\n")

    # 1. Extract triple-backtick code blocks first to protect their contents
    code_blocks: List[str] = []

    def _replace_block(match: re.Match) -> str:
        code_blocks.append(match.group(1))
        return f"\x00BLOCK{len(code_blocks) - 1}\x00"

    text = re.sub(r"```(?:\w+)?\n?([\s\S]*?)```", _replace_block, text)

    # 2. Extract inline code (single backticks)
    inline_codes: List[str] = []

    def _replace_inline(match: re.Match) -> str:
        inline_codes.append(match.group(1))
        return f"\x00INLINE{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", _replace_inline, text)

    # 3. Escape HTML special characters in the normal prose
    text = html.escape(text, quote=False)

    # 4. Markdown headers: # Header, ## Header, ### Header -> <b>Header</b>
    text = re.sub(r"^(?:#{1,6}\s*)(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 5. Bold: **text** or __text__ -> <b>text</b>
    text = re.sub(r"\*\*([^\*\n]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_\n]+)__", r"<b>\1</b>", text)

    # 6. Italics: *text* (single asterisk) or _text_ -> <i>text</i>
    text = re.sub(r"(?<!\*)\*([^\*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", text)

    # 7. Unordered list markers (- item or * item) -> clean bullet point (• item)
    text = re.sub(r"^\s*[\*\-]\s+", "• ", text, flags=re.MULTILINE)

    # 8. Restore inline codes wrapped in <code>
    for i, code in enumerate(inline_codes):
        escaped_code = html.escape(code, quote=False)
        text = text.replace(f"\x00INLINE{i}\x00", f"<code>{escaped_code}</code>")

    # 9. Restore code blocks wrapped in <pre>
    for i, block in enumerate(code_blocks):
        escaped_block = html.escape(block, quote=False)
        text = text.replace(f"\x00BLOCK{i}\x00", f"<pre>{escaped_block}</pre>")

    # 10. Clean up excessive consecutive blank lines (max 2)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text


def strip_html_tags(text: str) -> str:
    """Removes all HTML tags for plain-text fallback."""
    if not text:
        return ""
    # Unescape common entities after removing tags
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean)
    return clean.strip()
