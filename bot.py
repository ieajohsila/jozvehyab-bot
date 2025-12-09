import nest_asyncio
nest_asyncio.apply()

import logging
import os  # <-- این ماژول برای خواندن متغیرهای محیطی اضافه شد
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- تغییر در اینجا اعمال شده است ---
# توکن دیگر مستقیما در کد نیست، بلکه از محیط خوانده می‌شود
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

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
        f"به ربات «جزوه‌یاب» خوش آمدید. من آماده‌ام تا به شما کمک کنم.",
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تکرار پیام کاربر"""
    await update.message.reply_text("این یک ربات آزمایشی است.")


def main() -> None:
    """اجرای اصلی ربات"""
    if not TELEGRAM_BOT_TOKEN:
        print("خطا: توکن تلگرام در متغیرهای محیطی یافت نشد.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("ربات «جزوه‌یاب» با موفقیت اجرا شد...")
    application.run_polling()


if __name__ == "__main__":
    main()
