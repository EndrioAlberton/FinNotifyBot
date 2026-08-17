"""Descobre o seu user id numerico (para preencher TG_OWNER_ID no .env)."""

import asyncio

from telethon import TelegramClient

from config import API_HASH, API_ID, SESSION_PATH


async def main() -> None:
    async with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"\nSeu TG_OWNER_ID e: {me.id}\n")


if __name__ == "__main__":
    asyncio.run(main())
