from telethon import TelegramClient, events
import asyncio
import os
from dotenv import load_dotenv
from telethon.network import connection
load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
handler = os.getenv("HANDLER", ".saveit")

client = TelegramClient(
    "save", 
    api_id, 
    api_hash,
    connection=connection.ConnectionTcpAbridged
)
your_user_id = None

# Isi chat yang boleh dipantau.
# Contoh:
# ALLOWED_CHATS = {123456789, -1009876543210}
ALLOWED_CHATS = {1230120835,1193779817}

# Biar tidak dobel save pesan yang sama
processed_messages = set()

# Delay kecil biar lebih natural
AUTO_DELAY_SECONDS = 2


def has_ttl_media(msg) -> bool:
    if not msg or not msg.media:
        return False

    # Cek ttl_seconds di berbagai kemungkinan objek
    if getattr(msg, "ttl_period", None):
        return True

    media = msg.media
    if getattr(media, "ttl_seconds", None):
        return True

    photo = getattr(media, "photo", None)
    if photo and getattr(photo, "ttl_seconds", None):
        return True

    document = getattr(media, "document", None)
    if document and getattr(document, "ttl_seconds", None):
        return True

    return False


def is_supported_media(msg) -> bool:
    if not msg or not msg.media:
        return False

    media = msg.media
    if hasattr(media, "photo"):
        return True
    if hasattr(media, "document"):
        return True
    return False


async def save_message_media(msg, source="auto"):
    global processed_messages

    if not msg or not msg.media:
        return False, "No media found."

    key = (msg.chat_id, msg.id)
    if key in processed_messages:
        return False, "Already processed."

    if not is_supported_media(msg):
        return False, "Unsupported media type."

    download_path = "downloads"
    os.makedirs(download_path, exist_ok=True)

    try:
        file_path = await client.download_media(msg, file=download_path)
        if not file_path:
            return False, "Download failed."
    except Exception as err:
        return False, f"Failed to download: {err}"

    sender_id = getattr(msg, "sender_id", "unknown")

    try:
        await client.send_file(
            "me",
            file_path,
            caption=f"[{source}] File saved from {sender_id} | chat_id={msg.chat_id} | msg_id={msg.id}",
            force_document=True,
        )
    except Exception as err:
        return False, f"Failed to send to Saved Messages: {err}"

    processed_messages.add(key)
    return True, file_path


@client.on(events.NewMessage(pattern=rf"\{handler}"))
async def manual_save(event):
    global your_user_id

    if your_user_id is None:
        me = await client.get_me()
        your_user_id = me.id

    if event.sender_id != your_user_id:
        return

    status = await event.client.send_message(event.sender_id, "Downloading...")

    if not event.reply_to_msg_id:
        await status.edit("Reply ke message media yang mau disimpan.")
        return

    msg = await event.get_reply_message()
    await event.delete()

    ok, result = await save_message_media(msg, source="manual")
    if ok:
        await status.delete()
    else:
        await status.edit(result)


@client.on(events.NewMessage(incoming=True))
async def semi_auto_save(event):
    global your_user_id

    if your_user_id is None:
        me = await client.get_me()
        your_user_id = me.id

    msg = event.message
    print(f"[DEBUG] Pesan masuk dari chat_id={event.chat_id}, sender_id={event.sender_id}, has_media={bool(msg.media)}")

    # Jangan proses pesan dari diri sendiri
    if event.sender_id == your_user_id:
        return

    # Wajib batasi chat
    if ALLOWED_CHATS and event.chat_id not in ALLOWED_CHATS:
        print(f"[DEBUG] Dilewati: chat_id {event.chat_id} tidak ada di ALLOWED_CHATS")
        return

    # Hanya media TTL / sekali lihat
    if not has_ttl_media(msg):
        print(f"[DEBUG] Dilewati: Media bukan tipe TTL/sekali lihat")
        return

    # Hanya media yang didukung
    if not is_supported_media(msg):
        return

    print("[DEBUG] Media TTL terdeteksi! Memproses download...")
    await asyncio.sleep(AUTO_DELAY_SECONDS)
    await save_message_media(msg, source="semi-auto")


async def main():
    print(">>> Menghubungkan ke Telegram...", flush=True)
    async with client:
        global your_user_id
        me = await client.get_me()
        your_user_id = me.id
        print(f"Running as: {me.username} (ID: {your_user_id})")
        print(f"Allowed chats: {ALLOWED_CHATS if ALLOWED_CHATS else 'ALL DISABLED - isi dulu ALLOWED_CHATS'}")
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())