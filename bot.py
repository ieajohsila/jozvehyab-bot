import nest_asyncio
nest_asyncio.apply()

import logging
import os
from datetime import datetime

# --- کتابخانه‌های دیتابیس ---
from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, String, 
                        BigInteger, DateTime, insert, select)

# --- کتابخانه‌های تلگرام برای منوها و مکالمه ---
from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton, 
                      InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.ext import (Application, CommandHandler, MessageHandler, filters, 
                          ContextTypes, ConversationHandler, CallbackQueryHandler)

# --- خواندن متغیرهای محیطی ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 0)) # تبدیل به عدد

# --- فعال کردن لاگ‌گیری ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- تعریف ساختار دیتابیس ---
engine = create_engine(DATABASE_URL)
metadata_obj = MetaData()

users_table = Table("users", metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("user_id", BigInteger, unique=True, nullable=False),
    Column("first_name", String(100)),
    Column("username", String(50)),
    Column("created_at", DateTime, default=datetime.utcnow),
)

documents_table = Table("documents", metadata_obj,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String(200), nullable=False),
    Column("price", Integer, default=0),
    Column("file_id", String(200), unique=True, nullable=False),
)

def create_tables():
    try:
        metadata_obj.create_all(engine)
        print("✅ جداول با موفقیت بررسی و ایجاد شدند.")
    except Exception as e:
        print(f"❌ خطا در ایجاد جداول: {e}")
        raise e

# --- تعریف حالات برای مکالمه افزودن جزوه ---
GET_FILE, GET_TITLE, GET_PRICE = range(3)

# ==================== توابع اصلی ربات ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    # ثبت کاربر در دیتابیس (اگر جدید باشد)
    try:
        with engine.connect() as connection:
            existing_user = connection.execute(select(users_table).where(users_table.c.user_id == user.id)).first()
            if not existing_user:
                stmt = insert(users_table).values(user_id=user.id, first_name=user.first_name, username=user.username)
                connection.execute(stmt)
                connection.commit()
                print(f"کاربر جدید ثبت شد: {user.id}")
    except Exception as e:
        print(f"❌ خطا در ثبت کاربر: {e}")

    # --- ساخت منوی اصلی ---
    keyboard = [
        [KeyboardButton("📚 لیست جزوات")]
    ]
    # اگر کاربر ادمین باشد، دکمه مدیریت اضافه می‌شود
    if user.id == ADMIN_USER_ID:
        keyboard.append([KeyboardButton("➕ افزودن جزوه")])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_html(
        f"سلام {user.mention_html()}! 👋\n\nبه ربات «جزوه‌یاب» خوش آمدید. لطفاً از منوی زیر یک گزینه را انتخاب کنید.",
        reply_markup=reply_markup
    )

async def list_documents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لیست تمام جزوات موجود را نمایش می‌دهد"""
    with engine.connect() as connection:
        documents = connection.execute(select(documents_table)).fetchall()

    if not documents:
        await update.message.reply_text("متاسفانه در حال حاضر هیچ جزوه‌ای در ربات موجود نیست.")
        return

    await update.message.reply_text("لیست جزوات موجود:")
    for doc in documents:
        # برای هر جزوه یک دکمه "دریافت" می‌سازیم
        keyboard = [[InlineKeyboardButton("📥 دریافت جزوه", callback_data=f"doc_{doc.id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # قالب نمایش قیمت
        price_text = "رایگان" if doc.price == 0 else f"{doc.price:,} تومان"
        
        message_text = f"📄 **عنوان:** {doc.title}\n💰 **قیمت:** {price_text}"
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ به کلیک روی دکمه‌های Inline (مثل دکمه دریافت جزوه)"""
    query = update.callback_query
    await query.answer() # به تلگرام میگوید که کلیک را دریافت کرده
    
    data = query.data
    if data.startswith("doc_"):
        doc_id = int(data.split("_")[1])
        
        with engine.connect() as connection:
            document = connection.execute(select(documents_table).where(documents_table.c.id == doc_id)).first()

        if document:
            await context.bot.send_document(chat_id=query.effective_chat.id, document=document.file_id)
        else:
            await query.edit_message_text(text="متاسفانه این جزوه یافت نشد.")

# --- توابع مربوط به مکالمه افزودن جزوه (مخصوص ادمین) ---

async def add_document_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع فرآیند افزودن جزوه"""
    if update.effective_user.id != ADMIN_USER_ID:
        return ConversationHandler.END

    await update.message.reply_text("لطفاً فایل جزوه (PDF) را ارسال کنید. برای لغو /cancel را بزنید.")
    return GET_FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت فایل و درخواست عنوان"""
    if not update.message.document:
        await update.message.reply_text("لطفا فقط فایل ارسال کنید. برای لغو /cancel را بزنید.")
        return GET_FILE
        
    context.user_data['file_id'] = update.message.document.file_id
    await update.message.reply_text("عالی! حالا عنوان جزوه را وارد کنید.")
    return GET_TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت عنوان و درخواست قیمت"""
    context.user_data['title'] = update.message.text
    await update.message.reply_text("بسیار خب. حالا قیمت جزوه را به تومان وارد کنید (فقط عدد). برای جزوه رایگان، عدد 0 را وارد کنید.")
    return GET_PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دریافت قیمت و ذخیره نهایی جزوه در دیتابیس"""
    try:
        price = int(update.message.text)
    except ValueError:
        await update.message.reply_text("لطفاً فقط عدد وارد کنید. قیمت به تومان:")
        return GET_PRICE

    # --- ذخیره در دیتابیس ---
    try:
        with engine.connect() as connection:
            stmt = insert(documents_table).values(
                title=context.user_data['title'],
                price=price,
                file_id=context.user_data['file_id']
            )
            connection.execute(stmt)
            connection.commit()
        await update.message.reply_text("✅ جزوه با موفقیت به ربات اضافه شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ یک خطای غیرمنتظره در ذخیره جزوه رخ داد: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """لغو فرآیند افزودن جزوه"""
    await update.message.reply_text("عملیات افزودن جزوه لغو شد.")
    context.user_data.clear()
    return ConversationHandler.END

# ==================== تابع اصلی و اجرای ربات ====================

def main() -> None:
    # 1. بررسی و ایجاد جداول
    create_tables()

    # 2. بررسی متغیرهای محیطی
    if not all([TELEGRAM_BOT_TOKEN, DATABASE_URL, ADMIN_USER_ID]):
        print("❌ خطا: یک یا چند متغیر محیطی (Token, DB URL, Admin ID) تنظیم نشده‌اند.")
        return
        
    # 3. ساخت و تنظیم ربات
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- تعریف مکالمه برای افزودن جزوه ---
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ افزودن جزوه$'), add_document_start)],
        states={
            GET_FILE: [MessageHandler(filters.Document.PDF, get_file)],
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # 4. ثبت تمام دستورات و کنترل‌کننده‌ها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('^📚 لیست جزوات$'), list_documents))
    application.add_handler(conv_handler) # ثبت مکالمه
    application.add_handler(CallbackQueryHandler(button_callback)) # ثبت پاسخ به دکمه‌ها

    # 5. اجرای ربات
    print("ربات «جزوه‌یاب» با تمام قابلیت‌های جدید آماده به کار است...")
    application.run_polling()

if __name__ == "__main__":
    main()
