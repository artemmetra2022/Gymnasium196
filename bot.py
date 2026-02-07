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
MAIN_ADMIN_ID = int(os.environ.get("MAIN_ADMIN_ID", "1490660804"))
REGULAR_ADMINS_STR = os.environ.get("REGULAR_ADMINS", "").strip()
REGULAR_ADMINS = set(int(x.strip()) for x in REGULAR_ADMINS_STR.split(",") if x.strip().isdigit())
ALL_ADMINS = {MAIN_ADMIN_ID} | REGULAR_ADMINS

# === ИЗОБРАЖЕНИЕ ===
WELCOME_IMAGE_URL = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQxa_g7qQ8If0sQ0ahHso6bCVdFaGcy9_xvfw&s"

# === СПИСОК УЧИТЕЛЕЙ ===
SUBJECT_TEACHERS = {
    "Математика": [
        {"name": "Деянова И.С.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-matematiki/deanova-i-s"},
        {"name": "Иванова О.И.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-matematiki/ivanova-o-i"},
        {"name": "Корчагина С.М.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-matematiki/korcagina-svetlana-mihajlovna"},
        {"name": "Ефимов С.В.", "url": None},
    ],
    "Русский Язык и Литература": [
        {"name": "Егорова С.В.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/egorova-s-v"},
        {"name": "Леонтьева И.Г.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/leonteva-i-g"},
        {"name": "Паневина Л.В.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/panevina-l-v"},
        {"name": "Пищенко Л.В.", "url": None},
        {"name": "Селицкая В.В.", "url": None},
        {"name": "Шевченко С.Ф.", "url": None},
    ],
    "Иностранные Языки": [
        {"name": "Бондаренко Л.И.", "url": None},
        {"name": "Варлашкина Е.А.", "url": None},
        {"name": "Войлокова И.А.", "url": None},
        {"name": "Дорощенко С.Г.", "url": None},
        {"name": "Екимова О.М.", "url": None},
        {"name": "Ефимова С.В.", "url": None},
        {"name": "Иванова Е.В.", "url": None},
        {"name": "Каркалайнен И.В.", "url": None},
        {"name": "Кудрявцева С.И.", "url": None},
        {"name": "Леднева О.Ю.", "url": None},
        {"name": "Магомедова Н.Г.", "url": None},
        {"name": "Михайловская А.В.", "url": None},
        {"name": "Панфилова Н.В.", "url": None},
        {"name": "Погребная Ю.С.", "url": None},
        {"name": "Рябова Е.В.", "url": None},
        {"name": "Стефановская А.Р.", "url": None},
        {"name": "Тимофеева А.И.", "url": None},
        {"name": "Шелухина А.В.", "url": None},
    ],
    "Обществознание": [
        {"name": "Дмитриева В.С.", "url": None},
        {"name": "Ковалькова М.А.", "url": None},
        {"name": "Шумилова Е.В.", "url": None},
        {"name": "Бершадская Е.Л.", "url": None},
        {"name": "Карамян А.Г.", "url": None},
        {"name": "Кашина Н.В.", "url": None},
        {"name": "Моисенкова А.Р.", "url": None},
    ],
    "История": [
        {"name": "Дмитриева В.С.", "url": None},
        {"name": "Ковалькова М.А.", "url": None},
        {"name": "Шумилова Е.В.", "url": None},
        {"name": "Бершадская Е.Л.", "url": None},
        {"name": "Карамян А.Г.", "url": None},
        {"name": "Кашина Н.В.", "url": None},
        {"name": "Моисенкова А.Р.", "url": None},
    ],
    "ОбЖ и Физ-Культура": [
        {"name": "Коротченкова С.В.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/korotcenkova-s-v"},
        {"name": "Латура А.В.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/latura-a-v"},
        {"name": "Максимова С.А.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/maksimova-s-a"},
        {"name": "Мохова К.Б.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/mohova-k-b"},
    ],
    "Физика и Химия": [
        {"name": "Чернышова Т.Н.", "url": None},
        {"name": "Сажина Е.Г.", "url": None},
    ],
    "Биология и География": [
        {"name": "Александрова Е.В.", "url": None},
        {"name": "Сангаджиева К.Н.", "url": None},
        {"name": "Степанова С.В.", "url": None},
        {"name": "Ярина О.Г.", "url": None},
    ],
    "Информатика": [
        {"name": "Крутоверцева А.В.", "url": None},
        {"name": "Мездрогина Е.А.", "url": None},
    ],
    "Изо и Музыка": [
        {"name": "Горбачева Е.В.", "url": None},
        {"name": "Бакланова О.Е.", "url": None},
    ],
    "Технология": [
        {"name": "Хомченкова И.Б.", "url": None},
    ],
}

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# === ХРАНЕНИЕ ДАННЫХ ===
KNOWN_USERS = set()
USER_STATES = {}
BROADCAST_SENDER = {}
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
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="👇", reply_markup=reply_markup)

# === КОМАНДЫ ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    KNOWN_USERS.add(user_id)

    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=WELCOME_IMAGE_URL,
            caption="Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\nВыберите нужный вам пункт.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.warning(f"Не удалось загрузить изображение: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\nВыберите нужный вам пункт.",
            parse_mode="Markdown"
        )
    
    await send_main_menu(update, context)

async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for _ in range(50):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⠀")
    await send_main_menu(update, context)

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# === АДМИН-ПАНЕЛЬ ===

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != MAIN_ADMIN_ID:
        await context.bot.send_message(chat_id=user_id, text="❌ Доступ запрещён.")
        return

    if REGULAR_ADMINS:
        admins_list = "\n".join([f"`{aid}`" for aid in sorted(REGULAR_ADMINS)])
        text = f"👑 *Админ-панель*\n\nОбычные админы:\n{admins_list}"
    else:
        text = "👑 *Админ-панель*\n\nОбычных админов нет."

    keyboard = [
        [InlineKeyboardButton("➕ Назначить админа", callback_data="admin_add")],
        [InlineKeyboardButton("➖ Удалить админа", callback_data="admin_remove")],
        [InlineKeyboardButton("🔙 Закрыть", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)

# === РАССЫЛКА ===

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALL_ADMINS:
        await context.bot.send_message(chat_id=user_id, text="❌ Эта команда доступна только администраторам.")
        return

    keyboard = [
        [InlineKeyboardButton("👤 Админ", callback_data="broadcast_sender_admin")],
        [InlineKeyboardButton("🏛 Администрация гимназии", callback_data="broadcast_sender_gym")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text="📤 Выберите отправителя рассылки:", reply_markup=reply_markup)

# === ОБРАБОТКА ТЕКСТА ===

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # === РЕЖИМ НАЗНАЧЕНИЯ/УДАЛЕНИЯ АДМИНА ===
    if USER_STATES.get(MAIN_ADMIN_ID) == "admin_add":
        if user_id == MAIN_ADMIN_ID:
            try:
                new_admin_id = int(text.strip())
                if new_admin_id == MAIN_ADMIN_ID:
                    await context.bot.send_message(chat_id=chat_id, text="⚠️ Это вы — главный админ!")
                elif new_admin_id in REGULAR_ADMINS:
                    await context.bot.send_message(chat_id=chat_id, text="⚠️ Этот пользователь уже админ.")
                else:
                    REGULAR_ADMINS.add(new_admin_id)
                    ALL_ADMINS.add(new_admin_id)
                    await context.bot.send_message(chat_id=chat_id, text=f"✅ Пользователь `{new_admin_id}` назначен админом.", parse_mode="Markdown")
                    USER_STATES[MAIN_ADMIN_ID] = None
            except ValueError:
                await context.bot.send_message(chat_id=chat_id, text="❌ Неверный ID. Отправьте числовой ID.")
        return

    if USER_STATES.get(MAIN_ADMIN_ID) == "admin_remove":
        if user_id == MAIN_ADMIN_ID:
            try:
                admin_id = int(text.strip())
                if admin_id == MAIN_ADMIN_ID:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Нельзя удалить главного админа!")
                elif admin_id not in REGULAR_ADMINS:
                    await context.bot.send_message(chat_id=chat_id, text="❌ Такого админа нет.")
                else:
                    REGULAR_ADMINS.discard(admin_id)
                    ALL_ADMINS.discard(admin_id)
                    await context.bot.send_message(chat_id=chat_id, text=f"✅ Админ `{admin_id}` удалён.", parse_mode="Markdown")
                    USER_STATES[MAIN_ADMIN_ID] = None
            except ValueError:
                await context.bot.send_message(chat_id=chat_id, text="❌ Неверный ID.")
        return

    # === РАССЫЛКА ===
    if user_id in ALL_ADMINS and USER_STATES.get(user_id) == "broadcast_text":
        message_text = text
        date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        success_count = 0
        failed_count = 0
        for target_id in KNOWN_USERS:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"📩 *{BROADCAST_SENDER.get(user_id, 'Админ')}*\n"
                        f"📅 {date_str}\n\n"
                        f"{message_text}"
                    ),
                    parse_mode="Markdown"
                )
                success_count += 1
            except Exception as e:
                logging.warning(f"Не удалось отправить {target_id}: {e}")
                failed_count += 1

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Рассылка завершена!\nУспешно: {success_count}\nНеудачно: {failed_count}"
        )
        USER_STATES[user_id] = None
        BROADCAST_SENDER.pop(user_id, None)
        return

    # === ПРЕДЛОЖЕНИЕ ИДЕИ (ТОЛЬКО ГЛАВНОМУ АДМИНУ) ===
    if USER_STATES.get(user_id) == "waiting_for_idea":
        username = update.effective_user.username or "без_юзернейма"
        idea_msg = (
            f"💡 Новая идея от пользователя\n"
            f"ID: {user_id}\n"
            f"Username: @{username}\n\n"
            f"{text}"
        )
        try:
            await context.bot.send_message(chat_id=MAIN_ADMIN_ID, text=idea_msg)
        except Exception as e:
            logging.error(f"Ошибка отправки идеи: {e}")
        await context.bot.send_message(chat_id=chat_id, text="✅ Спасибо! Ваша идея отправлена разработчикам.")
        USER_STATES[user_id] = None
        await asyncio.sleep(30)
        await send_main_menu(update, context)
        return

    # === АНОНИМНАЯ СВЯЗЬ (ВСЕМ АДМИНАМ) ===
    if USER_STATES.get(user_id) == "in_contact":
        username = update.effective_user.username or "без_юзернейма"
        contact_msg = (
            f"📩 Анонимное сообщение от пользователя\n"
            f"ID: {user_id}\n"
            f"Username: @{username}\n\n"
            f"{text}"
        )
        for admin_id in ALL_ADMINS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=contact_msg)
            except Exception as e:
                logging.warning(f"Не удалось отправить админу {admin_id}: {e}")
        await context.bot.send_message(chat_id=chat_id, text="✅ Сообщение отправлено администрации гимназии!")
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
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Гимназия №196 в Санкт-Петербурге – это образовательное учреждение, предлагающее широкий спектр учебных программ.\n"
                "Адрес: Санкт-Петербург, пр. Ударников, 31.\n"
                "Контакты:\nТелефон: +7 (812) 417-22-02\nЭлектронная почта: school196@bk.ru."
            ),
            reply_markup=reply_markup
        )

    elif text == "Для учителей":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Дорогой учитель, если вы хотите, чтобы ваше сообщение/ссылки были в разделе \"Выбор Предмета\", "
                "свяжитесь с нами лично в гимназии и мы все обсудим и разместим."
            ),
            reply_markup=reply_markup
        )

    elif text == "Для учеников":
        keyboard = [
            [InlineKeyboardButton("🎮 Игра", callback_data="start_game")],
            [InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Привет, гимназист! В этом разделе для тебя только игра, "
                "но также ты можешь предложить идею в \"О разработке\" и мы её прочитаем."
            ),
            reply_markup=reply_markup
        )

    elif text == "О разработке/оценить":
        keyboard = [
            [InlineKeyboardButton("💡 Предложить идею", callback_data="suggest_idea")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Данный бот создан командой 7В класса. Вы можете предложить идею по улучшению бота, "
                "для этого выберите соответствующий пункт."
            ),
            reply_markup=reply_markup
        )

    elif text == "Выбор Предмета":
        subjects = list(SUBJECT_TEACHERS.keys())
        keyboard = []
        for i in range(0, len(subjects), 2):
            row = [InlineKeyboardButton(subjects[i], callback_data=f"subject_{subjects[i]}")]
            if i + 1 < len(subjects):
                row.append(InlineKeyboardButton(subjects[i+1], callback_data=f"subject_{subjects[i+1]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=chat_id, text="Выберите предмет:", reply_markup=reply_markup)

# === CALLBACK-ОБРАБОТЧИК ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if query.data == "back_to_menu":
        await query.message.delete()
        await send_main_menu(update, context)

    elif query.data == "admin_add":
        if user_id == MAIN_ADMIN_ID:
            USER_STATES[MAIN_ADMIN_ID] = "admin_add"
            await query.message.edit_text("Введите Telegram ID нового админа:")
    elif query.data == "admin_remove":
        if user_id == MAIN_ADMIN_ID:
            USER_STATES[MAIN_ADMIN_ID] = "admin_remove"
            await query.message.edit_text("Введите Telegram ID админа для удаления:")

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
                await context.bot.send_message(chat_id=chat_id, text="⏰ Время вышло. Возвращаемся в главное меню...")
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
        subject_name = query.data[len("subject_"):]
        if subject_name not in SUBJECT_TEACHERS:
            await query.message.edit_text("Предмет не найден.")
            await asyncio.sleep(2)
            await send_main_menu(update, context)
            return

        teachers = SUBJECT_TEACHERS[subject_name]
        keyboard = []
        for i in range(0, len(teachers), 2):
            row = [InlineKeyboardButton(teachers[i]["name"], callback_data=f"teacher_{subject_name}_{i}")]
            if i + 1 < len(teachers):
                row.append(InlineKeyboardButton(teachers[i+1]["name"], callback_data=f"teacher_{subject_name}_{i+1}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_subjects")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Удаляем старое сообщение и отправляем новое
        await query.message.delete()
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📚 *{subject_name}*\nВыберите учителя:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    elif query.data == "back_to_subjects":
        subjects = list(SUBJECT_TEACHERS.keys())
        keyboard = []
        for i in range(0, len(subjects), 2):
            row = [InlineKeyboardButton(subjects[i], callback_data=f"subject_{subjects[i]}")]
            if i + 1 < len(subjects):
                row.append(InlineKeyboardButton(subjects[i+1], callback_data=f"subject_{subjects[i+1]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.delete()
        await context.bot.send_message(chat_id=chat_id, text="Выберите предмет:", reply_markup=reply_markup)

    elif query.data.startswith("teacher_"):
        parts = query.data.split("_", 2)
        if len(parts) < 3:
            await query.message.edit_text("Ошибка выбора учителя.")
            return
        subject_name = parts[1]
        try:
            index = int(parts[2])
        except ValueError:
            await query.message.edit_text("Ошибка индекса учителя.")
            return
        teachers = SUBJECT_TEACHERS.get(subject_name, [])
        if index >= len(teachers):
            await query.message.edit_text("Учитель не найден.")
            return
        teacher = teachers[index]
        name = teacher["name"]
        url = teacher["url"]
        link_text = f"[Персональная страница]({url})" if url else "Нет ссылки"

        message = (
            f"👤 *{name}*\n\n"
            f"Информация от учителя: пока нет информации.\n\n"
            f"{link_text}"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f"subject_{subject_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(message, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=reply_markup)

    elif query.data == "broadcast_sender_admin":
        if user_id in ALL_ADMINS:
            BROADCAST_SENDER[user_id] = "Админ"
            await query.message.edit_text("Напишите текст рассылки.")
            USER_STATES[user_id] = "broadcast_text"

    elif query.data == "broadcast_sender_gym":
        if user_id in ALL_ADMINS:
            BROADCAST_SENDER[user_id] = "Администрация гимназии"
            await query.message.edit_text("Напишите текст рассылки.")
            USER_STATES[user_id] = "broadcast_text"

# === ОСНОВНАЯ ФУНКЦИЯ ===

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear_chat))
    application.add_handler(CommandHandler("restart", restart_bot))
    application.add_handler(CommandHandler("broadcast", broadcast_start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("contact", lambda u, c: c.bot.send_message(chat_id=u.effective_chat.id, text="Используйте раздел «Для родителей» → «Связь».")))
    application.add_handler(CommandHandler("idea", lambda u, c: c.bot.send_message(chat_id=u.effective_chat.id, text="Используйте раздел «О разработке» → «Предложить идею».")))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
