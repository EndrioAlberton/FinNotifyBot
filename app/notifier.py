"""Cliente minimo da Bot API: envia alertas e recebe comandos via getUpdates."""

import asyncio
import html
from typing import Any, Dict, List, Optional

import aiohttp

from config import BOT_TOKEN, OWNER_ID

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


class Notifier:
    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._offset: Optional[int] = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

    async def _call(self, method: str, payload: Dict[str, Any], timeout: int = 30):
        assert self._session is not None, "Notifier.start() nao foi chamado"
        url = f"{API_BASE}/{method}"
        try:
            async with self._session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    print(f"[bot-api] {method} falhou: {data.get('description')}")
                    return None
                return data.get("result")
        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientError as exc:
            print(f"[bot-api] erro de rede em {method}: {exc}")
            return None

    async def send(
        self,
        text: str,
        chat_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id or OWNER_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._call("sendMessage", payload)

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        # inline_keyboard vazio remove os botoes; None mantem o campo de fora
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        await self._call("editMessageText", payload)

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        await self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    async def get_updates(self) -> List[Dict[str, Any]]:
        """Long polling. Retorna lista de updates (pode ser vazia)."""
        payload: Dict[str, Any] = {
            "timeout": 25,
            "allowed_updates": ["message", "callback_query"],
        }
        if self._offset is not None:
            payload["offset"] = self._offset
        result = await self._call("getUpdates", payload, timeout=40)
        if not result:
            return []
        self._offset = result[-1]["update_id"] + 1
        return result


def esc(text: str) -> str:
    """Escapa texto para o parse_mode HTML do Telegram."""
    return html.escape(text or "", quote=False)
