"""
Tests for Telegram message formatter (Markdown to Telegram HTML conversion).
"""

import pytest
from industrial_rca.bot.telegram_formatter import format_telegram_response, strip_html_tags


def test_format_markdown_bold():
    raw = "**System Status: OK**"
    formatted = format_telegram_response(raw)
    assert formatted == "<b>System Status: OK</b>"


def test_format_bullet_lists():
    raw = "- Item 1\n- Item 2\n* Item 3"
    formatted = format_telegram_response(raw)
    assert formatted == "• Item 1\n• Item 2\n• Item 3"


def test_format_inline_code():
    raw = "Frequency is `40.0 Hz`"
    formatted = format_telegram_response(raw)
    assert formatted == "Frequency is <code>40.0 Hz</code>"


def test_format_code_block():
    raw = "```python\nx = 1\n```"
    formatted = format_telegram_response(raw)
    assert "<pre>x = 1\n</pre>" in formatted or "<pre>x = 1</pre>" in formatted


def test_format_html_escaping():
    raw = "Voltage is < 195 V and Current > 1.2 A & Safe"
    formatted = format_telegram_response(raw)
    assert "&lt; 195 V" in formatted
    assert "&gt; 1.2 A" in formatted
    assert "&amp; Safe" in formatted


def test_format_complex_llm_response():
    raw = (
        "### System Diagnosis\n\n"
        "**Status**: *Nominal*\n"
        "- Motor Speed: `1200 RPM`\n"
        "- DC Bus: `182.0 V` (Limit < 195V)\n"
    )
    formatted = format_telegram_response(raw)
    assert "<b>System Diagnosis</b>" in formatted
    assert "<b>Status</b>: <i>Nominal</i>" in formatted
    assert "• Motor Speed: <code>1200 RPM</code>" in formatted
    assert "• DC Bus: <code>182.0 V</code> (Limit &lt; 195V)" in formatted


def test_strip_html_tags():
    html_text = "<b>Status:</b> <code>OK</code> &amp; Nominal"
    clean = strip_html_tags(html_text)
    assert clean == "Status: OK & Nominal"
