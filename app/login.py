"""Executar UMA vez para gerar o arquivo de sessao (data/user.session)."""

import asyncio

from telethon import TelegramClient

from config import API_HASH, API_ID, SESSION_PATH


async def main() -> None:
    async with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"\nSessao criada com sucesso para: {me.first_name} (id {me.id})")
        print(f"Arquivo: {SESSION_PATH}.session")
        print("Guarde esse arquivo com o mesmo cuidado de uma senha.\n")


if __name__ == "__main__":
    asyncio.run(main())
