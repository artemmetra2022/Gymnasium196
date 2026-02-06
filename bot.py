import asyncio
import logging
import random
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
BOT_TOKEN = os.environ["7951383168:AAFeVrvRcR4NuukPjsk37H-yuhQYdfVY1ns"]  # ← ОБЯЗАТЕЛЬНО замените на свой токен от @BotFather
ADMIN_CHAT_ID = 1490660804  # ← Ваш ID — сюда приходят идеи и сообщения

# URL изображения приветствия (замените на реальный!)
WELCOME_IMAGE_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQxa_g7qQ8If0sQ0ahHso6bCVdFaGcy9_xvfw&s"  # ← ЗАМЕНИТЕ НА СВОЙ URL!

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# === ГЛОБАЛЬНЫЕ СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ===
USER_STATES = {}  # user_id -> состояние ('waiting_for_idea', 'in_contact')
GAME_SCORES = {}  # user_id -> {'user': int, 'bot': int}

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
    await update.message.reply_text(
        "Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\n"
        "Выберите нужный вам пункт.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# === КОМАНДЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=WELCOME_IMAGE_URL,
            caption="Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\n"
                    "Выберите нужный вам пункт.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка загрузки изображения: {e}")
        await update.message.reply_text(
            "Здравствуйте! Бот Гимназии №196 готов помочь.\nВыберите пункт меню.",
            parse_mode="Markdown"
        )
    await send_main_menu(update, context)

async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for _ in range(50):
        await update.message.reply_text("⠀")  # Невидимый символ
    await send_main_menu(update, context)

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# === ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ===

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if USER_STATES.get(user_id) == "waiting_for_idea":
        # Отправка идеи админу
        username = update.effective_user.username or "без_юзернейма"
        idea_text = (
            f"💡 *Новая идея от пользователя*\n"
            f"ID: `{user_id}`\n"
            f"Username: @{username}\n\n"
            f"{update.message.text}"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=idea_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить идею: {e}")
        await update.message.reply_text("✅ Спасибо! Ваша идея отправлена разработчикам.")
        USER_STATES[user_id] = None
        # Автоматический возврат через 30 сек
        await asyncio.sleep(30)
        await send_main_menu(update, context)
        return

    if USER_STATES.get(user_id) == "in_contact":
        # Анонимное сообщение админу
        username = update.effective_user.username or "без_юзернейма"
        msg_text = (
            f"📩 *Анонимное сообщение от пользователя*\n"
            f"ID: `{user_id}`\n"
            f"Username: @{username}\n\n"
            f"{update.message.text}"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=msg_text,
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ Сообщение отправлено администрации гимназии!")
        except Exception as e:
            await update.message.reply_text("❌ Не удалось отправить. Попробуйте позже.")
        USER_STATES[user_id] = None
        await send_main_menu(update, context)
        return

    # Обработка кнопок главного меню
    if text == "Для родителей":
        keyboard = [
            [InlineKeyboardButton("🌐 Сайт", url="http://www.196.edusite.ru")],
            [InlineKeyboardButton(".VK ВКонтакте", url="https://vk.com/gym196")],
            [InlineKeyboardButton("📞 Связь", callback_data="contact_admin")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Гимназия №196 в Санкт-Петербурге – это образовательное учреждение, предлагающее широкий спектр учебных программ.\n"
            "Адрес: Санкт-Петербург, пр. Ударников, 31.\n"
            "Контакты:\nТелефон: +7 (812) 417-22-02\nЭлектронная почта: school196@bk.ru",
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
            "Напишите своё сообщение. Оно будет анонимно передано администрации гимназии.\n"
            "После отправки вы вернётесь в главное меню."
        )

    elif query.data == "suggest_idea":
        USER_STATES[user_id] = "waiting_for_idea"
        await query.message.edit_text(
            "Напишите свою идею по улучшению бота. Мы обязательно её прочитаем!\n"
            "Через 30 секунд вы автоматически вернётесь в главное меню."
        )
        # Таймер на 30 сек
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
        await query.message.edit_text("📚 Материалы по этому предмету скоро появятся!")
        await asyncio.sleep(2)
        await send_main_menu(update, context)

# === ОСНОВНАЯ ФУНКЦИЯ ===

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear_chat))
    application.add_handler(CommandHandler("restart", restart_bot))
    application.add_handler(CommandHandler("contact", lambda u, c: u.message.reply_text("Используйте раздел «Для родителей» → «Связь».")))
    application.add_handler(CommandHandler("idea", lambda u, c: u.message.reply_text("Используйте раздел «О разработке» → «Предложить идею».")))

    # Callback-кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Все текстовые сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Бот запущен и готов принимать сообщения!")
    print(f"📬 Все идеи и сообщения будут приходить вам (ID: {ADMIN_CHAT_ID})")
    application.run_polling()

if __name__ == "__main__":
    main()
