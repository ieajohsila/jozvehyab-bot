import nest_asyncio
nest_asyncio.apply()

import logging
import os
from datetime import datetime, timedelta

# --- کتابخانه‌های دیتابیس ---
from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, String, 
                        BigInteger, DateTime, select, update)
from sqlalchemy.orm import declarative_base

# --- کتابخانه‌های تلگرام ---
from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice,
                      InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.ext import (Application, CommandHandler, MessageHandler, filters, 
                          ContextTypes, ConversationHandler, CallbackQueryHandler, 
                          PreCheckoutQueryHandler)

# --- خواندن متغیرهای محیطی ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 0))

# --- فعال کردن لاگ‌گیری ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- تعریف ساختار دیتابیس با SQLAlchemy ---
Base = declarative_base()
engine = create_engine(DATABASE_URL)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    first_name = Column(String(100), nullable=True)
    username = Column(String(50), nullable=True)
    subscription_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    price = Column(Integer, default=0)
    file_id = Column(String(200), unique=True, nullable=False)

def create_tables():
    try:
        Base.metadata.create_all(engine)
        print("✅ جداول با موفقیت بررسی و ایجاد شدند.")
    except Exception as e:
        print(f"❌ خطا در ایجاد جداول: {e}")
        raise e

# --- تعریف حالات برای مکالمه افزودن جزوه ---
GET_FILE, GET_TITLE, GET_PRICE = range(3)

# ==================== توابع اصلی ربات ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    try:
        with engine.connect() as connection:
            user_table = User.__table__
            existing_user = connection.execute(select(user_table).where(user_table.c.user_id == user.id)).first()
            if not existing_user:
                stmt = user_table.insert().values(user_id=user.id, first_name=user.first_name, username=user.username)
                connection.execute(stmt)
                connection.commit()
                print(f"کاربر جدید ثبت شد: {user.id}")
    except Exception as e:
        print(f"❌ خطا در ثبت کاربر: {e}")

    keyboard = [
        [KeyboardButton("📚 لیست جزوات"), KeyboardButton("⭐ خرید اشتراک")]
    ]
    if user.id == ADMIN_USER_ID:
        keyboard.append([KeyboardButton("➕ افزودن جزوه")])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_html(
        f"سلام {user.mention_html()}! 👋\n\nبه ربات «جزوه‌یاب» خوش آمدید. لطفاً از منوی زیر یک گزینه را انتخاب کنید.",
        reply_markup=reply_markup
    )

async def list_documents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with engine.connect() as connection:
        doc_table = Document.__table__
        documents = connection.execute(select(doc_table)).fetchall()

    if not documents:
        await update.message.reply_text("متاسفانه در حال حاضر هیچ جزوه‌ای در ربات موجود نیست.")
        return

    await update.message.reply_text("لیست جزوات موجود:")
    for doc in documents:
        keyboard = [[InlineKeyboardButton("📥 دریافت جزوه", callback_data=f"doc_{doc.id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        price_text = "رایگان" if doc.price == 0 else f"{doc.price:,} تومان"
        message_text = f"📄 **عنوان:** {doc.title}\n💰 **قیمت:** {price_text}"
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    with engine.connect() as connection:
        user_table = User.__table__
        user_record = connection.execute(select(user_table).where(user_table.c.user_id == query.effective_user.id)).first()
    
    is_subscribed = user_record and user_record.subscription_expires and user_record.subscription_expires > datetime.utcnow()

    if not is_subscribed:
        await query.message.reply_text("❌ برای دسترسی به جزوات، ابتدا باید اشتراک تهیه کنید.\n\nلطفاً از منوی اصلی دکمه «⭐ خرید اشتراک» را انتخاب کنید.")
        return

    data = query.data
    if data.startswith("doc_"):
        doc_id = int(data.split("_")[1])
        with engine.connect() as connection:
            doc_table = Document.__table__
            document = connection.execute(select(doc_table).where(doc_table.c.id == doc_id)).first()

        if document:
            try:
                await context.bot.send_document(chat_id=query.effective_chat.id, document=document.file_id)
            except Exception as e:
                await query.message.reply_text(f"خطا در ارسال فایل: {e}")
        else:
            await query.edit_message_text(text="متاسفانه این جزوه یافت نشد.")

# --- توابع پرداخت با استار ---

async def show_subscription_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("⭐ ۱ ماهه (۱۰۰ استار)", callback_data="subscribe_1_100")],
        [InlineKeyboardButton("⭐ ۳ ماهه (۲۵۰ استار)", callback_data="subscribe_3_250")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفاً یکی از پلن‌های اشتراک زیر را انتخاب کنید:", reply_markup=reply_markup)

async def subscription_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, months, stars = query.data.split('_')
    title = f"اشتراک {months} ماهه جزوه‌یاب"
    description = f"دسترسی کامل به تمام جزوات به مدت {months} ماه"
    payload = f"jozvehyab-sub-{months}m"
    await context.bot.send_invoice(
        chat_id=query.effective_chat.id, title=title, description=description,
        payload=payload, currency="XTR", prices=[LabeledPrice(f"{months} ماه", int(stars))]
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload.startswith('jozvehyab-sub-'):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="مشکلی در پرداخت پیش آمده است.")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = update.message.successful_payment.invoice_payload
    months = int(payload.split('-')[2][:-1])
    user_id = update.effective_user.id

    with engine.connect() as connection:
        user_table = User.__table__
        user_record = connection.execute(select(user_table).where(user_table.c.user_id == user_id)).first()
        current_expiry = (user_record.subscription_expires if (user_record and user_record.subscription_expires and user_record.subscription_expires > datetime.utcnow()) else datetime.utcnow())
        new_expiry_date = current_expiry + timedelta(days=30 * months)
        stmt = update(user_table).where(user_table.c.user_id == user_id).values(subscription_expires=new_expiry_date)
        connection.execute(stmt)
        connection.commit()
    await update.message.reply_text(f"✅ پرداخت شما با موفقیت انجام شد! اشتراک شما تا تاریخ {new_expiry_date.strftime('%Y-%m-%d')} تمدید شد.")

# --- توابع مکالمه افزودن جزوه ---

async def add_document_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != ADMIN_USER_ID: return ConversationHandler.END
    await update.message.reply_text("لطفاً فایل جزوه (PDF) را ارسال کنید. برای لغو /cancel را بزنید.")
    return GET_FILE

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.document:
        await update.message.reply_text("لطفا فقط فایل PDF ارسال کنید. برای لغو /cancel را بزنید.")
        return GET_FILE
    context.user_data['file_id'] = update.message.document.file_id
    await update.message.reply_text("عالی! حالا عنوان جزوه را وارد کنید.")
    return GET_TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title'] = update.message.text
    await update.message.reply_text("بسیار خب. حالا قیمت تکی جزوه را وارد کنید (فقط عدد). برای رایگان، 0 را بزنید.")
    return GET_PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = int(update.message.text)
        with engine.connect() as connection:
            doc_table = Document.__table__
            stmt = doc_table.insert().values(title=context.user_data['title'], price=price, file_id=context.user_data['file_id'])
            connection.execute(stmt)
            connection.commit()
        await update.message.reply_text("✅ جزوه با موفقیت به ربات اضافه شد.")
    except ValueError:
        await update.message.reply_text("لطفاً فقط عدد وارد کنید.")
        return GET_PRICE
    except Exception as e:
        await update.message.reply_text(f"❌ یک خطای غیرمنتظره در ذخیره جزوه رخ داد: {e}")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.")
    context.user_data.clear()
    return ConversationHandler.END

# ==================== تابع اصلی و اجرای ربات ====================

def main() -> None:
    create_tables()
    if not all([TELEGRAM_BOT_TOKEN, DATABASE_URL, ADMIN_USER_ID]):
        print("❌ خطا: یک یا چند متغیر محیطی تنظیم نشده‌اند.")
        return
        
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ افزودن جزوه$') & filters.User(user_id=ADMIN_USER_ID), add_document_start)],
        states={
            GET_FILE: [MessageHandler(filters.Document.PDF, get_file)],
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('^📚 لیست جزوات$'), list_documents))
    application.add_handler(MessageHandler(filters.Regex('^⭐ خرید اشتراک$'), show_subscription_options))
    application.add_handler(CallbackQueryHandler(subscription_invoice, pattern='^subscribe_'))
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^doc_'))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(conv_handler)
    
    print("ربات «جزوه‌یاب» با قابلیت پرداخت استار آماده به کار است...")
    application.run_polling()

if __name__ == "__main__":
    main()
