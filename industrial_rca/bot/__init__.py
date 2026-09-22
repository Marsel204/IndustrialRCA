"""
Telegram Bot package for Industrial Root Cause Analysis (RCA).
Provides real-time alerting, LangGraph HITL approval, DeepSeek AI Copilot,
and in-memory Matplotlib industrial waveform charting.
"""

from industrial_rca.bot.telegram_client import TelegramClient
from industrial_rca.bot.chart_generator import (
    generate_trip_waveform,
    generate_live_trend_plot,
    generate_spectrum_plot,
)
from industrial_rca.bot.telegram_bot import (
    TelegramBotService,
    get_telegram_service,
)

__all__ = [
    "TelegramClient",
    "TelegramBotService",
    "get_telegram_service",
    "generate_trip_waveform",
    "generate_live_trend_plot",
    "generate_spectrum_plot",
]
