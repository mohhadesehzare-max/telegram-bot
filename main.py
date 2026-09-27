import os
import threading
import tempfile
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from groq import Groq

TOKEN = "8977278269:AAH4NSZRyu_X2L5ea1hLEBU0LP5DpWvftss"
GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)

MODELS_TO_TRY = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "mixtral-8x7b-32768",
    "openai/gpt-oss-20b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

PERSIAN_PROMPT = "این فایل صوتی درباره کتاب، درس، تدریس، ریاضی، فیزیک، شیمی، زیست، پزشکی، مهندسی، برنامه‌نویسی، ادبیات، تاریخ، اقتصاد، حقوق، فلسفه، روانشناسی، مدیریت، اصطلاحات علمی، تخصصی و دانشگاهی است. کلمات را با املای صحیح فارسی بنویس."
ENGLISH_PROMPT = "This audio is about a course, book, teaching, mathematics, physics, chemistry, biology, medicine, engineering, programming, literature, history, economics, law, philosophy, psychology, management, and academic technical terms. Please transcribe accurately."

def call_ai(messages, temperature=0):
    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_error = str(e)
            continue
    return f"[خطا: هیچ مدلی جواب نداد. آخرین خطا: {last_error}]"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data='lang_fa')],
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
    ]
    await update.message.reply_text(
        "سلام! لطفاً زبان فایل صوتی خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split('_')[1]
    context.user_data['language'] = lang
    lang_name = "فارسی" if lang == 'fa' else "English"
    await query.edit_message_text(
        f"✅ زبان انتخاب شد: {lang_name}\n\nحالا فایل صوتی یا ویس خود را بفرستید."
    )

def transcribe_audio(path: str, language: str) -> str:
    prompt = PERSIAN_PROMPT if language == 'fa' else ENGLISH_PROMPT
    with open(path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(os.path.basename(path), f.read()),
            model="whisper-large-v3",
            language=language,
            prompt=prompt,
            response_format="text",
            temperature=0,
        )
    return result.strip()

def fix_persian_text(text: str) -> str:
    if not text.strip():
        return text
    chunks = [text[i:i + 3000] for i in range(0, len(text), 3000)]
    fixed_chunks = []
    for chunk in chunks:
        result = call_ai([
            {"role": "system", "content": "تو یک ویراستار حرفه‌ای فارسی هستی. متن زیر را ویرایش کن: غلط‌های املایی را اصلاح کن، فاصله و نیم‌فاصله‌ها را درست کن، حروف عربی (ي، ك، ة) را به فارسی (ی، ک، ه) تبدیل کن، اما معنی و اصطلاحات تخصصی را تغییر نده. فقط متن ویرایش‌شده را برگردان، بدون هیچ توضیح اضافه."},
            {"role": "user", "content": chunk}
        ])
        fixed_chunks.append(result)
    return "\n".join(fixed_chunks)

def translate_text(text: str, target_lang: str) -> str:
    if target_lang == 'fa':
        instruction = "متن زیر را به فارسی روان و دقیق ترجمه کن. اصطلاحات تخصصی و علمی را حفظ کن و بدون غلط املایی بنویس. فقط خود ترجمه را بنویس و هیچ توضیح اضافه‌ای نده:\n\n"
    else:
        instruction = "Translate the following text into fluent and accurate English. Keep technical and academic terms. Only output the translation and nothing else:\n\n"
    chunks = [text[i:i + 3000] for i in range(0, len(text), 3000)]
    translated_chunks = []
    for chunk in chunks:
        result = call_ai([{"role": "user", "content": instruction + chunk}])
        translated_chunks.append(result)
    return "\n".join(translated_chunks)

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    lang = context.user_data.get('language')
    if not lang:
        await msg.reply_text("لطفاً ابتدا دستور /start را بزنید و زبان را انتخاب کنید.")
        return

    file = None
    suffix = ".ogg"
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

    await msg.reply_text("📥 دریافت شد. در حال پردازش...")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    try:
        await file.download_to_drive(custom_path=tmp.name)

        text = await asyncio.to_thread(transcribe_audio, tmp.name, lang)
        if not text:
            await msg.reply_text("❌ چیزی تشخیص داده نشد.")
            return

        if lang == 'fa':
            await msg.reply_text("✏️ در حال ویرایش و اصلاح متن...")
            text = await asyncio.to_thread(fix_persian_text, text)

        context.user_data['last_text'] = text
        context.user_data['last_lang'] = lang

        for i in range(0, len(text), 4000):
            await msg.reply_text(text[i:i + 4000])

        buttons = []
        if lang == 'fa':
            buttons.append([InlineKeyboardButton("🌐 ترجمه به انگلیسی", callback_data='trans_en')])
        else:
            buttons.append([InlineKeyboardButton("🌐 ترجمه به فارسی", callback_data='trans_fa')])

        await msg.reply_text(
            "برای ترجمه، روی دکمه زیر بزنید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        await msg.reply_text(f"❌ خطا: {e}")
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

async def translate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[1]
    text = context.user_data.get('last_text')

    if not text:
        await query.edit_message_text("❌ متنی برای ترجمه پیدا نشد.")
        return

    await query.edit_message_text("⏳ در حال ترجمه...")
    try:
        translated = await asyncio.to_thread(translate_text, text, target)
        label = "🌐 ترجمه انگلیسی" if target == 'en' else "🌐 ترجمه فارسی"
        for i in range(0, len(translated), 4000):
            await query.message.reply_text(f"{label}:\n\n{translated[i:i + 4000]}")
        await query.delete_message()
    except Exception as e:
        await query.edit_message_text(f"❌ خطا در ترجمه: {e}")

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
    app.add_handler(CallbackQueryHandler(language_selected, pattern='^lang_'))
    app.add_handler(CallbackQueryHandler(translate_callback, pattern='^trans_'))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.Document.AUDIO, handle_audio
    ))
    print("bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
