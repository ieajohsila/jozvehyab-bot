import nest_asyncio
nest_asyncio.apply()

import logging
import os
from sqlalchemy import create_engine # <-- کتابخانه دیتابیس اضافه شد
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# خواندن متغیرهای محیطی
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL") # <-- آدرس دیتابیس خوانده شد

# فعال کردن لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ به دستور /start"""
    user = update.effective_user
    await update.message.reply_html(
        f"سلام {user.mention_html()}! 👋\n\n"
        f"به ربات «جزوه‌یاب» خوش آمدید.",
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تکرار پیام کاربر"""
    await update.message.reply_text("ربات در حال توسعه است...")


def main() -> None:
    """اجرای اصلی ربات"""
    # --- شروع بخش تست اتصال به دیتابیس ---
    if not DATABASE_URL:
        print("❌ خطا: آدرس اتصال دیتابیس (DATABASE_URL) یافت نشد.")
        return

    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
        print("✅ اتصال به پایگاه داده با موفقیت برقرار شد.")
        connection.close()
    except Exception as e:
        print(f"❌ خطا در اتصال به پایگاه داده: {e}")
        return
    # --- پایان بخش تست اتصال به دیتابیس ---

    if not TELEGRAM_BOT_TOKEN:
        print("❌ خطا: توکن تلگرام یافت نشد.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("ربات «جزوه‌یاب» آماده به کار است...")
    application.run_polling()


if __name__ == "__main__":
    main()
