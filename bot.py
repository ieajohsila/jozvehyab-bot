import nest_asyncio
nest_asyncio.apply()

import logging
import os
from datetime import datetime # <-- برای ثبت زمان اضافه شد

# --- شروع بخش کتابخانه‌های دیتابیس ---
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, BigInteger, DateTime, insert
# --- پایان بخش کتابخانه‌های دیتابیس ---

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# خواندن متغیرهای محیطی
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# فعال کردن لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- شروع بخش تعریف ساختار دیتابیس ---
engine = create_engine(DATABASE_URL)
metadata_obj = MetaData()

# تعریف جدول کاربران
users_table = Table(
    "users",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, unique=True, nullable=False),
    Column("first_name", String(100)),
    Column("username", String(50)),
    Column("created_at", DateTime, default=datetime.utcnow),
)

# تعریف جدول جزوات
documents_table = Table(
    "documents",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("title", String(200), nullable=False),
    Column("description", String(500)),
    Column("price", Integer, default=0),
    Column("file_id", String(200), unique=True), # <-- برای ذخیره فایل در تلگرام
)

def create_tables():
    """این تابع جداول را در دیتابیس ایجاد می‌کند (اگر وجود نداشته باشند)"""
    try:
        metadata_obj.create_all(engine)
        print("✅ جداول 'users' و 'documents' با موفقیت بررسی و ایجاد شدند.")
    except Exception as e:
        print(f"❌ خطا در ایجاد جداول: {e}")
        raise e
# --- پایان بخش تعریف ساختار دیتابیس ---


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ به دستور /start و ثبت کاربر در دیتابیس"""
    user = update.effective_user
    
    # --- شروع بخش ثبت کاربر ---
    try:
        with engine.connect() as connection:
            # چک میکنیم کاربر از قبل وجود دارد یا نه
            existing_user = connection.execute(
                users_table.select().where(users_table.c.user_id == user.id)
            ).first()

            if not existing_user:
                # اگر کاربر جدید بود، او را اضافه میکنیم
                stmt = insert(users_table).values(
                    user_id=user.id,
                    first_name=user.first_name,
                    username=user.username
                )
                connection.execute(stmt)
                connection.commit()
                print(f"کاربر جدید ثبت شد: {user.id} - {user.first_name}")

    except Exception as e:
        print(f"❌ خطا در ثبت کاربر: {e}")
    # --- پایان بخش ثبت کاربر ---

    await update.message.reply_html(
        f"سلام {user.mention_html()}! 👋\n\n"
        f"به ربات «جزوه‌یاب» خوش آمدید.",
    )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("ربات در حال توسعه است...")


def main() -> None:
    # اول جداول را ایجاد یا بررسی میکنیم
    create_tables()

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
