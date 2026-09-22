"""
Asynchronous Telegram Bot API Client built with httpx.
Provides native async methods for messaging, inline keyboards, photo uploads,
and long-polling without external heavyweight dependencies.
"""

import io
import asyncio
import re
from typing import Dict, Any, List, Optional, Union
import httpx

from industrial_rca.utils.logging import get_logger

logger = get_logger("industrial_rca.bot.client")


class TelegramClient:
    """Async client for Telegram Bot API."""

    def __init__(self, token: str, timeout: float = 15.0):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Returns or creates the underlying httpx AsyncClient, resilient to event loop changes."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            self._client is None
            or self._client.is_closed
            or getattr(self, "_loop", None) != current_loop
        ):
            self._loop = current_loop
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Closes the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    async def get_me(self) -> Dict[str, Any]:
        """Tests the bot token and returns basic bot identity."""
        client = await self.get_client()
        resp = await client.get(f"{self.base_url}/getMe")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise ValueError(f"Telegram API Error: {data.get('description')}")
        return data.get("result", {})

    @staticmethod
    def _clean_reply_markup(reply_markup: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Validates inline keyboard buttons.
        Removes buttons with invalid localhost or non-public URLs which Telegram rejects with 400 Bad Request.
        If all buttons in a row are removed or keyboard is empty, returns None to prevent Telegram error.
        """
        if not reply_markup or not isinstance(reply_markup, dict):
            return None
        ik = reply_markup.get("inline_keyboard")
        if not isinstance(ik, list):
            return reply_markup

        valid_rows = []
        for row in ik:
            if not isinstance(row, list):
                continue
            valid_row = []
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                url = btn.get("url")
                if url:
                    lower_url = str(url).lower()
                    if "localhost" in lower_url or "127.0.0.1" in lower_url:
                        continue
                    if not (lower_url.startswith("http://") or lower_url.startswith("https://")):
                        continue
                valid_row.append(btn)
            if valid_row:
                valid_rows.append(valid_row)

        if not valid_rows:
            return None
        return {"inline_keyboard": valid_rows}

    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        """Sends a text message with optional inline buttons and formatting."""
        client = await self.get_client()
        cleaned_markup = self._clean_reply_markup(reply_markup)
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if cleaned_markup:
            payload["reply_markup"] = cleaned_markup

        resp = await client.post(f"{self.base_url}/sendMessage", json=payload)
        if resp.status_code != 200:
            # Fallback for entity parse errors (e.g. malformed HTML tags)
            if resp.status_code == 400 and payload.get("parse_mode"):
                logger.warning(f"Telegram sendMessage parse_mode={parse_mode} failed, retrying plain text: {resp.text}")
                fallback_payload = dict(payload)
                fallback_payload.pop("parse_mode", None)
                fallback_payload["text"] = re.sub(r"<[^>]+>", "", text)
                resp = await client.post(f"{self.base_url}/sendMessage", json=fallback_payload)
            if resp.status_code != 200:
                logger.error(f"Telegram sendMessage error ({resp.status_code}): {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.warning(f"Failed to send Telegram message: {data.get('description')}")
            raise ValueError(f"Telegram send_message failed: {data.get('description')}")
        return data.get("result", {})

    async def send_photo(
        self,
        chat_id: Union[int, str],
        photo_bytes: bytes,
        filename: str = "waveform.png",
        caption: Optional[str] = None,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Uploads and sends an in-memory PNG photo."""
        client = await self.get_client()
        cleaned_markup = self._clean_reply_markup(reply_markup)
        data_fields: Dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data_fields["caption"] = caption
            data_fields["parse_mode"] = parse_mode
        if cleaned_markup:
            import json
            data_fields["reply_markup"] = json.dumps(cleaned_markup)

        files = {
            "photo": (filename, photo_bytes, "image/png"),
        }

        resp = await client.post(f"{self.base_url}/sendPhoto", data=data_fields, files=files)
        if resp.status_code != 200:
            logger.error(f"Telegram sendPhoto error ({resp.status_code}): {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.warning(f"Failed to send Telegram photo: {data.get('description')}")
            raise ValueError(f"Telegram send_photo failed: {data.get('description')}")
        return data.get("result", {})

    async def edit_message_text(
        self,
        chat_id: Union[int, str],
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Edits an existing text message (e.g. to update action buttons)."""
        client = await self.get_client()
        cleaned_markup = self._clean_reply_markup(reply_markup)
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if cleaned_markup is not None:
            payload["reply_markup"] = cleaned_markup

        resp = await client.post(f"{self.base_url}/editMessageText", json=payload)
        if resp.status_code != 200:
            data = resp.json() if resp.content else {}
            desc = str(data.get("description", resp.text))
            # If Telegram says "message is not modified", telemetry values haven't changed — return safely
            if "message is not modified" in desc.lower():
                return data.get("result", {})
            # Fallback for entity parse errors
            if resp.status_code == 400 and payload.get("parse_mode") and "can't parse entities" in desc.lower():
                logger.warning(f"Telegram editMessageText parse error, retrying plain text: {desc}")
                fallback_payload = dict(payload)
                fallback_payload.pop("parse_mode", None)
                fallback_payload["text"] = re.sub(r"<[^>]+>", "", text)
                resp = await client.post(f"{self.base_url}/editMessageText", json=fallback_payload)
            if resp.status_code != 200:
                logger.warning(f"Telegram editMessageText error ({resp.status_code}): {desc}")
                resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.warning(f"Failed to edit Telegram message: {data.get('description')}")
        return data.get("result", {})


    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> bool:
        """Acknowledges an inline keyboard callback query."""
        client = await self.get_client()
        payload: Dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text

        try:
            resp = await client.post(f"{self.base_url}/answerCallbackQuery", json=payload)
            data = resp.json()
            return bool(data.get("ok"))
        except Exception as e:
            logger.warning(f"Failed to answer callback query {callback_query_id}: {e}")
            return False

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 50,
        timeout: int = 15,
    ) -> List[Dict[str, Any]]:
        """Long-polls for incoming updates."""
        try:
            client = await self.get_client()
            params: Dict[str, Any] = {"limit": limit, "timeout": timeout}
            if offset is not None:
                params["offset"] = offset

            # Use a slightly longer HTTP timeout than the long-poll timeout
            resp = await client.get(
                f"{self.base_url}/getUpdates",
                params=params,
                timeout=timeout + 5.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                logger.warning(f"Telegram getUpdates failed: {data.get('description')}")
                return []
            return data.get("result", [])
        except httpx.TimeoutException:
            # Normal long-polling timeout when no new messages arrived
            return []
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                self._client = None
                return []
            raise
        except httpx.RequestError as e:
            logger.debug(f"Transient Telegram network glitch: {e}")
            return []

    @staticmethod
    def build_inline_keyboard(rows: List[List[Dict[str, str]]]) -> Dict[str, Any]:
        """
        Builds a Telegram InlineKeyboardMarkup object.
        Example row:
            [{"text": "✅ Approve", "callback_data": "approve_123"},
             {"text": "🔗 Web App", "url": "http://localhost:5173"}]
        """
        return {"inline_keyboard": rows}
