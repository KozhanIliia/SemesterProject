import os
from pathlib import Path
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, \
    ConversationHandler
from gmail_service import GmailService
from db_manager import init_db, save_email
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / '.env'
load_dotenv(dotenv_path=ENV_PATH)

RECIPIENT, SUBJECT, BODY = range(3)

init_db()
try:
    gmail = GmailService()
except Exception as e:
    print(f"Критична помилка ініціалізації Gmail: {e}")
    gmail = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['📩 Вхідні', '✍️ Написати листа']]
    await update.message.reply_text(
        "Привіт! Я твій Gmail-бот. Що будемо робити?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def check_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not gmail:
        await update.message.reply_text("❌ Помилка авторизації Gmail.")
        return

    await update.message.reply_text("🔄 Перевіряю пошту...")
    emails = gmail.get_latest_emails(5)

    if not emails:
        await update.message.reply_text("📭 Вхідні пусті або помилка доступу.")
        return

    response_text = "📬 **Останні 5 листів:**\n\n"

    # Зберігаємо ID листів у пам'яті (context.user_data), щоб дістати їх при кліку
    context.user_data['last_emails'] = {}

    buttons_row = []

    for i, mail in enumerate(emails):
        # Зберігаємо в БД
        save_email(mail['id'], mail['sender'], mail['subject'], mail['snippet'])

        idx = str(i + 1)
        # Кешуємо ID листа
        context.user_data['last_emails'][idx] = mail['id']

        # Формуємо текст списку
        response_text += f"{idx}. 👤 **Від:** {mail['sender']}\n📝 **Тема:** {mail['subject']}\n📎 {mail['snippet'][:50]}...\n\n"

        # Додаємо кнопку
        buttons_row.append(InlineKeyboardButton(f"📖 {idx}", callback_data=f"read_{idx}"))

    response_text += "👇 *Натисніть на номер листа, щоб прочитати повністю:*"

    # Додаємо клавіатуру з кнопками
    reply_markup = InlineKeyboardMarkup([buttons_row])

    await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)


# --- Нова функція: Обробка натискання на кнопку "Читати" ---
async def read_email_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Прибирає годинничок завантаження на кнопці

    # Отримуємо номер листа з callback_data (наприклад "read_1" -> "1")
    idx = query.data.split("_")[1]

    # Шукаємо реальний ID листа в пам'яті
    email_id = context.user_data.get('last_emails', {}).get(idx)

    if not email_id:
        await query.edit_message_text("⚠️ Список застарів. Оновіть вхідні ще раз.")
        return

    await query.message.reply_text("🔄 Завантажую повний текст...")

    full_text = gmail.get_full_message_text(email_id)

    # Обрізаємо, якщо текст занадто довгий для Telegram (ліміт ~4096)
    if len(full_text) > 4000:
        full_text = full_text[:4000] + "\n\n... (Текст скорочено)"

    await query.message.reply_text(f"📄 **Лист №{idx}**\n\n{full_text}")


async def start_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть email отримувача:", reply_markup=ReplyKeyboardRemove())
    return RECIPIENT


async def get_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['recipient'] = update.message.text
    await update.message.reply_text("Введіть тему листа:")
    return SUBJECT


async def get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['subject'] = update.message.text
    await update.message.reply_text("Введіть текст повідомлення:")
    return BODY


async def send_email_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not gmail:
        await update.message.reply_text("❌ Помилка сервісу.")
        return ConversationHandler.END

    recipient = context.user_data['recipient']
    subject = context.user_data['subject']
    body = update.message.text

    await update.message.reply_text("🚀 Відправляю...")
    result = gmail.send_message(recipient, subject, body)

    keyboard = [['📩 Вхідні', '✍️ Написати листа']]
    if result:
        await update.message.reply_text("✅ Лист успішно надіслано!",
                                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await update.message.reply_text("❌ Помилка при відправці.",
                                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Дію скасовано.",
                                    reply_markup=ReplyKeyboardMarkup([['📩 Вхідні', '✍️ Написати листа']],
                                                                     resize_keyboard=True))
    return ConversationHandler.END


async def run_bot():
    load_dotenv(dotenv_path=ENV_PATH)
    token = os.environ.get("TELEGRAM_TOKEN")

    if not token:
        print("\n" + "=" * 40 + "\n❌ ПОМИЛКА: Токен не знайдено!\n" + "=" * 40 + "\n")
        return

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^✍️ Написати листа$'), start_email)],
        states={
            RECIPIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_recipient)],
            SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subject)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_email_finish)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('^📩 Вхідні$'), check_inbox))

    # Додаємо обробник для кнопок "Читати" (всі callback_data, що починаються на "read_")
    application.add_handler(CallbackQueryHandler(read_email_callback, pattern="^read_"))

    application.add_handler(conv_handler)

    await application.run_polling()