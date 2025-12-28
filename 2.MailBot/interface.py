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
    print(f"Помилка ініціалізації сервісу: {e}")
    gmail = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['Оновити вхідні', 'Написати лист']]
    await update.message.reply_text(
        "Головне меню. Оберіть дію:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def check_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not gmail:
        await update.message.reply_text("Помилка авторизації.")
        return

    await update.message.reply_text("Завантаження даних...")
    emails = gmail.get_latest_emails(5)

    if not emails:
        await update.message.reply_text("Вхідні пусті або відсутній доступ.")
        return

    response_text = "**Список останніх повідомлень:**\n\n"

    context.user_data['last_emails'] = {}
    buttons_row = []

    for i, mail in enumerate(emails):
        # Збереження в локальну БД
        save_email(mail['id'], mail['sender'], mail['subject'], mail['snippet'])

        idx = str(i + 1)
        context.user_data['last_emails'][idx] = mail['id']

        response_text += f"{idx}. Від: {mail['sender']}\nТема: {mail['subject']}\nЗміст: {mail['snippet'][:50]}...\n\n"
        buttons_row.append(InlineKeyboardButton(f"Читати {idx}", callback_data=f"read_{idx}"))

    response_text += "*Оберіть лист для перегляду:*"

    reply_markup = InlineKeyboardMarkup([buttons_row])
    await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)


async def read_email_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    idx = query.data.split("_")[1]
    email_id = context.user_data.get('last_emails', {}).get(idx)

    if not email_id:
        await query.edit_message_text("Дані застаріли. Оновіть список.")
        return

    await query.message.reply_text("Отримання тексту...")

    full_text = gmail.get_full_message_text(email_id)

    if len(full_text) > 4000:
        full_text = full_text[:4000] + "\n\n[Текст скорочено]"

    await query.message.reply_text(f"**Лист №{idx}**\n\n{full_text}", parse_mode='Markdown')


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
        await update.message.reply_text("Сервіс недоступний.")
        return ConversationHandler.END

    recipient = context.user_data['recipient']
    subject = context.user_data['subject']
    body = update.message.text

    await update.message.reply_text("Виконується відправка...")
    result = gmail.send_message(recipient, subject, body)

    keyboard = [['Оновити вхідні', 'Написати лист']]
    if result:
        await update.message.reply_text("Лист відправлено.",
                                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await update.message.reply_text("Помилка відправки.",
                                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано.",
                                    reply_markup=ReplyKeyboardMarkup([['Оновити вхідні', 'Написати лист']],
                                                                     resize_keyboard=True))
    return ConversationHandler.END


async def run_bot():
    load_dotenv(dotenv_path=ENV_PATH)
    token = os.environ.get("TELEGRAM_TOKEN")

    if not token:
        print("Помилка: TELEGRAM_TOKEN не знайдено.")
        return

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Написати лист$'), start_email)],
        states={
            RECIPIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_recipient)],
            SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subject)],
            BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_email_finish)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('^Оновити вхідні$'), check_inbox))
    application.add_handler(CallbackQueryHandler(read_email_callback, pattern="^read_"))
    application.add_handler(conv_handler)

    await application.run_polling()