import os
import asyncio
import logging
import random
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = 1490660804  # Ваш ID

# Рабочая ссылка на изображение
WELCOME_IMAGE_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQxa_g7qQ8If0sQ0ahHso6bCVdFaGcy9_xvfw&s"

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# === ХРАНЕНИЕ ДАННЫХ ===
KNOWN_USERS = set()  # Все пользователи, писавшие боту
USER_STATES = {}     # Состояния: 'waiting_for_idea', 'in_contact', 'broadcast_text'
BROADCAST_SENDER = {}  # {user_id: "Админ" или "Администрация гимназии"}
GAME_SCORES = {}

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def main_menu_keyboard():
    return [
        ["Для родителей", "Для учителей"],
        ["Для учеников", "О разработке/оценить"],
        ["Выбор Предмета"]
    ]

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = main_menu_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("👇", reply_markup=reply_markup)

# === КОМАНДЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    KNOWN_USERS.add(user_id)  # Запоминаем пользователя

    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=WELCOME_IMAGE_URL,
            caption="Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\nВыберите нужный вам пункт.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.warning(f"Не удалось загрузить изображение: {e}")
        await update.message.reply_text(
            "Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\nВыберите нужный вам пункт.",
            parse_mode="Markdown"
        )
    
    await send_main_menu(update, context)

async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for _ in range(50):
        await update.message.reply_text("⠀")
    await send_main_menu(update, context)

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# === РАССЫЛКА ===

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Эта команда доступна только администратору.")
        return

    keyboard = [
        [InlineKeyboardButton("👤 Админ", callback_data="broadcast_sender_admin")],
        [InlineKeyboardButton("🏛 Администрация гимназии", callback_data="broadcast_sender_gym")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📤 Выберите отправителя рассылки:", reply_markup=reply_markup)

# === ОБРАБОТКА ТЕКСТА ===

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # === РАССЫЛКА ===
    if user_id == ADMIN_CHAT_ID and USER_STATES.get(user_id) == "broadcast_text":
        sender = BROADCAST_SENDER.get(user_id, "Админ")
        message_text = text
        date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        success_count = 0
        failed_count = 0
        for chat_id in KNOWN_USERS:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"📩 *{sender}*\n"
                        f"📅 {date_str}\n\n"
                        f"{message_text}"
                    ),
                    parse_mode="Markdown"
                )
                success_count += 1
            except Exception as e:
                logging.warning(f"Не удалось отправить {chat_id}: {e}")
                failed_count += 1

        await update.message.reply_text(
            f"✅ Рассылка завершена!\n"
            f"Успешно: {success_count}\n"
            f"Неудачно: {failed_count}"
        )
        USER_STATES[user_id] = None
        BROADCAST_SENDER.pop(user_id, None)
        return

    # === ПРЕДЛОЖЕНИЕ ИДЕИ ===
    if USER_STATES.get(user_id) == "waiting_for_idea":
        username = update.effective_user.username or "без_юзернейма"
        idea_msg = (
            f"💡 *Новая идея от пользователя*\n"
            f"ID: `{user_id}`\n"
            f"Username: @{username}\n\n"
            f"{text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=idea_msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Ошибка отправки идеи: {e}")
        await update.message.reply_text("✅ Спасибо! Ваша идея отправлена разработчикам.")
        USER_STATES[user_id] = None
        await asyncio.sleep(30)
        await send_main_menu(update, context)
        return

    # === АНОНИМНАЯ СВЯЗЬ ===
    if USER_STATES.get(user_id) == "in_contact":
        username = update.effective_user.username or "без_юзернейма"
        contact_msg = (
            f"📩 *Анонимное сообщение от пользователя*\n"
            f"ID: `{user_id}`\n"
            f"Username: @{username}\n\n"
            f"{text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=contact_msg, parse_mode="Markdown")
            await update.message.reply_text("✅ Сообщение отправлено администрации гимназии!")
        except Exception as e:
            await update.message.reply_text("❌ Не удалось отправить. Попробуйте позже.")
        USER_STATES[user_id] = None
        await send_main_menu(update, context)
        return

    # === ГЛАВНОЕ МЕНЮ ===
    if text == "Для родителей":
        keyboard = [
            [InlineKeyboardButton("🌐 Сайт", url="https://196spb.edusite.ru/")],
            [InlineKeyboardButton(".VK ВКонтакте", url="https://vk.com/gym196")],
            [InlineKeyboardButton("📞 Связь", callback_data="contact_admin")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Гимназия №196 в Санкт-Петербурге – это образовательное учреждение, предлагающее широкий спектр учебных программ.\n"
            "Адрес: Санкт-Петербург, пр. Ударников, 31.\n"
            "Контакты:\nТелефон: +7 (812) 417-22-02\nЭлектронная почта: school196@bk.ru.",
            reply_markup=reply_markup
        )

    elif text == "Для учителей":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Дорогой учитель, если вы хотите, чтобы ваше сообщение/ссылки были в разделе \"Выбор Предмета\", "
            "свяжитесь с нами лично в гимназии и мы все обсудим и разместим.",
            reply_markup=reply_markup
        )

    elif text == "Для учеников":
        keyboard = [
            [InlineKeyboardButton("🎮 Игра", callback_data="start_game")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Привет, гимназист! В этом разделе для тебя только игра, "
            "но также ты можешь предложить идею в \"О разработке\" и мы её прочитаем.",
            reply_markup=reply_markup
        )

    elif text == "О разработке/оценить":
        keyboard = [
            [InlineKeyboardButton("💡 Предложить идею", callback_data="suggest_idea")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Данный бот создан командой 7В класса. Вы можете предложить идею по улучшению бота, "
            "для этого выберите соответствующий пункт.",
            reply_markup=reply_markup
        )

    elif text == "Выбор Предмета":
        subjects = [
            "Математика", "Русский Язык и Литература", "Иностранные Языки",
            "Обществознание", "История", "ОбЖ и Физ-Культура",
            "Физика и Химия", "Биология и География", "Информатика",
            "Изо и Музыка", "Технология"
        ]
        keyboard = [[InlineKeyboardButton(subj, callback_data=f"subject_{subj}")] for subj in subjects]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите предмет:", reply_markup=reply_markup)

# === CALLBACK-ОБРАБОТЧИК ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "back_to_menu":
        await query.message.delete()
        await send_main_menu(update, context)

    elif query.data == "contact_admin":
        USER_STATES[user_id] = "in_contact"
        await query.message.edit_text(
            "Напишите своё сообщение. Оно будет анонимно передано администрации гимназии."
        )

    elif query.data == "suggest_idea":
        USER_STATES[user_id] = "waiting_for_idea"
        await query.message.edit_text(
            "Напишите свою идею. Через 30 секунд вы вернётесь в главное меню."
        )
        async def auto_return():
            await asyncio.sleep(30)
            if USER_STATES.get(user_id) == "waiting_for_idea":
                USER_STATES[user_id] = None
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="⏰ Время вышло. Возвращаемся в главное меню..."
                )
                await send_main_menu(update, context)
        asyncio.create_task(auto_return())

    elif query.data == "start_game":
        if user_id not in GAME_SCORES:
            GAME_SCORES[user_id] = {"user": 0, "bot": 0}
        score = GAME_SCORES[user_id]
        keyboard = [
            [InlineKeyboardButton("🪨 Камень", callback_data="game_rock")],
            [InlineKeyboardButton("✂️ Ножницы", callback_data="game_scissors")],
            [InlineKeyboardButton("📄 Бумага", callback_data="game_paper")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            f"🎮 Камень, ножницы, бумага!\nСчёт: Вы — {score['user']}, Бот — {score['bot']}\n\nВыберите:",
            reply_markup=reply_markup
        )

    elif query.data.startswith("game_"):
        user_choice = query.data.split("_")[1]
        bot_choice = random.choice(["rock", "scissors", "paper"])
        emojis = {"rock": "🪨", "scissors": "✂️", "paper": "📄"}
        names = {"rock": "Камень", "scissors": "Ножницы", "paper": "Бумага"}

        if user_choice == bot_choice:
            result = "🤝 Ничья!"
        elif (
            (user_choice == "rock" and bot_choice == "scissors") or
            (user_choice == "scissors" and bot_choice == "paper") or
            (user_choice == "paper" and bot_choice == "rock")
        ):
            result = "🎉 Вы победили!"
            GAME_SCORES[user_id]["user"] += 1
        else:
            result = "🤖 Бот победил!"
            GAME_SCORES[user_id]["bot"] += 1

        score = GAME_SCORES[user_id]
        keyboard = [
            [InlineKeyboardButton("🪨 Камень", callback_data="game_rock")],
            [InlineKeyboardButton("✂️ Ножницы", callback_data="game_scissors")],
            [InlineKeyboardButton("📄 Бумага", callback_data="game_paper")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(
            f"Вы: {emojis[user_choice]} ({names[user_choice]})\n"
            f"Бот: {emojis[bot_choice]} ({names[bot_choice]})\n\n"
            f"{result}\n\n"
            f"Счёт: Вы — {score['user']}, Бот — {score['bot']}\n\n"
            "Сыграем ещё?",
            reply_markup=reply_markup
        )

    elif query.data.startswith("subject_"):
        await query.message.edit_text("Пока ничего нет.")
        await asyncio.sleep(2)
        await send_main_menu(update, context)

    # === РАССЫЛКА: выбор отправителя ===
    elif query.data == "broadcast_sender_admin":
        BROADCAST_SENDER[ADMIN_CHAT_ID] = "Админ"
        await query.message.edit_text("Напишите текст рассылки.")
        USER_STATES[ADMIN_CHAT_ID] = "broadcast_text"

    elif query.data == "broadcast_sender_gym":
        BROADCAST_SENDER[ADMIN_CHAT_ID] = "Администрация гимназии"
        await query.message.edit_text("Напишите текст рассылки.")
        USER_STATES[ADMIN_CHAT_ID] = "broadcast_text"

# === ОСНОВНАЯ ФУНКЦИЯ ===

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear_chat))
    application.add_handler(CommandHandler("restart", restart_bot))
    application.add_handler(CommandHandler("broadcast", broadcast_start))
    application.add_handler(CommandHandler("contact", lambda u, c: u.message.reply_text("Используйте раздел «Для родителей» → «Связь».")))
    application.add_handler(CommandHandler("idea", lambda u, c: u.message.reply_text("Используйте раздел «О разработке» → «Предложить идею».")))

    # Обработчики
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
