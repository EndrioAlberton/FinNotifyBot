"""Ponto de entrada: escuta grupos/canais e notifica quando bate uma palavra-chave."""

import asyncio
import hashlib
import signal
from typing import Any, Dict, Optional, Tuple

from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User

import db
from config import (
    API_HASH,
    API_ID,
    BOT_ID,
    DEDUPE_TTL_HOURS,
    FUZZY_THRESHOLD,
    MAX_ALERTS_PER_HOUR,
    OWNER_ID,
    SESSION_PATH,
    SNIPPET_CHARS,
)
from matcher import find_matches, normalize
from notifier import Notifier, esc

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
notifier = Notifier()
_shutdown = asyncio.Event()


# ------------------------------------------------------------------ helpers

def chat_title(chat: Any) -> str:
    if chat is None:
        return "desconhecido"
    if isinstance(chat, User):
        return " ".join(filter(None, [chat.first_name, chat.last_name])) or "privado"
    return getattr(chat, "title", None) or "desconhecido"


def message_link(chat: Any, msg_id: int) -> Optional[str]:
    """Link direto para a mensagem original."""
    if chat is None:
        return None
    username = getattr(chat, "username", None)
    if username:
        return f"https://t.me/{username}/{msg_id}"
    if isinstance(chat, Channel):
        # Channel.id no Telethon ja vem sem o prefixo -100
        return f"https://t.me/c/{chat.id}/{msg_id}"
    return None  # grupos legados (Chat) nao tem link publico


def snippet(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def digest_of(text_norm: str) -> str:
    return hashlib.sha256(text_norm.encode("utf-8")).hexdigest()[:32]


# ------------------------------------------------------------------ listener

@client.on(events.NewMessage(incoming=True))
async def on_message(event: events.NewMessage.Event) -> None:
    try:
        if event.sender_id == BOT_ID:
            return  # mensagem do proprio bot notificador (confirmacao/alerta) -> nao reescanear

        if db.is_paused():
            return

        raw = event.raw_text or ""   # cobre texto e legenda de foto
        if not raw.strip():
            return

        text_norm = normalize(raw)
        keywords = db.list_keywords()
        if not keywords:
            return

        matches = find_matches(text_norm, keywords, FUZZY_THRESHOLD)
        if not matches:
            return

        # Mesmo anuncio repostado em varios grupos -> notifica uma vez so
        if db.already_seen(digest_of(text_norm), DEDUPE_TTL_HOURS):
            return

        match = max(matches, key=lambda m: m.score)
        if not db.can_alert(match.term_norm, MAX_ALERTS_PER_HOUR):
            return
        db.record_alert(match.term_norm)

        chat = await event.get_chat()
        title = chat_title(chat)
        link = message_link(chat, event.id)

        tag = "\U0001F3AF" if match.kind == "exato" else "\U0001F50E"
        header = f"{tag} <b>{esc(match.term)}</b>"
        if match.kind == "aproximado":
            header += f" <i>(aproximado, {match.score}%)</i>"

        lines = [
            header,
            f"\U0001F4E2 {esc(title)}",
            "",
            esc(snippet(raw, SNIPPET_CHARS)),
        ]
        if link:
            lines += ["", f'<a href="{link}">Abrir mensagem original</a>']

        await notifier.send("\n".join(lines))

    except Exception as exc:  # nunca deixa uma mensagem derrubar o listener
        print(f"[listener] erro ao processar mensagem: {exc!r}")


# ------------------------------------------------------------------ comandos

HELP = (
    "<b>Comandos</b>\n"
    "/add termo - cadastra uma palavra-chave\n"
    "/list - lista os termos cadastrados\n"
    "/del id - remove pelo id mostrado em /list\n"
    "/test texto - simula uma mensagem e mostra o que casaria\n"
    "/stats - alertas das ultimas 24h\n"
    "/pause e /resume - liga e desliga as notificacoes\n"
    "/help - esta ajuda"
)


def build_list_payload(rows) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Monta o texto + teclado inline do /list, com um botao 'remover' por termo."""
    if not rows:
        return "Nenhum termo cadastrado. Use <code>/add armani code</code>", None
    text = "<b>Termos cadastrados</b>\nToque no X pra remover."
    keyboard = [
        [{"text": f"❌ {r['term']}", "callback_data": f"del:{r['id']}"}]
        for r in rows
    ]
    return text, {"inline_keyboard": keyboard}


async def handle_command(text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/start", "/help"):
        return HELP, None

    if cmd == "/add":
        if not arg:
            return "Uso: <code>/add armani code</code>", None
        term_norm = normalize(arg)
        if not term_norm:
            return "Termo invalido.", None
        if db.add_keyword(arg.strip(), term_norm):
            return f"Cadastrado: <b>{esc(arg.strip())}</b>", None
        return f"<b>{esc(arg.strip())}</b> ja estava cadastrado.", None

    if cmd == "/list":
        return build_list_payload(db.list_keywords())

    if cmd == "/del":
        if not arg.isdigit():
            return "Uso: <code>/del 3</code> (veja os ids em /list, ou toque no X)", None
        removed = db.delete_keyword(int(arg))
        if removed is None:
            return "Id nao encontrado.", None
        return f"Removido: <b>{esc(removed)}</b>", None

    if cmd == "/test":
        if not arg:
            return "Uso: <code>/test promo armanicode 100ml</code>", None
        matches = find_matches(normalize(arg), db.list_keywords(), FUZZY_THRESHOLD)
        if not matches:
            return "Nenhum termo casaria com esse texto.", None
        body = "\n".join(
            f"- <b>{esc(m.term)}</b> ({m.kind}, {m.score}%)" for m in matches
        )
        return f"<b>Casaria com:</b>\n{body}", None

    if cmd == "/stats":
        rows = db.stats_last_24h()
        if not rows:
            return "Nenhum alerta nas ultimas 24h.", None
        body = "\n".join(f"- {esc(term)}: {count}" for term, count in rows)
        return f"<b>Alertas nas ultimas 24h</b>\n{body}", None

    if cmd == "/pause":
        db.set_setting("paused", "1")
        return "Notificacoes pausadas. Use /resume para religar.", None

    if cmd == "/resume":
        db.set_setting("paused", "0")
        return "Notificacoes religadas.", None

    return "Comando desconhecido. Use /help", None


async def handle_callback(cq: Dict[str, Any]) -> None:
    """Trata o toque num botao inline (hoje, so o X de remover do /list)."""
    sender = (cq.get("from") or {}).get("id")
    cq_id = cq.get("id")
    data = cq.get("data") or ""
    message: Dict[str, Any] = cq.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")

    if sender != OWNER_ID:
        await notifier.answer_callback(cq_id, "Nao autorizado.")
        return

    if not data.startswith("del:") or not data[4:].isdigit():
        await notifier.answer_callback(cq_id)
        return

    removed = db.delete_keyword(int(data[4:]))
    await notifier.answer_callback(cq_id, f"Removido: {removed}" if removed else "Ja tinha sido removido.")

    if chat_id is not None and message_id is not None:
        text, markup = build_list_payload(db.list_keywords())
        await notifier.edit_message(chat_id, message_id, text, markup or {"inline_keyboard": []})


async def command_loop() -> None:
    while not _shutdown.is_set():
        try:
            updates = await notifier.get_updates()
            for update in updates:
                if "callback_query" in update:
                    await handle_callback(update["callback_query"])
                    continue

                message: Dict[str, Any] = update.get("message") or {}
                sender = (message.get("from") or {}).get("id")
                text = message.get("text") or ""
                if sender != OWNER_ID or not text.startswith("/"):
                    continue
                reply, markup = await handle_command(text)
                await notifier.send(reply, reply_markup=markup)
        except Exception as exc:
            print(f"[comandos] erro: {exc!r}")
            await asyncio.sleep(5)


# ------------------------------------------------------------------ startup

async def amain() -> None:
    db.conn()
    await notifier.start()
    await client.start()

    me = await client.get_me()
    dialogs = await client.get_dialogs()  # popula o cache de entidades (necessario p/ updates de canal chegarem)
    print(f"[ok] conectado como {me.first_name} (id {me.id}) - {len(dialogs)} conversas visiveis")
    await notifier.send(
        "\u2705 Monitor ligado. Use /help para ver os comandos."
    )

    task = asyncio.create_task(command_loop())
    try:
        await client.run_until_disconnected()
    finally:
        _shutdown.set()
        task.cancel()
        await notifier.close()


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: _shutdown.set())
        except NotImplementedError:
            pass  # Windows
    try:
        loop.run_until_complete(amain())
    except KeyboardInterrupt:
        print("\n[saindo]")


if __name__ == "__main__":
    main()
