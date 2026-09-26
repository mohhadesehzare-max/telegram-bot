import os
import threading
import tempfile
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# توکن ربات جدید شما
TOKEN = "8977278269:AAH4NSZRyu_X2L5ea1hLEBU0LP5DpWvftss"

# کلید Groq شما
GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! یک ویس یا فایل صوتی بفرست تا متنش کنم.")

def transcribe_file(path: str) -> str:
    with open(path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(path), audio_file.read()),
            model="whisper-large-v3",
            response_format="text",
            language="fa",
        )
    return transcription.strip()

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    file = None
    suffix = ".ogg"  # برای سازگاری با Groq
    
    if msg.voice:
        file = await msg.voice.get_file()
    elif msg.audio:
        file = await msg.audio.get_file()
        suffix = os.path.splitext(msg.audio.file_name or "")[1] or ".mp3"
    elif msg.document and (msg.document.mime_type or "").startswith("audio/"):
        file = await msg.document.get_file()
        suffix = os.path.splitext(msg.document.file_name or "")[1] or ".mp3"
    else:
        return
    await msg.reply_text("دریافت شد، دارم تبدیل می‌کنم...")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    try:
        await file.download_to_drive(custom_path=tmp.name)
        text = await asyncio.to_thread(transcribe_file, tmp.name)
        if not text:
            await msg.reply_text("چیزی تشخیص داده نشد.")
            return
        for i in range(0, len(text), 4000):
            await msg.reply_text(text[i:i + 4000])
    except Exception as e:
        await msg.reply_text(f"خطا: {e}")
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

def run_web():
    port = int(os.environ.get("PORT", 8080))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"bot is alive")
    HTTPServer(("0.0.0.0", port), H).serve_forever()

def main():
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.Document.AUDIO, handle_audio))
    print("bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
