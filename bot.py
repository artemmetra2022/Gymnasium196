"""
Telegram-бот Гимназии №196 Красногвардейского района Санкт-Петербурга
Установка: pip install python-telegram-bot==20.7
Запуск:    python bot.py

Добавлено: опросы, изменение информации об учителе, запланированные рассылки,
           учительская заметка, расширенная статистика, причина бана, архив рассылок,
           /dm, автобэкап, подтверждение разбана, история банов, каникулы,
           закреплённое объявление, /find, /teacher (роли учителей),
           фото в новостях/рассылках/страницах учителей, подписка на учителя, временный бан
"""

import logging
import json
import os
import io
import csv
import random
import asyncio
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ══════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ══════════════════════════════════════════
BOT_TOKEN      = "7951383168:AAFeVrvRcR4NuukPjsk37H-yuhQYdfVY1ns"   # ← вставьте токен от @BotFather
MAIN_ADMIN_ID  = 1490660804
DATA_FILE      = "data.json"

BROADCAST_TEMPLATE = (
    "Присоединяйтесь в группу нашей гимназии в VK!\n"
    "https://vk.com/gym196"
)
BROADCAST_TEMPLATE_TECH = (
    "⚠️Возможна нестабильная работа бота из-за технических работ. ⚠️"
)

# Дата ближайших каникул (можно менять)
HOLIDAY_DATE = datetime(2026, 3, 23)

# Пути к фото разделов (загружаются один раз, file_id кешируются в БД)
# Локальные файлы картинок разделов (положить рядом с bot.py)
SECTION_PHOTOS = {
    "schedule": "photo_schedule.jpg",
    "students": "photo_students.png",
    "teachers": "photo_teachers.png",
    "about":    "photo_about.png",
    "contact":  "photo_contact.png",
}

# Расписание звонков (статичное)
BELL_SCHEDULE = [
    ("1 Урок", "8:30 - 9:15"),
    ("2 Урок", "9:25 - 10:10"),
    ("3 Урок", "10:30 - 11:15"),
    ("4 Урок", "11:35 - 12:20"),
    ("5 Урок", "12:40 - 13:25"),
    ("6 Урок", "13:35 - 14:20"),
    ("7 Урок", "14:30 - 15:15"),
]

async def send_section_photo(chat_obj, chat_id, section: str, caption: str, kb, db):
    """Отправляет фото раздела.
    1. Если file_id есть в БД — берём оттуда (мгновенно).
    2. Иначе читаем локальный файл с увеличенным таймаутом, сохраняем file_id.
    3. Если файла нет — только текст.
    """
    import os
    from telegram.request import HTTPXRequest
    cached = db.get("section_photo_ids", {}).get(section)
    path   = SECTION_PHOTOS.get(section)
    try:
        if cached:
            await chat_obj.send_photo(photo=cached, caption=caption, reply_markup=kb)
        elif path and os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            from telegram import InputFile
            msg = await chat_obj.send_photo(
                photo=InputFile(io.BytesIO(data), filename=path),
                caption=caption,
                reply_markup=kb,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=30,
            )
            if msg.photo:
                db.setdefault("section_photo_ids", {})[section] = msg.photo[-1].file_id
                save_data(db)
        else:
            await chat_obj.send_message(text=caption, reply_markup=kb)
    except Exception as e:
        logger.error(f"send_section_photo [{section}] error: {e}")
        try:
            await chat_obj.send_message(text=caption, reply_markup=kb)
        except: pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════
#  СПИСОК УЧИТЕЛЕЙ
# ══════════════════════════════════════════
SUBJECT_TEACHERS = {
    "Математика": [
        {"name": "Деянова И.С.",   "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-matematiki/deanova-i-s"},
        {"name": "Иванова О.И.",   "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-matematiki/ivanova-o-i"},
        {"name": "Корчагина С.М.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-matematiki/korcagina-svetlana-mihajlovna"},
        {"name": "Ефимов С.В.",    "url": None},
    ],
    "Русский Язык и Литература": [
        {"name": "Егорова С.В.",   "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/egorova-s-v"},
        {"name": "Леонтьева И.Г.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/leonteva-i-g"},
        {"name": "Паневина Л.В.",  "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/panevina-l-v"},
        {"name": "Пищенко Л.В.",   "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/pisenko-l-v"},
        {"name": "Селицкая В.В.",  "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/selickaa-v-v",
         "extra": "Также: https://nsportal.ru/selitskaya-viktoriya-valerevna"},
        {"name": "Шевченко С.Ф.",  "url": "https://sites.google.com/site/ucitelskijklub196/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D1%8F%D0%B7%D1%8B%D0%BA-%D0%B8-%D0%BB%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0/sevcenko-s-f"},
    ],
    "Иностранные Языки": [
        {"name": "Бондаренко Л.И.",    "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/a-ponimau-mir-mir-ponimaet-mena"},
        {"name": "Варлашкина Е.А.",    "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/varlaskina-e-a"},
        {"name": "Войлокова И.А.",     "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/vojlokova-i-a"},
        {"name": "Дорощенко С.Г.",     "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/doroseno-s-g"},
        {"name": "Екимова О.М.",       "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/ekimova-olga-mihajlovna"},
        {"name": "Ефимова С.В.",       "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/letova-s-v"},
        {"name": "Иванова Е.В.",       "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/ivanova-ev"},
        {"name": "Каркалайнен И.В.",   "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/nikolaeva-n-v"},
        {"name": "Кудрявцева С.И.",    "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/ilina-s-i"},
        {"name": "Леднева О.Ю.",       "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/ledneva-o-u"},
        {"name": "Михайловская А.В.",  "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/mihajlovskaa-a-v"},
        {"name": "Панфилова Н.В.",     "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/panfilova-n-v"},
        {"name": "Погребная Ю.С.",     "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/pogrebnaa-u-s"},
        {"name": "Стефановская А.Р.",  "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/stefanovskaa-a-r"},
        {"name": "Тимофеева А.И.",     "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/avakan-m-u"},
        {"name": "Шелухина А.В.",      "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-inostrannyh-azykov/seluhina-a-v"},
    ],
    "Обществознание": [
        {"name": "Бершадская Е.Л.",  "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-istorii-i-obsestvoznania/bersadskaa-e-l-obsestvoznanie"},
        {"name": "Кашина Н.В.",      "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-istorii-i-obsestvoznania/kasina-n-v"},
        {"name": "Моисенкова А.Р.",  "url": None},
    ],
    "История": [
        {"name": "Ковалькова М.А.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-istorii-i-obsestvoznania/kovalkova-m-a",
         "extra": "Ссылка на оформление доклада: https://docs.google.com/document/d/0B-nQgdNmGcNQUlRXVkJTUUZhUU0/edit"},
        {"name": "Шумилова Е.В.",   "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-istorii-i-obsestvoznania/sumilova-e-v-istoria",
         "extra": "Директор гимназии"},
        {"name": "Бершадская Е.Л.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-istorii-i-obsestvoznania/bersadskaa-e-l-obsestvoznanie"},
        {"name": "Кашина Н.В.",     "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-istorii-i-obsestvoznania/kasina-n-v"},
        {"name": "Моисенкова А.Р.", "url": None},
    ],
    "ОбЖ и Физ-Культура": [
        {"name": "Коротченкова С.В.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/korotcenkova-s-v"},
        {"name": "Латура А.В.",       "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/latura-a-v"},
        {"name": "Максимова С.А.",    "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/maksimova-s-a"},
        {"name": "Мохова К.Б.",       "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0-%D0%B8-%D0%BE%D0%B1%D0%B7%D1%80/mohova-k-b"},
    ],
    "Физика и Химия": [
        {"name": "Чернышова Т.Н.", "url": "https://sites.google.com/site/ucitelskijklub196/%D1%84%D0%B8%D0%B7%D0%B8%D0%BA%D0%B0/cernyseva-t-n"},
        {"name": "Катунцева А.В.", "url": None},
        {"name": "Сафина Ю.Е.",    "url": None},
        {"name": "Сажина Е.Г.",    "url": "https://sites.google.com/site/ucitelskijklub196/%D1%85%D0%B8%D0%BC%D0%B8%D1%8F/sazina-e-g"},
    ],
    "Биология и География": [
        {"name": "Александрова Е.В.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-estestvoznania/aleksandrova-e-v-geografia",
         "extra": "Заместитель директора"},
        {"name": "Сангаджиева К.Н.",  "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-estestvoznania/sangadzieva-k-n"},
        {"name": "Степанова С.В.",    "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-estestvoznania/stepanova-s-v",
         "extra": "Заместитель директора"},
        {"name": "Ярина О.Г.",        "url": "https://sites.google.com/view/678196/%D0%B3%D0%BB%D0%B0%D0%B2%D0%BD%D0%B0%D1%8F"},
    ],
    "Информатика": [
        {"name": "Крутоверцева А.В.", "url": "https://sites.google.com/site/ucitelskijklub196/%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D0%BA%D0%B0/informatika-mladsie-klassy"},
        {"name": "Реуцкая Е.А.",      "url": None},
    ],
    "Изо и Музыка": [
        {"name": "Горбачева Е.В.",  "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-esteticeskogo-vospitania/gorbaceva-e-v---muzyka"},
        {"name": "Бакланова О.Е.",  "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-esteticeskogo-vospitania/baklanova-o-e"},
        {"name": "Дрюма Д.В.",      "url": None},
    ],
    "Технология": [
        {"name": "Хомченкова И.Б.", "url": "https://sites.google.com/site/ucitelskijklub196/kafedra-matematiki/homcenko-i-a"},
    ],
    "Начальная школа": [
        {"name": "Андреева Н.Е.",   "url": None}, {"name": "Белова Ю.В.",      "url": None},
        {"name": "Бучиц О.В.",      "url": None}, {"name": "Ваганова В.В.",    "url": None},
        {"name": "Данилова Т.В.",   "url": None}, {"name": "Костью Е.Ю.",      "url": None},
        {"name": "Кайялайнен Л.И.", "url": None}, {"name": "Лобанова Л.М.",    "url": None},
        {"name": "Лоборева М.В.",   "url": None}, {"name": "Михалева И.В.",    "url": None},
        {"name": "Мякота В.А.",     "url": None}, {"name": "Подзолкина Т.А.",  "url": None},
        {"name": "Полуянова Е.А.",  "url": None}, {"name": "Попова О.Н.",      "url": None},
        {"name": "Ретровская Е.А.", "url": None}, {"name": "Филина Т.Б.",      "url": None},
        {"name": "Любарская Е.",    "url": None, "extra": "логопед"},
    ],
}

# ══════════════════════════════════════════
#  БАЗА ДАННЫХ
# ══════════════════════════════════════════
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"admins": [], "news": [], "banned": [], "users": [],
            "tickets": [], "answered": [], "reviews": [], "reviews_done": []}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_main_admin(uid: int) -> bool:
    return uid == MAIN_ADMIN_ID

def is_admin(uid: int) -> bool:
    return is_main_admin(uid) or uid in load_data().get("admins", [])

def is_banned(uid: int) -> bool:
    db = load_data()
    if uid not in db.get("banned", []):
        return False
    # Проверяем временный бан
    until = db.get("ban_until", {}).get(str(uid))
    if until:
        until_dt = datetime.fromisoformat(until)
        if datetime.now() >= until_dt:
            # Бан истёк — снимаем
            db["banned"].remove(uid)
            db.get("ban_until", {}).pop(str(uid), None)
            save_data(db)
            return False
    return True

def track_section(section: str):
    """Увеличить счётчик посещений раздела + трекинг по часам и дням"""
    db  = load_data()
    db.setdefault("section_visits", {})[section] = db.get("section_visits", {}).get(section, 0) + 1
    now = datetime.now()
    hour_key = now.strftime("%H")          # "08", "14" и т.д.
    day_key  = now.strftime("%Y-%m-%d")    # "2026-02-28"
    db.setdefault("visits_by_hour", {}).setdefault(hour_key, 0)
    db["visits_by_hour"][hour_key] += 1
    db.setdefault("visits_by_day", {}).setdefault(day_key, 0)
    db["visits_by_day"][day_key] += 1
    save_data(db)

def register_user(uid: int, username: str = ""):
    db = load_data()
    if uid not in db.get("users", []):
        db.setdefault("users", []).append(uid)
    # Сохраняем/обновляем расширенную информацию
    info = db.setdefault("users_info", {})
    if str(uid) not in info:
        info[str(uid)] = {
            "username": username or "—",
            "registered": datetime.now().strftime("%d.%m.%Y %H:%M"),
        }
    elif username:
        info[str(uid)]["username"] = username
    save_data(db)

# ══════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════
# ══════════════════════════════════════════
#  FAQ (статичный список, редактируется в коде)
# ══════════════════════════════════════════
FAQ = {
    "user": [
        {
            "q": "Как написать сообщение администрации?",
            "a": "Нажмите «Для родителей» или «Для учеников» -> «Связаться с администрацией», "
                 "или используйте /contact. Ответ придёт в этот же чат."
        },
        {
            "q": "Как посмотреть расписание?",
            "a": "Раздел «Для учеников» -> кнопка «Расписание». "
                 "Откроется таблица в Google Docs."
        },
        {
            "q": "Как узнать кабинет нужного учителя?",
            "a": "Раздел «Выбор Предмета» -> выберите предмет -> выберите учителя. "
                 "На карточке будет указан кабинет и информация."
        },
        {
            "q": "Как оставить оценку боту?",
            "a": "Раздел «О разработке/оценить» -> «Оценить бота». "
                 "Можно поставить от 1 до 5 звёзд и оставить комментарий."
        },
        {
            "q": "Как предложить идею для бота?",
            "a": "Раздел «О разработке/оценить» -> «Предложить идею». "
                 "Напишите вашу идею - она уйдёт разработчикам."
        },
        {
            "q": "Как узнать сколько дней до каникул?",
            "a": "Раздел «Для учеников» -> кнопка «До каникул». "
                 "Бот покажет точный обратный отсчёт."
        },
        {
            "q": "Почему бот не отвечает на мои сообщения?",
            "a": "Бот отвечает только на команды (начинаются с /) и нажатия кнопок. "
                 "Для связи с администрацией используйте /contact."
        },
        {
            "q": "Что делать если бот перестал отвечать?",
            "a": "Отправьте команду /start - это перезапустит меню. "
                 "Если не помогло, попробуйте /clear для очистки чата."
        },
        {
            "q": "Как проголосовать в опросе?",
            "a": "Раздел «О разработке/оценить» -> «Опросы». "
                 "Выберите активный опрос и нажмите на один из вариантов ответа. "
                 "Проголосовать можно только один раз. Результаты видны сразу после голосования."
        },
        {
            "q": "Где смотреть новости гимназии?",
            "a": "Кнопка «Новости» в главном меню. "
                 "Листайте стрелками влево/вправо. "
                 "Закреплённая новость (со значком 📌) всегда показывается первой."
        },
        {
            "q": "Как посмотреть информацию для родителей?",
            "a": "Кнопка «Для родителей» в главном меню. "
                 "Там можно найти контакты администрации и связаться с ней."
        },
        {
            "q": "Как сыграть в игру?",
            "a": "Раздел «Для учеников» -> «Игра». "
                 "Это «Камень, ножницы, бумага» против бота. "
                 "Счёт отображается в заголовке игры. Победы сохраняются в вашем профиле /profile."
        },
        {
            "q": "Что такое /profile?",
            "a": "Команда /profile показывает вашу личную карточку: "
                 "роль в боте, дата регистрации, количество побед в игре, "
                 "число обращений к администрации, предложенные идеи и оценка бота."
        },
        {
            "q": "Мои данные в безопасности?",
            "a": "Бот хранит только: ваш Telegram ID, юзернейм и дату первого запуска. "
                 "Переписка с администрацией хранится в зашифрованной базе данных "
                 "и доступна только администраторам гимназии."
        },
        {
            "q": "Можно ли отправить анонимное сообщение?",
            "a": "Нет, все обращения через /contact привязаны к вашему Telegram-аккаунту. "
                 "Однако администраторы обязуются соблюдать конфиденциальность."
        },
    ],
    "teacher": [
        {
            "q": "Как попасть на свою страницу?",
            "a": "Нажмите «Выбор Предмета» в главном меню. "
                 "Появится кнопка «На свою страницу»."
        },
        {
            "q": "Как изменить информацию на своей странице?",
            "a": "Своя страница -> «Изменить информацию» -> введите новый текст. "
                 "Можно писать: время консультаций, требования, текущую тему, напоминания."
        },
        {
            "q": "Как указать или изменить кабинет?",
            "a": "Своя страница -> «Изменить кабинет» -> введите номер. "
                 "Например: 214 или 3-15."
        },
        {
            "q": "Как добавить фото на страницу?",
            "a": "Своя страница -> «Изменить фото» -> отправьте фотографию в чат боту. "
                 "Фото появится на вашей карточке для учеников."
        },
        {
            "q": "Как загрузить файлы (задания, материалы) для учеников?",
            "a": "Своя страница -> «Добавить файл» -> отправьте файл в чат (PDF, Word, Excel и др.). "
                 "Ученики увидят список и смогут скачать одной кнопкой. "
                 "Максимум 10 файлов, до 20 МБ каждый."
        },
        {
            "q": "Как удалить или заменить файл?",
            "a": "Своя страница -> «Управление файлами» -> нажмите на название файла чтобы удалить. "
                 "Затем добавьте новый через «Добавить файл»."
        },
        {
            "q": "Где ученики видят мою страницу?",
            "a": "Раздел «Выбор Предмета» -> ваш предмет -> ваша фамилия. "
                 "Ученики видят: имя, кабинет, информацию, фото и список файлов."
        },
        {
            "q": "Что писать в поле «Информация от учителя»?",
            "a": "Что угодно полезное для учеников: время консультаций, "
                 "текущая тема, требования к работам, напоминания о контрольных."
        },
        {
            "q": "Как написать администрации бота?",
            "a": "Используйте /contact. В сообщении будет автоматически указан "
                 "префикс [Учитель] и администрация увидит вашу роль."
        },
        {
            "q": "Можно ли удалить фото или информацию с страницы?",
            "a": "Да. Фото: своя страница -> «Удалить фото». "
                 "Информацию: «Удалить информацию». Кабинет: «Удалить кабинет». "
                 "Файлы: «Управление файлами» -> нажмите на файл."
        },
    ],
    "admin": [
        {
            "q": "Как открыть панель администратора?",
            "a": "Команда /admin. Там: управление новостями, банлист, статистика, "
                 "рассылки, опросы, экспорт и другие функции."
        },
        {
            "q": "Как заблокировать пользователя?",
            "a": "/banlist -> «Заблокировать» -> введите ID -> введите причину. "
                 "Пользователь получит уведомление с причиной блокировки."
        },
        {
            "q": "Как разблокировать пользователя?",
            "a": "/banlist -> «Разблокировать» -> выберите из списка -> подтвердите. "
                 "Пользователь получит уведомление о разблокировке."
        },
        {
            "q": "Как ответить на обращение пользователя?",
            "a": "/tickets -> найдите обращение стрелками -> «Ответить» -> введите текст. "
                 "Ответ придёт пользователю в личку от имени бота."
        },
        {
            "q": "Как сделать рассылку всем пользователям?",
            "a": "/broadcast -> выберите шаблон или напишите текст -> "
                 "при желании прикрепите фото -> «Отправить сейчас» или «Запланировать»."
        },
        {
            "q": "Как создать новость?",
            "a": "/event -> выберите отправителя -> дата события -> "
                 "текст -> фото (или пропустить) -> «Отправить»."
        },
        {
            "q": "Как найти пользователя по ID или нику?",
            "a": "/find -> введите ID числом или @юзернейм. "
                 "Бот покажет: роль, статус, дату регистрации, обращения, оценку бота."
        },
        {
            "q": "Как написать личное сообщение пользователю?",
            "a": "/dm -> введите ID или @юзернейм -> введите текст. "
                 "Пользователь получит сообщение с пометкой «от администрации»."
        },
        {
            "q": "Как посмотреть статистику бота?",
            "a": "/stats - всего пользователей, посещения разделов, "
                 "активность, средняя оценка, топ активных пользователей."
        },
        {
            "q": "Как экспортировать данные?",
            "a": "/admin -> «Экспорт данных» -> выберите: "
                 "пользователи, отзывы, статистика или полный бэкап БД."
        },
    ],
    "main_admin": [
        {
            "q": "Как назначить пользователя учителем?",
            "a": "/teacher -> введите ID или @юзернейм -> выберите предмет -> "
                 "выберите фамилию. Пользователь получит уведомление."
        },
        {
            "q": "Как снять роль учителя?",
            "a": "/admin -> «Управление учителями» -> нажмите «Снять [имя]». "
                 "Пользователь получит уведомление о снятии роли."
        },
        {
            "q": "Как назначить нового администратора?",
            "a": "/admin -> «Назначить админа» -> введите ID пользователя. "
                 "Обычный админ получает доступ к /tickets, /banlist, /broadcast, /stats."
        },
        {
            "q": "Как установить закреплённое объявление?",
            "a": "/admin -> «Закреплённое объявление» -> «Установить/изменить» -> введите текст. "
                 "Объявление показывается всем при /start."
        },
        {
            "q": "Как сделать резервную копию базы данных?",
            "a": "/backup - бот пришлёт файл БД в личку. "
                 "Автоматический бэкап делается раз в неделю."
        },
    ],
}

BANNED_WORDS = [
    # Мат (основные корни — бот ловит вхождения)
    "блять", "бля", "сука", "пизд", "хуй", "хуе", "хуя", "ёбан", "ебан",
    "еban", "пидор", "пидр", "мудак", "мудил", "залуп", "ёб ", " ёб",
    "уёб", "сучар", "ублюд", "выблядок", "шлюх", "проститут",
    # Оскорбления и угрозы
    "убью", "убить", "угрожаю", "взорву", "взорвать",
    # Спам-маркеры
    "заработок без вложений", "казино", "1xbet", "1хбет",
]

def contains_banned(text: str) -> str | None:
    """Возвращает найденное запрещённое слово или None"""
    low = text.lower()
    for word in BANNED_WORDS:
        if word in low:
            return word
    return None

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def escape_md(text: str) -> str:
    """Экранирует спецсимволы для Markdown v1 в Telegram"""
    # В Markdown v1 проблемы только с незакрытыми * _ ` [
    # Проще всего — убрать parse_mode и отправлять plain text
    # Но мы оставляем разметку только для наших *жирных* меток
    return text

async def safe_send(q, text: str, kb, parse_mode="Markdown"):
    """Универсальная отправка: edit если текст, delete+send если фото/документ"""
    try:
        await q.edit_message_text(text, parse_mode=parse_mode, reply_markup=kb)
    except Exception as e:
        err = str(e)
        if "There is no text" in err or "message can't be edited" in err.lower() or "MESSAGE_NOT_MODIFIED" in err:
            # Сообщение — медиа, удаляем и отправляем новое
            try:
                await q.message.delete()
            except: pass
            await q.message.chat.send_message(text, parse_mode=parse_mode, reply_markup=kb)
        elif "can't parse entities" in err.lower() or "parse" in err.lower():
            # Проблема с Markdown — отправляем без форматирования
            plain = text.replace("*", "").replace("_", "").replace("`", "")
            try:
                await q.edit_message_text(plain, reply_markup=kb)
            except:
                try:
                    await q.message.delete()
                except: pass
                await q.message.chat.send_message(plain, reply_markup=kb)
        else:
            # Другая ошибка — пробуем без parse_mode
            try:
                plain = text.replace("*", "").replace("_", "").replace("`", "")
                await q.message.delete()
            except: pass
            try:
                await q.message.chat.send_message(text, reply_markup=kb)
            except: pass

def main_kb():
    return ReplyKeyboardMarkup(
        [["Для родителей", "Для учителей"],
         ["Для учеников", "О разработке/оценить"],
         ["Выбор Предмета", "Новости"]],
        resize_keyboard=True
    )

async def delete_or_clear(q, send_menu: bool = True):
    try:
        await q.message.delete()
    except Exception:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
    if send_menu:
        try:
            await q.message.chat.send_message(
                "Вы находитесь в главном меню. Выберите интересующий вас пункт с помощью кнопок:",
                reply_markup=main_kb())
        except Exception:
            pass


# ══════════════════════════════════════════
#  ВИКТОРИНА — вопросы
# ══════════════════════════════════════════
QUIZ_QUESTIONS = [
    {"q": "Сколько планет в Солнечной системе?",
     "opts": ["7", "8", "9", "10"], "ans": 1},
    {"q": "Какой химический символ золота?",
     "opts": ["Go", "Gd", "Au", "Ag"], "ans": 2},
    {"q": "В каком году была основана Россия (образование Древнерусского государства)?",
     "opts": ["862", "988", "1147", "1240"], "ans": 0},
    {"q": "Чему равна сумма углов треугольника?",
     "opts": ["90°", "180°", "270°", "360°"], "ans": 1},
    {"q": "Какой орган вырабатывает инсулин?",
     "opts": ["Печень", "Почки", "Поджелудочная железа", "Селезёнка"], "ans": 2},
    {"q": "Автор романа «Война и мир»?",
     "opts": ["Достоевский", "Тургенев", "Толстой", "Чехов"], "ans": 2},
    {"q": "Какая планета самая большая в Солнечной системе?",
     "opts": ["Сатурн", "Нептун", "Юпитер", "Уран"], "ans": 2},
    {"q": "Скорость света (приближённо)?",
     "opts": ["200 000 км/с", "300 000 км/с", "400 000 км/с", "150 000 км/с"], "ans": 1},
    {"q": "Какой газ больше всего в атмосфере Земли?",
     "opts": ["Кислород", "Углекислый газ", "Аргон", "Азот"], "ans": 3},
    {"q": "Как звали первого человека в космосе?",
     "opts": ["Титов", "Гагарин", "Терешкова", "Леонов"], "ans": 1},
    {"q": "Чему равно π (пи) приближённо?",
     "opts": ["2.14", "3.14", "4.14", "1.14"], "ans": 1},
    {"q": "Столица Франции?",
     "opts": ["Берлин", "Лондон", "Рим", "Париж"], "ans": 3},
    {"q": "Сколько хромосом у человека?",
     "opts": ["23", "44", "46", "48"], "ans": 2},
    {"q": "Какой элемент имеет атомный номер 1?",
     "opts": ["Гелий", "Водород", "Литий", "Углерод"], "ans": 1},
    {"q": "В каком веке произошла Отечественная война 1812 года?",
     "opts": ["XVIII", "XIX", "XX", "XVII"], "ans": 1},
    {"q": "Что изучает биология?",
     "opts": ["Землю", "Живые организмы", "Звёзды", "Химические реакции"], "ans": 1},
    {"q": "Сколько нот в музыкальной гамме?",
     "opts": ["5", "6", "7", "8"], "ans": 2},
    {"q": "Самая длинная река в мире?",
     "opts": ["Амазонка", "Нил", "Янцзы", "Миссисипи"], "ans": 1},
    {"q": "Формула воды?",
     "opts": ["HO", "H2O", "H3O", "OH2"], "ans": 1},
    {"q": "Кто написал «Евгения Онегина»?",
     "opts": ["Лермонтов", "Гоголь", "Пушкин", "Некрасов"], "ans": 2},
]

# ══════════════════════════════════════════
#  ИГРА «Камень, ножницы, бумага»
# ══════════════════════════════════════════
GAME_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
GAME_EMOJI = {"rock": "🪨 Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}

def game_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪨 Камень",   callback_data="game_rock"),
         InlineKeyboardButton("✂️ Ножницы", callback_data="game_scissors"),
         InlineKeyboardButton("📄 Бумага",  callback_data="game_paper")],
        [InlineKeyboardButton("🏠 В меню",  callback_data="main_menu")],
    ])

async def show_game(q, ctx, result=""):
    sc  = ctx.user_data.get("game_score", {"user": 0, "bot": 0})
    txt = f"🎮 Камень, ножницы, бумага!\nСчёт: Вы — {sc['user']}, Бот — {sc['bot']}\n\n"
    txt += (result + "\n\nВыберите:") if result else "Выберите:"
    await q.edit_message_text(txt, reply_markup=game_kb())

# ══════════════════════════════════════════
#  ЛИСТАЛКИ (общая функция)
# ══════════════════════════════════════════
def pager_kb(page, total, prefix, close_cb="pager_close"):
    nav = []
    if page > 0:        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if page < total-1:  nav.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}{page+1}"))
    return InlineKeyboardMarkup([nav, [InlineKeyboardButton("❌ Закрыть", callback_data=close_cb)]])

# ══════════════════════════════════════════
#  ТИКЕТЫ (обращения пользователей)
# ══════════════════════════════════════════
def get_user_role_prefix(uid) -> str:
    """Возвращает префикс роли пользователя"""
    db = load_data()
    teachers = db.get("assigned_teachers", {})
    if any(v.get("uid") == uid for v in teachers.values()):
        return "[Учитель] "
    if uid == MAIN_ADMIN_ID:
        return "[Гл. админ] "
    if uid in db.get("admins", []):
        return "[Админ] "
    return "[Обычный пользователь] "

def ticket_text(t: dict, idx: int, total: int, section: str) -> str:
    status = "⏳ Ожидает ответа" if section == "tickets" else f"✅ Отвечено ({t.get('answered_by','?')})"
    role_prefix = get_user_role_prefix(t.get("uid", 0))
    lines = [
        f"📩 *Обращение {idx+1} из {total}*",
        f"👤 {role_prefix}{t.get('username','?')} (ID: `{t.get('uid')}`)",
        f"📅 {t.get('date','—')}",
        f"Статус: {status}",
        "",
        t.get('text',''),
    ]
    if section == "answered" and t.get("reply"):
        lines += ["", f"💬 *Ответ:* {t['reply']}"]
    return "\n".join(lines)

def ticket_kb(page: int, total: int, section: str, ticket_id: str) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:       nav.append(InlineKeyboardButton("⬅️", callback_data=f"{section}_pg_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if page < total-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"{section}_pg_{page+1}"))
    rows = [nav]
    if section == "tickets":
        rows.append([InlineKeyboardButton("💬 Ответить", callback_data=f"ticket_reply_{ticket_id}")])
    rows.append([InlineKeyboardButton("❌ Закрыть", callback_data="pager_close")])
    return InlineKeyboardMarkup(rows)

async def show_ticket_page(target, section: str, page: int, edit=False, send=False):
    db   = load_data()
    lst  = db.get(section, [])
    if not lst:
        empty = "⏳ Неотвеченных обращений нет." if section == "tickets" else "✅ Отвеченных обращений нет."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Закрыть", callback_data="pager_close")]])
        if send:   await target.reply_text(empty, reply_markup=kb)
        elif edit: await target.edit_message_text(empty, reply_markup=kb)
        return
    page  = max(0, min(page, len(lst)-1))
    t     = lst[page]
    txt   = ticket_text(t, page, len(lst), section)
    kb    = ticket_kb(page, len(lst), section, t.get("id",""))
    if send:   await target.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    elif edit: await target.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

# ══════════════════════════════════════════
#  ОЦЕНКИ
# ══════════════════════════════════════════
async def show_review_page(target, page: int, edit=False, send=False):
    db      = load_data()
    reviews = db.get("reviews", [])
    if not reviews:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Закрыть", callback_data="pager_close")]])
        if send:   await target.reply_text("⭐️ Оценок пока нет.", reply_markup=kb)
        elif edit: await target.edit_message_text("⭐️ Оценок пока нет.", reply_markup=kb)
        return
    page  = max(0, min(page, len(reviews)-1))
    r     = reviews[page]
    stars = "⭐️" * r.get("stars", 0)
    txt   = (
        f"⭐️ *Оценка {page+1} из {len(reviews)}*\n\n"
        f"👤 {r.get('username','?')} (ID: `{r.get('uid')}`)\n"
        f"📅 {r.get('date','—')}\n"
        f"Оценка: {stars}\n\n"
        f"✅ Понравилось:\n{r.get('liked','—')}\n\n"
        f"❌ Не понравилось:\n{r.get('disliked','—')}"
    )
    kb = pager_kb(page, len(reviews), "reviews_pg_")
    if send:   await target.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    elif edit: await target.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

# ══════════════════════════════════════════
#  АДМИН-ПАНЕЛЬ
# ══════════════════════════════════════════
async def show_admin_panel(target, ctx, uid: int, edit: bool = False):
    if is_main_admin(uid):
        db     = load_data()
        admins     = db.get("admins", [])
        users_info = db.get("users_info", {})
        if admins:
            a_lines = []
            for a in admins:
                info  = users_info.get(str(a), {})
                uname = info.get("username", "—")
                uname_str = f" (@{uname})" if uname and uname != "—" else ""
                a_lines.append(f"`{a}`{uname_str}")
            a_txt = "\n".join(a_lines)
        else:
            a_txt = "Обычных администраторов нет"
        # Считаем неотвеченные обращения
        pending = len(db.get("tickets", []))
        pending_str = f" ({pending} новых)" if pending else ""

        txt = (
            f"👑 *Админ-панель*\n\n"
            f"Обычные админы:\n{a_txt}\n\n"
            f"📘 *Справка по командам*\n\n"
            f"👤 *Для всех пользователей:*\n"
            f"/start — перезапуск бота\n"
            f"/clear — очистить чат\n"
            f"/profile — мой профиль\n"
            f"/contact — связь с администрацией\n"
            f"/idea — предложить идею\n\n"
            f"🛡️ *Для администраторов:*\n"
            f"/broadcast — отправить рассылку\n"
            f"/event — создать новость\n"
            f"/banlist — чёрный список\n"
            f"/tickets — обращения{pending_str}\n"
            f"/answered — отвеченные обращения\n"
            f"/reviews — оценки бота\n"
            f"/stats — статистика бота\n"
            f"/exportreviews — выгрузить оценки в CSV\n"
            f"/export — экспорт данных (единое меню)\\n"
            f"/polls — управление опросами\\n"
            f"/broadcasts — архив рассылок\\n"
            f"/dm — личное сообщение пользователю\\n\\n"
            f"👑 *Только главному админу:*\n"
            f"/admin — эта панель\n"
            f"/backup — резервная копия БД\n"
            f"/teacher — назначить пользователя учителем\n"
            f"Назначать/удалять админов\n\n"
            f"🔍 *Для всех администраторов:*\n"
            f"/find — поиск пользователя по ID или юзернейму"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить информацию об учителе", callback_data="edit_teacher_stub")],
            [InlineKeyboardButton("📰 Управление новостями",    callback_data="admin_news")],
            [InlineKeyboardButton("📊 Управление опросами",     callback_data="admin_polls")],
            [InlineKeyboardButton("📩 Обращения" + pending_str, callback_data="admin_tickets")],
            [InlineKeyboardButton("📊 Статистика",              callback_data="admin_stats")],
            [InlineKeyboardButton("📌 Закреплённое объявление", callback_data="pinned_view")],
            [InlineKeyboardButton("👨‍🏫 Управление учителями",   callback_data="admin_teachers")],
            [InlineKeyboardButton("➕ Назначить админа",        callback_data="admin_add")],
            [InlineKeyboardButton("➖ Удалить админа",          callback_data="admin_remove_list")],
            [InlineKeyboardButton("🔙 Закрыть",                 callback_data="admin_close")],
        ])
    else:
        db      = load_data()
        pending = len(db.get("tickets", []))
        pending_str = f" ({pending} новых)" if pending else ""
        txt = (
            f"🛡️ *Команды для администраторов:*\n\n"
            f"/broadcast — отправить рассылку\n"
            f"/event — создать новость\n"
            f"/banlist — чёрный список\n"
            f"/tickets — обращения{pending_str}\n"
            f"/answered — отвеченные обращения\n"
            f"/reviews — оценки бота\n"
            f"/stats — статистика бота\n"
            f"/exportreviews — выгрузить оценки в CSV\n"
            f"/export — экспорт данных\n"
            f"/broadcasts — архив рассылок\n"
            f"/dm — личное сообщение пользователю\n"
            f"/find — поиск пользователя\n"
            f"/admin — эта справка"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Обращения" + pending_str, callback_data="admin_tickets")],
            [InlineKeyboardButton("🔙 Закрыть", callback_data="admin_close")],
        ])

    if edit:
        await target.edit_message_text(txt, reply_markup=kb, parse_mode="Markdown")
    else:
        await target.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

# ══════════════════════════════════════════
#  КОМАНДЫ
# ══════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid):
        await update.message.reply_text("❌ Вы заблокированы в этом боте.")
        return
    register_user(uid, update.effective_user.username or "")
    ctx.user_data.clear()
    try:
        await update.message.reply_photo(
            photo="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQxa_g7qQ8If0sQ0ahHso6bCVdFaGcy9_xvfw&s",
            caption="Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\nВыберите нужный вам пункт.",
            parse_mode="Markdown",
            reply_markup=main_kb()
        )
    except Exception:
        await update.message.reply_text(
            "Здравствуйте, вы попали в телеграм бота *Гимназии 196 Красногвардейского района Санкт-Петербурга*.\nВыберите нужный вам пункт.",
            parse_mode="Markdown", reply_markup=main_kb()
        )
    # Показать закреплённое объявление если есть
    db = load_data()
    pinned = db.get("pinned_announcement")
    if pinned:
        await update.message.reply_text(
            f"📌 *Закреплённое объявление:*\n\n{pinned}",
            parse_mode="Markdown")

async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("state", None)
    await update.message.reply_text("Выберите раздел:", reply_markup=main_kb())

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    await show_admin_panel(update.message, ctx, uid)

async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Всем пользователям",          callback_data="bc_group_all")],
        [InlineKeyboardButton("👨‍🏫 Только учителям",            callback_data="bc_group_teachers")],
        [InlineKeyboardButton("🎓 Только ученикам",             callback_data="bc_group_students")],
        [InlineKeyboardButton("❌ Отмена",                      callback_data="pager_close")],
    ])
    await update.message.reply_text(
        "📢 *Новая рассылка*\n\nКому отправить?",
        parse_mode="Markdown", reply_markup=kb)

async def cmd_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Админ",                  callback_data="event_sender_admin")],
        [InlineKeyboardButton("Администрация гимназии", callback_data="event_sender_school")],
    ])
    await update.message.reply_text("Выберите отправителя новости:", reply_markup=kb)

async def cmd_banlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа.")
        return
    db      = load_data()
    banned  = db.get("banned", [])
    reasons = db.get("ban_reasons", {})
    if not banned:
        txt = "🚫 *Чёрный список пуст.*"
    else:
        lines = []
        for b in banned:
            r = reasons.get(str(b), "—")
            lines.append(f"`{b}` — {r}")
        txt = "🚫 *Чёрный список:*\n" + "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Заблокировать",   callback_data="admin_ban")],
        [InlineKeyboardButton("➖ Разблокировать", callback_data="admin_unban")],
        [InlineKeyboardButton("📋 История банов",  callback_data="ban_history")],
    ])
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

async def cmd_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_banned(update.effective_user.id):
        await update.message.reply_text("❌ Вы заблокированы в этом боте.")
        return
    db = load_data()
    all_adm = list(set([MAIN_ADMIN_ID] + db.get("admins", [])))
    adm_count = len(all_adm)
    ctx.user_data["state"] = "contact"
    await update.message.reply_text(
        f"📞 *Связь с администрацией*\n\n"
        f"Администраторов в сети: *{adm_count}*\n\n"
        f"Напишите ваше сообщение и мы ответим вам как можно скорее.\n"
        f"_Максимум 3 открытых обращения одновременно._",
        parse_mode="Markdown")

async def cmd_idea(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_banned(update.effective_user.id):
        await update.message.reply_text("❌ Вы заблокированы в этом боте.")
        return
    ctx.user_data["state"] = "idea"
    await update.message.reply_text("Напишите вашу идею, она будет отправлена разработчикам:")

async def cmd_tickets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    await show_ticket_page(update.message, "tickets", 0, send=True)

async def cmd_answered(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    await show_ticket_page(update.message, "answered", 0, send=True)

async def cmd_reviews(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    await show_review_page(update.message, 0, send=True)

async def cmd_backup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    if not os.path.exists(DATA_FILE):
        await update.message.reply_text("❌ Файл базы данных не найден.")
        return
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    with open(DATA_FILE, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=f"backup_{now_str}.json",
            caption=f"💾 Резервная копия базы данных\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

# ══════════════════════════════════════════
#  СТАТИСТИКА
# ══════════════════════════════════════════
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    db       = load_data()
    reviews  = db.get("reviews", [])
    tickets  = db.get("tickets", [])
    answered = db.get("answered", [])
    users    = db.get("users", [])
    news     = db.get("news", [])
    banned   = db.get("banned", [])
    admins   = db.get("admins", [])
    polls    = db.get("polls", [])
    visits   = db.get("section_visits", {})

    avg_str = "—"
    if reviews:
        avg = sum(r.get("stars", 0) for r in reviews) / len(reviews)
        avg_str = f"{avg:.1f} ⭐️ ({len(reviews)} отзывов)"
    stars_dist = {i: 0 for i in range(1, 6)}
    for r in reviews:
        s = r.get("stars", 0)
        if s in stars_dist: stars_dist[s] += 1
    stars_bar = "  ".join(f"{i}⭐️:{stars_dist[i]}" for i in range(5, 0, -1))
    total_tickets = len(tickets) + len(answered)
    teachers  = db.get("assigned_teachers", {})
    t_count   = sum(1 for tv in teachers.values() if tv.get("uid"))
    total_subs = sum(len(v) for v in db.get("teacher_subs", {}).values())
    tq_count  = len(db.get("teacher_questions", []))
    ideas     = db.get("ideas", [])
    broads    = db.get("broadcasts", [])
    temp_bans = sum(1 for u in banned if db.get("ban_until", {}).get(str(u)))
    perm_bans = len(banned) - temp_bans
    top_visits = sorted(visits.items(), key=lambda x: -x[1])[:5]
    visits_txt = "\n".join(f"• {k}: {v}" for k, v in top_visits) or "—"
    txt = (
        "📊 *Статистика бота*\n\n"
        f"👥 *Пользователи:*\n"
        f"Зарегистрировано: {len(users)}\n"
        f"Заблокировано всего: {len(banned)} (пост.: {perm_bans}, врем.: {temp_bans})\n"
        f"Администраторов: {len(admins) + 1}\n"
        f"Учителей с аккаунтом: {t_count}\n\n"
        f"📩 *Обращения:*\n"
        f"Открытых: {len(tickets)} | Закрытых: {len(answered)}\n"
        f"Всего за всё время: {total_tickets}\n\n"
        f"👨‍🏫 *Учителя:*\n"
        f"Подписок на учителей: {total_subs}\n"
        f"Вопросов учителям: {tq_count}\n\n"
        f"⭐️ *Оценки бота:*\n"
        f"Средняя: {avg_str}\n"
        f"Распределение: {stars_bar}\n\n"
        f"📰 *Контент:*\n"
        f"Новостей: {len(news)} | Опросов: {len(polls)}\n"
        f"Идей предложено: {len(ideas)}\n"
        f"Рассылок отправлено: {len(broads)}\n\n"
        f"🗂 *Топ разделов:*\n"
        f"{visits_txt}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 По часам (сегодня)",  callback_data="stats_graph_hours")],
        [InlineKeyboardButton("📊 По дням (неделя)",    callback_data="stats_graph_week")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="pager_close")],
    ])
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

async def cmd_exportreviews(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    db      = load_data()
    reviews = db.get("reviews", [])
    if not reviews:
        await update.message.reply_text("⭐️ Оценок пока нет — выгружать нечего.")
        return
    # Формируем CSV в памяти
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    writer.writerow(["Дата", "Пользователь", "ID", "Оценка (звёзды)", "Понравилось", "Не понравилось"])
    for r in reviews:
        writer.writerow([
            r.get("date", ""),
            r.get("username", ""),
            r.get("uid", ""),
            r.get("stars", ""),
            r.get("liked", ""),
            r.get("disliked", ""),
        ])
    buf.seek(0)
    file_bytes = io.BytesIO(buf.getvalue().encode("utf-8-sig"))  # utf-8-sig для корректного открытия в Excel
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_bytes.name = f"reviews_{now_str}.csv"
    await update.message.reply_document(
        document=file_bytes,
        filename=f"reviews_{now_str}.csv",
        caption="⭐️ Выгрузка оценок бота\n" + datetime.now().strftime("%d.%m.%Y %H:%M") + f"\nВсего оценок: {len(reviews)}",
    )


# ══════════════════════════════════════════
#  ЭКСПОРТ — вспомогательные функции
# ══════════════════════════════════════════
def make_csv_reviews(db: dict) -> io.BytesIO:
    reviews = db.get("reviews", [])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    w.writerow(["Дата", "Пользователь", "ID", "Оценка (звёзды)", "Понравилось", "Не понравилось"])
    for r in reviews:
        w.writerow([r.get("date",""), r.get("username",""), r.get("uid",""),
                    r.get("stars",""), r.get("liked",""), r.get("disliked","")])
    buf.seek(0)
    return io.BytesIO(buf.getvalue().encode("utf-8-sig"))

def make_csv_users(db: dict) -> io.BytesIO:
    users   = db.get("users", [])
    banned  = db.get("banned", [])
    admins  = db.get("admins", [])
    reviews = {r.get("uid"): r.get("stars") for r in db.get("reviews", [])}
    tickets = db.get("tickets", [])
    answered= db.get("answered", [])
    ideas   = db.get("ideas_log", {})   # будущий расширяемый лог
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL)
    w.writerow(["ID", "Username", "Дата регистрации", "Оценка", "Обращений (открыт.)",
                "Обращений (закрыт.)", "Статус", "Роль", "Подписок на учителей",
                "Побед в игре", "Срок бана"])
    all_subs = db.get("teacher_subs", {})
    ban_until_map = db.get("ban_until", {})
    game_scores = db.get("game_scores", {})
    for u in users:
        stars  = reviews.get(u, "-")
        open_t = sum(1 for t in tickets  if t.get("uid") == u)
        clos_t = sum(1 for t in answered if t.get("uid") == u)
        user_info = db.get("users_info", {}).get(str(u), {})
        uname  = user_info.get("username", "—")
        reg_dt = user_info.get("registered", "—")
        status = "Заблокирован" if u in banned else "Активен"
        if u == MAIN_ADMIN_ID:
            role = "Главный админ"
        elif u in admins:
            role = "Админ"
        elif any(tv.get("uid") == u for tv in db.get("assigned_teachers", {}).values()):
            role = "Учитель"
        else:
            role = "Пользователь"
        sub_count = sum(1 for subs in all_subs.values() if u in subs)
        wins = game_scores.get(str(u), {}).get("wins", 0)
        ban_u = ban_until_map.get(str(u), "—")
        if ban_u and ban_u != "—":
            try: ban_u = datetime.fromisoformat(ban_u).strftime("%d.%m.%Y %H:%M")
            except: pass
        w.writerow([u, uname, reg_dt, stars, open_t, clos_t, status, role, sub_count, wins, ban_u])
    buf.seek(0)
    return io.BytesIO(buf.getvalue().encode("utf-8-sig"))

def make_txt_stats(db: dict) -> io.BytesIO:
    reviews  = db.get("reviews", [])
    tickets  = db.get("tickets", [])
    answered = db.get("answered", [])
    users    = db.get("users", [])
    news     = db.get("news", [])
    banned   = db.get("banned", [])
    admins   = db.get("admins", [])
    avg_str  = "—"
    if reviews:
        avg = sum(r.get("stars", 0) for r in reviews) / len(reviews)
        avg_str = f"{avg:.1f} из 5 ({len(reviews)} отзывов)"
    stars_dist = {i: 0 for i in range(1, 6)}
    for r in reviews:
        s = r.get("stars", 0)
        if s in stars_dist: stars_dist[s] += 1
    stars_bar = "  ".join(f"{i}*:{stars_dist[i]}" for i in range(5, 0, -1))
    total_tickets = len(tickets) + len(answered)
    polls    = db.get("polls", [])
    ideas    = db.get("ideas", [])
    teachers = db.get("assigned_teachers", {})
    t_count  = sum(1 for tv in teachers.values() if tv.get("uid"))
    subs     = db.get("teacher_subs", {})
    total_subs = sum(len(v) for v in subs.values())
    tq_count = len(db.get("teacher_questions", []))
    visits   = db.get("section_visits", {})
    top_visit = sorted(visits.items(), key=lambda x: -x[1])[:5]
    lines = [
        "СТАТИСТИКА БОТА ГИМНАЗИИ 196",
        f"Дата выгрузки: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        "",
        "== ПОЛЬЗОВАТЕЛИ ==",
        f"Зарегистрировано: {len(users)}",
        f"В чёрном списке: {len(banned)}",
        f"Администраторов: {len(admins) + 1}",
        f"Учителей с аккаунтом: {t_count}",
        "",
        "== ОБРАЩЕНИЯ ==",
        f"Открытых (ожидают ответа): {len(tickets)}",
        f"Закрытых (отвечено): {len(answered)}",
        f"Всего за всё время: {total_tickets}",
        "",
        "== УЧИТЕЛЯ ==",
        f"Всего подписок на учителей: {total_subs}",
        f"Вопросов учителям: {tq_count}",
        "",
        "== ОЦЕНКИ ==",
        f"Средняя оценка: {avg_str}",
        f"Распределение: {stars_bar}",
        "",
        "== КОНТЕНТ ==",
        f"Новостей опубликовано: {len(news)}",
        f"Активных опросов: {len(polls)}",
        f"Идей предложено: {len(ideas)}",
        "",
        "== ТОП РАЗДЕЛОВ ==",
    ] + [f"  {k}: {v}" for k, v in top_visit]
    return io.BytesIO("\n".join(lines).encode("utf-8-sig"))

async def send_export_backup(target, db):
    if not os.path.exists(DATA_FILE):
        await target.reply_text("❌ Файл базы данных не найден.")
        return
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    with open(DATA_FILE, "rb") as f:
        await target.reply_document(document=f, filename=f"backup_{now_str}.json",
            caption=f"💾 Резервная копия БД\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

async def send_export_reviews(target, db):
    reviews = db.get("reviews", [])
    if not reviews:
        await target.reply_text("⭐️ Оценок пока нет.")
        return
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    buf = make_csv_reviews(db)
    buf.name = f"reviews_{now_str}.csv"
    await target.reply_document(document=buf, filename=f"reviews_{now_str}.csv",
        caption=f"⭐️ Оценки бота — {len(reviews)} шт.\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

async def send_export_users(target, db):
    users = db.get("users", [])
    if not users:
        await target.reply_text("👥 Пользователей пока нет.")
        return
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    buf = make_csv_users(db)
    buf.name = f"users_{now_str}.csv"
    await target.reply_document(document=buf, filename=f"users_{now_str}.csv",
        caption=f"👥 Список пользователей — {len(users)} чел.\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

async def send_export_stats(target, db):
    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    buf = make_txt_stats(db)
    buf.name = f"stats_{now_str}.txt"
    await target.reply_document(document=buf, filename=f"stats_{now_str}.txt",
        caption=f"📊 Статистика бота\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")

async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    rows = []
    if is_main_admin(uid):
        rows.append([InlineKeyboardButton("💾 Резервная копия БД", callback_data="exp_backup")])
    rows.append([InlineKeyboardButton("⭐️ Оценки пользователей",  callback_data="exp_reviews")])
    rows.append([InlineKeyboardButton("👥 Список пользователей",   callback_data="exp_users")])
    rows.append([InlineKeyboardButton("📊 Статистика бота",        callback_data="exp_stats")])
    if is_main_admin(uid):
        rows.append([InlineKeyboardButton("📦 Всё сразу",          callback_data="exp_all")])
    else:
        rows.append([InlineKeyboardButton("📦 Всё сразу",          callback_data="exp_all_nodb")])
    rows.append([InlineKeyboardButton("❌ Отмена",                  callback_data="pager_close")])
    await update.message.reply_text(
        "📤 *Экспорт данных*\n\nВыберите что выгрузить:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows))

# ══════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНАЯ: ПРЕДПРОСМОТР РАССЫЛКИ
# ══════════════════════════════════════════
async def show_broadcast_preview(q, ctx, text: str):
    ctx.user_data["broadcast_text"] = text
    now      = datetime.now().strftime("%d.%m.%Y %H:%M")
    preview  = f"📢 *Новая рассылка!*\n\nИнформация от администрации:\n\n📅 {now}\n\n{text}"
    photo_id = ctx.user_data.get("broadcast_photo")
    photo_str = "\n📸 Фото: прикреплено" if photo_id else ""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Отправить сейчас",   callback_data="broadcast_confirm")],
        [InlineKeyboardButton("⏰ Запланировать",       callback_data="broadcast_schedule")],
        [InlineKeyboardButton("📸 Изменить фото",      callback_data="bc_change_photo")],
        [InlineKeyboardButton("❌ Отменить",            callback_data="broadcast_cancel")],
    ])
    await q.edit_message_text(
        f"Предпросмотр:{photo_str}\n\n{preview}\n\n*Когда отправить?*",
        reply_markup=kb, parse_mode="Markdown")

# ══════════════════════════════════════════
#  CALLBACK-ОБРАБОТЧИК
# ══════════════════════════════════════════
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    await q.answer()
    d   = q.data
    uid = q.from_user.id

    if is_banned(uid):
        await q.edit_message_text("❌ Вы заблокированы в этом боте.")
        return

    # ── noop (счётчик страниц) ───────────────────────────────────────────
    if d == "noop":
        return

    # ── Закрыть листалку ────────────────────────────────────────────────
    if d == "pager_close":
        await delete_or_clear(q)
        return

    # ── Главное меню ─────────────────────────────────────────────────────
    if d == "main_menu":
        await delete_or_clear(q)
        return

    # ── Разделы меню ────────────────────────────────────────────────────
    if d == "sec_parents":
        txt = (
            "Гимназия №196 в Санкт-Петербурге – это образовательное учреждение, "
            "предлагающее широкий спектр учебных программ.\n"
            "Адрес: Санкт-Петербург, пр. Ударников, 31.\n\nКонтакты:\n"
            "Телефон: +7 (812) 417-22-02\nЭлектронная почта: school196@bk.ru"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Сайт",      url="https://196spb.edusite.ru/")],
            [InlineKeyboardButton("VK ВКонтакте", url="https://vk.com/gym196")],
            [InlineKeyboardButton("📞 Связь",     callback_data="contact_mode")],
            [InlineKeyboardButton("🔙 Назад",     callback_data="main_menu")],
        ])
        db = load_data()
        try: await q.message.delete()
        except: pass
        await send_section_photo(q.message.chat, q.message.chat.id, "contact", txt, kb, db)
        return

    if d == "sec_teachers":
        track_section("Для учителей")
        db = load_data()
        txt_t = ('Дорогой учитель, если вы хотите, чтобы ваше сообщение/ссылки были в разделе '
                 '"Выбор Предмета", свяжитесь с нами лично в гимназии и мы все обсудим и разместим.')
        kb_t = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
        try: await q.message.delete()
        except: pass
        await send_section_photo(q.message.chat, q.message.chat.id, "teachers", txt_t, kb_t, db)
        return

    if d == "sec_students":
        track_section("Для учеников")
        db = load_data()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Расписание уроков",   url="https://drive.google.com/file/d/1YjKO0N7Pbvq2IHAkSy5cpr2cwvisV0OT/view")],
            [InlineKeyboardButton("🔔 Расписание звонков",  callback_data="bell_schedule")],
            [InlineKeyboardButton("🎮 Игра",                callback_data="game_start")],
            [InlineKeyboardButton("📅 До каникул",          callback_data="holidays_countdown")],
            [InlineKeyboardButton("🧠 Викторина",            callback_data="quiz_start")],
            [InlineKeyboardButton("🏠 В меню",              callback_data="main_menu")],
        ])
        caption = (
            "Привет, гимназист! Здесь ты можешь:\n"
            "• Посмотреть расписание уроков\n"
            "• Посмотреть расписание звонков\n"
            "• Поиграть в игру\n"
            "• Узнать сколько дней до каникул"
        )
        try: await q.message.delete()
        except: pass
        await send_section_photo(q.message.chat, q.message.chat.id, "students", caption, kb, db)
        return

    if d == "bell_schedule":
        db = load_data()
        lines = "\n".join(f"{name}   {time}" for name, time in BELL_SCHEDULE)
        caption = f"🔔 Расписание звонков:\n\n{lines}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="sec_students")]])
        try: await q.message.delete()
        except: pass
        await send_section_photo(q.message.chat, q.message.chat.id, "schedule", caption, kb, db)
        return

    if d == "sec_about":
        track_section("О разработке")
        db = load_data()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Предложить идею", callback_data="idea_mode")],
            [InlineKeyboardButton("⭐️ Оценить бота",   callback_data="review_start")],
            [InlineKeyboardButton("📊 Опросы",          callback_data="polls_list")],
            [InlineKeyboardButton("❓ FAQ",              callback_data="faq_menu")],
            [InlineKeyboardButton("🔙 Назад",           callback_data="main_menu")],
        ])
        txt_a = ("Данный бот создан командой 8 класса. "
                 "Вы можете предложить идею, оставить оценку или пройти опрос.")
        try: await q.message.delete()
        except: pass
        await send_section_photo(q.message.chat, q.message.chat.id, "about", txt_a, kb, db)
        return

    # ── Выбор предмета (числовые индексы, лимит callback 64 байта) ──────
    if d in ("sec_subjects", "subjects_back"):
        track_section("Выбор предмета")
        db = load_data()
        # Если пользователь — учитель, показываем выбор страницы
        teacher_key = next(
            (tk for tk, tv in db.get("assigned_teachers", {}).items() if tv.get("uid") == uid),
            None)
        if teacher_key and d == "sec_subjects":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 На свою страницу",      callback_data=f"my_teacher_page_{teacher_key}")],
                [InlineKeyboardButton("📚 В выбор предмета",      callback_data="subjects_back")],
                [InlineKeyboardButton("🔙 Назад",                 callback_data="main_menu")],
            ])
            await q.edit_message_text("Выберите страницу:", reply_markup=kb)
            return
        subjects = list(SUBJECT_TEACHERS.keys())
        indexed  = list(enumerate(subjects))
        rows     = list(chunks(indexed, 2))
        kb       = [[InlineKeyboardButton(s, callback_data=f"si_{i}") for i, s in row] for row in rows]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        try:
            await q.edit_message_text("Выберите предмет:", reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            await q.message.delete()
            await q.message.chat.send_message("Выберите предмет:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("si_"):
        si       = int(d[3:])
        subjects = list(SUBJECT_TEACHERS.keys())
        subject  = subjects[si]
        teachers = SUBJECT_TEACHERS[subject]
        indexed  = list(enumerate(teachers))
        rows     = list(chunks(indexed, 2))
        kb       = [[InlineKeyboardButton(t["name"], callback_data=f"ti_{si}_{ti}") for ti, t in row] for row in rows]
        # Проверяем — является ли текущий пользователь учителем этого предмета
        db = load_data()
        for t_key, tv in db.get("assigned_teachers", {}).items():
            if tv.get("uid") == uid:
                key_si, key_ti = t_key.split("_", 1)
                if int(key_si) == si:
                    kb.insert(0, [InlineKeyboardButton(
                        "👤 Открыть мою страницу", callback_data=f"my_teacher_page_{t_key}")])
                    break
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="subjects_back")])
        try:
            await q.edit_message_text(f"Учителя — {subject}:", reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            await q.message.delete()
            await q.message.chat.send_message(f"Учителя — {subject}:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("ti_"):
        _, si_str, ti_str = d.split("_", 2)
        si, ti   = int(si_str), int(ti_str)
        subjects = list(SUBJECT_TEACHERS.keys())
        subject  = subjects[si]
        teacher  = SUBJECT_TEACHERS[subject][ti]
        db       = load_data()
        t_key    = f"{si}_{ti}"
        t_info   = db.get("teacher_info", {}).get(t_key, "➖")
        t_room   = db.get("teacher_room", {}).get(t_key, "➖")
        t_photo  = db.get("teacher_photo", {}).get(t_key)
        t_files  = db.get("teacher_files", {}).get(t_key, [])
        txt = f"👤 *{teacher['name']}*"
        if teacher.get("extra"):
            txt += f"\n\n{teacher['extra']}"
        if teacher.get("url"):
            txt += f"\n\n[Персональная страница]({teacher['url']})"
        txt += f"\n\n🚪 *Кабинет:* {t_room}"
        txt += f"\n\n📝 *Информация от учителя:*\n{t_info}"
        if t_files:
            fnames = "\n".join(f"• {f['name']}" for f in t_files)
            txt += f"\n\n📎 *Файлы:*\n{fnames}"
        # Кнопки
        kb_rows = []
        if t_files:
            kb_rows.append([InlineKeyboardButton("📥 Скачать файлы", callback_data=f"tfiles_{t_key}")])
        # Кнопка подписки
        db2 = load_data()
        is_subbed = uid in db2.get("teacher_subs", {}).get(t_key, [])
        sub_label = "🔕 Отписаться" if is_subbed else "🔔 Подписаться на учителя"
        kb_rows.append([InlineKeyboardButton(sub_label, callback_data=f"sub_teacher_{t_key}")])
        kb_rows.append([InlineKeyboardButton("❓ Задать вопрос учителю", callback_data=f"ask_teacher_{t_key}")])
        kb_rows.append([InlineKeyboardButton("🔙 Назад", callback_data=f"si_{si}")])
        kb = InlineKeyboardMarkup(kb_rows)
        if t_photo:
            try:
                await q.edit_message_media(InputMediaPhoto(media=t_photo, caption=txt, parse_mode="Markdown"))
                await q.edit_message_reply_markup(reply_markup=kb)
            except:
                await q.message.reply_photo(t_photo, caption=txt, parse_mode="Markdown", reply_markup=kb)
        else:
            await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
        return

    # ── Новости ─────────────────────────────────────────────────────────
    if d.startswith("news_"):
        page      = int(d[5:])
        db        = load_data()
        news_list = db.get("news", [])
        if not news_list:
            await q.edit_message_text("📰 Новостей пока нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="main_menu")]]))
            return
        total = len(news_list)
        idx   = max(0, min(page, total - 1))
        n     = news_list[idx]
        pin_icon = "📌 " if n.get("pinned") else ""
        txt   = (f"{pin_icon}🔔 *Новая новость!*\n📩 От: {n.get('sender')}\n"
                 f"📅 Опубликовано: {n.get('pub_date')}\n"
                 f"📆 Дата проведения события: {n.get('event_date', 'Не указана')}\n\n"
                 f"Информация о событии:\n{n.get('text')}")
        nav = []
        if idx > 0:         nav.append(InlineKeyboardButton("⬅️ Назад",   callback_data=f"news_{idx-1}"))
        if idx < total - 1: nav.append(InlineKeyboardButton("➡️ Вперёд", callback_data=f"news_{idx+1}"))
        kb = []
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("🏠 В меню", callback_data="main_menu")])
        if n.get("photo"):
            try:
                await q.edit_message_media(
                    InputMediaPhoto(media=n["photo"], caption=txt, parse_mode="Markdown"))
                await q.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
            except:
                await q.message.reply_photo(n["photo"], caption=txt, parse_mode="Markdown",
                                            reply_markup=InlineKeyboardMarkup(kb))
        else:
            try:
                await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
            except:
                await q.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ── Игра ────────────────────────────────────────────────────────────
    if d == "game_start":
        ctx.user_data["game_score"] = {"user": 0, "bot": 0}
        await show_game(q, ctx)
        return

    if d in ("game_rock", "game_scissors", "game_paper"):
        choice = d[5:]
        bot_c  = random.choice(["rock", "scissors", "paper"])
        sc     = ctx.user_data.get("game_score", {"user": 0, "bot": 0})
        if choice == bot_c:
            res = "Ничья! 🤝"
        elif GAME_BEATS[choice] == bot_c:
            res = "Вы победили! 🎉"; sc["user"] += 1
            # Сохраняем победу в профиль
            _db = load_data()
            _db.setdefault("game_wins", {})[str(uid)] = _db.get("game_wins", {}).get(str(uid), 0) + 1
            save_data(_db)
        else:
            res = "Бот победил! 🤖"; sc["bot"]  += 1
        ctx.user_data["game_score"] = sc
        await show_game(q, ctx, f"Вы: {GAME_EMOJI[choice]} | Бот: {GAME_EMOJI[bot_c]}\n{res}")
        return

    # ── Связь / Идея ────────────────────────────────────────────────────
    if d == "contact_mode":
        db = load_data()
        all_adm = list(set([MAIN_ADMIN_ID] + db.get("admins", [])))
        adm_count = len(all_adm)
        ctx.user_data["state"] = "contact"
        txt_c = (f"📞 *Связь с администрацией*\n\n"
                 f"Администраторов в сети: *{adm_count}*\n\n"
                 f"Напишите ваше сообщение и мы ответим вам как можно скорее.\n"
                 f"_Максимум 3 открытых обращения одновременно._")
        try:
            await q.edit_message_text(txt_c, parse_mode="Markdown")
        except:
            try: await q.message.delete()
            except: pass
            await q.message.chat.send_message(txt_c, parse_mode="Markdown")
        return

    if d == "idea_mode":
        ctx.user_data["state"] = "idea"
        await q.edit_message_text("Напишите вашу идею, она будет отправлена разработчикам:")
        return

    # ── Оценка бота ─────────────────────────────────────────────────────
    if d in ("review_start", "review_change"):
        db = load_data()
        already = str(uid) in db.get("reviews_done", [])
        is_change = (d == "review_change") or already
        if already and d == "review_start":
            # Показать текущую оценку + кнопку изменить
            r = next((x for x in db.get("reviews", []) if x.get("uid") == uid), None)
            stars_str = ("⭐️" * r["stars"]) if r else "?"
            await q.edit_message_text(
                f"⭐️ Вы уже оставили оценку: {stars_str}\n\nХотите изменить её?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Изменить оценку", callback_data="review_change")],
                    [InlineKeyboardButton("🔙 Назад",           callback_data="sec_about")],
                ]))
            return
        ctx.user_data["review_is_change"] = is_change
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐️ 1", callback_data="review_stars_1"),
             InlineKeyboardButton("⭐️ 2", callback_data="review_stars_2"),
             InlineKeyboardButton("⭐️ 3", callback_data="review_stars_3"),
             InlineKeyboardButton("⭐️ 4", callback_data="review_stars_4"),
             InlineKeyboardButton("⭐️ 5", callback_data="review_stars_5")],
            [InlineKeyboardButton("🔙 Назад", callback_data="sec_about")],
        ])
        title = "✏️ *Изменить оценку*" if is_change else "⭐️ *Оцените бота*"
        await q.edit_message_text(title + "\n\nВыберите оценку от 1 до 5:",
                                   parse_mode="Markdown", reply_markup=kb)
        return

    if d.startswith("review_stars_"):
        stars = int(d[-1])
        ctx.user_data["review_stars"] = stars
        ctx.user_data["state"] = "review_liked"
        await q.edit_message_text(
            f"Вы выбрали: {'⭐️' * stars}\n\n"
            f"✅ Что вам *понравилось* в боте?\n_(напишите текстом или `-`)_",
            parse_mode="Markdown")
        return

    if d.startswith("reviews_pg_"):
        if not is_admin(uid): return
        page = int(d[11:])
        await show_review_page(q, page, edit=True)
        return

    # ── Тикеты (обращения) ───────────────────────────────────────────────
    if d == "admin_tickets":
        if not is_admin(uid): return
        await show_ticket_page(q, "tickets", 0, edit=True)
        return

    if d.startswith("tickets_pg_"):
        if not is_admin(uid): return
        page = int(d[11:])
        await show_ticket_page(q, "tickets", page, edit=True)
        return

    if d.startswith("answered_pg_"):
        if not is_admin(uid): return
        page = int(d[12:])
        await show_ticket_page(q, "answered", page, edit=True)
        return

    if d.startswith("ticket_reply_"):
        if not is_admin(uid): return
        ticket_id = d[13:]
        db = load_data()
        # Проверяем что тикет ещё в неотвеченных
        ticket = next((t for t in db.get("tickets", []) if t.get("id") == ticket_id), None)
        if not ticket:
            await q.edit_message_text("⚠️ Это обращение уже было отвечено другим администратором.")
            return
        ctx.user_data["reply_ticket_id"] = ticket_id
        ctx.user_data["state"] = "reply_ticket"
        await q.edit_message_text(
            f"📩 Обращение от {ticket.get('username','?')}:\n\n{ticket.get('text','')}\n\n"
            f"✍️ Напишите ваш ответ:")
        return

    # ── Рассылка ────────────────────────────────────────────────────────
    if d == "bc_use_template":
        if not is_admin(uid): return
        await show_broadcast_preview(q, ctx, BROADCAST_TEMPLATE)
        return

    if d == "bc_use_template_tech":
        if not is_admin(uid): return
        await show_broadcast_preview(q, ctx, BROADCAST_TEMPLATE_TECH)
        return

    if d in ("bc_group_all", "bc_group_teachers", "bc_group_students"):
        if not is_admin(uid): return
        ctx.user_data["bc_group"] = d[9:]  # "all", "teachers", "students"
        kb_txt = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Шаблон: VK группа",          callback_data="bc_use_template")],
            [InlineKeyboardButton("⚠️ Шаблон: Технические работы", callback_data="bc_use_template_tech")],
            [InlineKeyboardButton("✏️ Написать свой текст",         callback_data="bc_custom")],
            [InlineKeyboardButton("❌ Отмена",                      callback_data="broadcast_cancel")],
        ])
        group_names = {"all": "всем", "teachers": "только учителям", "students": "только ученикам"}
        g = group_names.get(d[9:], "всем")
        await q.edit_message_text(
            f"📢 Рассылка *{g}*\n\nВыберите текст:",
            parse_mode="Markdown", reply_markup=kb_txt)
        return

    if d == "bc_custom":
        if not is_admin(uid): return
        ctx.user_data["state"] = "broadcast_text"
        await q.edit_message_text("Введите текст рассылки:")
        return

    if d == "bc_change_photo":
        if not is_admin(uid): return
        ctx.user_data["state"] = "broadcast_photo"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Убрать фото", callback_data="bc_skip_photo")],
            [InlineKeyboardButton("❌ Отменить",    callback_data="broadcast_cancel")],
        ])
        await q.edit_message_text("📸 Отправьте новое фото или нажмите «Убрать фото»:",
                                   reply_markup=kb)
        return

    if d == "broadcast_confirm":
        txt_send  = ctx.user_data.pop("broadcast_text", "")
        photo_id  = ctx.user_data.pop("broadcast_photo", None)
        ctx.user_data.pop("state", None)
        db  = load_data()
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        msg = f"📢 *Новая рассылка!*\n\nИнформация от администрации:\n\n📅 {now}\n\n{txt_send}"
        # Определяем аудиторию
        bc_group = ctx.user_data.pop("bc_group", "all")
        all_users = db.get("users", [])
        assigned  = db.get("assigned_teachers", {})
        teacher_uids = [tv.get("uid") for tv in assigned.values() if tv.get("uid")]
        if bc_group == "teachers":
            targets = [u for u in all_users if u in teacher_uids]
        elif bc_group == "students":
            targets = [u for u in all_users if u not in teacher_uids]
        else:
            targets = all_users
        ok, fail = 0, 0
        for u in targets:
            try:
                if photo_id:
                    await ctx.bot.send_photo(u, photo_id, caption=msg, parse_mode="Markdown")
                else:
                    await ctx.bot.send_message(u, msg, parse_mode="Markdown")
                ok += 1
            except: fail += 1
        # Сохраняем в архив рассылок
        admin_name = f"@{q.from_user.username}" if q.from_user.username else str(uid)
        db.setdefault("broadcasts", []).append({
            "text": txt_send, "photo": photo_id, "date": now,
            "sent_by": admin_name, "ok": ok, "fail": fail
        })
        save_data(db)
        await q.edit_message_text(f"✅ Рассылка завершена!\nУспешно: {ok}\nНеудачно: {fail}")
        return

    if d == "broadcast_schedule":
        if not is_admin(uid): return
        ctx.user_data["state"] = "broadcast_schedule_dt"
        await q.edit_message_text(
            "⏰ *Запланировать рассылку*\n\n"
            "Введите дату и время отправки в формате:\n"
            "`ДД.ММ.ГГГГ ЧЧ:ММ`\n\n"
            "_Например: 25.02.2026 18:00_",
            parse_mode="Markdown")
        return

    if d == "bc_skip_photo":
        if not is_admin(uid): return
        ctx.user_data.pop("broadcast_photo", None)
        ctx.user_data.pop("state", None)
        await show_broadcast_preview(q, ctx, ctx.user_data.get("broadcast_text", ""))
        return

    if d == "broadcast_cancel":
        ctx.user_data.pop("broadcast_text", None)
        ctx.user_data.pop("broadcast_photo", None)
        ctx.user_data.pop("state", None)
        await q.edit_message_text("Рассылка отменена.")
        return

    # ── Событие ─────────────────────────────────────────────────────────
    if d in ("event_sender_admin", "event_sender_school"):
        ctx.user_data["event_sender"] = "Админ" if d == "event_sender_admin" else "Администрация гимназии"
        ctx.user_data["state"]        = "event_date"
        await q.edit_message_text(
            "Введите дату проведения мероприятия в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Или напишите `-`, если дата неизвестна:")
        return

    if d == "event_skip_photo":
        ctx.user_data.pop("event_photo", None)
        ctx.user_data.pop("state", None)
        now     = datetime.now().strftime("%d.%m.%Y %H:%M")
        preview = (f"🔔 *Новая новость!*\n📩 От: {ctx.user_data.get('event_sender')}\n"
                   f"📅 Опубликовано: {now}\n"
                   f"📆 Дата проведения события: {ctx.user_data.get('event_date', 'Не указана')}\n\n"
                   f"Информация о событии:\n{ctx.user_data.get('event_text', '')}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Отправить", callback_data="event_confirm"),
             InlineKeyboardButton("❌ Отменить",  callback_data="event_cancel")],
        ])
        await q.edit_message_text(f"Предпросмотр:\n\n{preview}", reply_markup=kb, parse_mode="Markdown")
        return

    if d == "event_confirm":
        db  = load_data()
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        photo_id = ctx.user_data.get("event_photo")
        item = {
            "sender":     ctx.user_data.get("event_sender"),
            "pub_date":   now,
            "event_date": ctx.user_data.get("event_date", "Не указана"),
            "text":       ctx.user_data.get("event_text", ""),
            "photo":      photo_id,
        }
        db.setdefault("news", []).append(item)
        save_data(db)
        msg = (f"🔔 *Новая новость!*\n📩 От: {item['sender']}\n📅 Опубликовано: {now}\n"
               f"📆 Дата проведения события: {item['event_date']}\n\nИнформация о событии:\n{item['text']}")
        for u in db.get("users", []):
            try:
                if photo_id:
                    await ctx.bot.send_photo(u, photo_id, caption=msg, parse_mode="Markdown")
                else:
                    await ctx.bot.send_message(u, msg, parse_mode="Markdown")
            except: pass
        await q.edit_message_text("✅ Новость опубликована!")
        for k in ["event_sender", "event_date", "event_text", "event_photo", "state"]:
            ctx.user_data.pop(k, None)
        return

    if d == "event_cancel":
        for k in ["event_sender", "event_date", "event_text", "state"]:
            ctx.user_data.pop(k, None)
        await q.edit_message_text("Создание новости отменено.")
        return

    # ── Управление админами ─────────────────────────────────────────────
    if d == "admin_add":
        if not is_main_admin(uid): return
        ctx.user_data["state"] = "admin_add"
        await q.edit_message_text("Введите ID пользователя для назначения администратором:")
        return

    if d == "admin_remove_list":
        if not is_main_admin(uid): return
        db     = load_data()
        admins = db.get("admins", [])
        if not admins:
            await q.edit_message_text("Обычных администраторов нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
            return
        kb = [[InlineKeyboardButton(str(a), callback_data=f"remove_admin_{a}")] for a in admins]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        await q.edit_message_text("Выберите админа для удаления:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("remove_admin_"):
        if not is_main_admin(uid): return
        target = int(d[13:])
        db     = load_data()
        if target in db.get("admins", []):
            db["admins"].remove(target)
            save_data(db)
        await q.edit_message_text(f"✅ Админ `{target}` удалён.", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return

    if d == "admin_ban":
        if not is_admin(uid): return
        ctx.user_data["state"] = "admin_ban"
        await q.edit_message_text("Введите ID пользователя для блокировки:")
        return

    if d == "admin_unban":
        if not is_admin(uid): return
        db      = load_data()
        banned  = db.get("banned", [])
        reasons = db.get("ban_reasons", {})
        users_info = db.get("users_info", {})
        if not banned:
            await q.edit_message_text("🚫 Чёрный список пуст.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
            return
        rows = []
        for b in banned:
            uname  = users_info.get(str(b), {}).get("username", "—")
            reason = reasons.get(str(b), "—")
            label  = f"🔓 {uname} ({b}) — {reason[:20]}{"..." if len(reason)>20 else ""}"
            rows.append([InlineKeyboardButton(label, callback_data=f"unban_select_{b}")])
        rows.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        await q.edit_message_text("Выберите пользователя для разблокировки:",
            reply_markup=InlineKeyboardMarkup(rows))
        return

    if d.startswith("unban_select_"):
        if not is_admin(uid): return
        target = int(d[13:])
        db     = load_data()
        reason = db.get("ban_reasons", {}).get(str(target), "—")
        uname  = db.get("users_info", {}).get(str(target), {}).get("username", "—")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, разблокировать", callback_data=f"unban_confirm_{target}")],
            [InlineKeyboardButton("❌ Отмена",             callback_data="admin_unban")],
        ])
        await q.edit_message_text(
            f"⚠️ Разблокировать пользователя?\n\n"
            f"👤 @{uname} (ID: `{target}`)\n"
            f"📝 Причина блокировки: {reason}",
            parse_mode="Markdown", reply_markup=kb)
        return

    if d.startswith("unban_confirm_"):
        if not is_admin(uid): return
        target = int(d[14:])
        db = load_data()
        if target in db.get("banned", []):
            db["banned"].remove(target)
        db.get("ban_reasons", {}).pop(str(target), None)
        save_data(db)
        try:
            await ctx.bot.send_message(target, "✅ Вы были разблокированы администрацией.")
        except: pass
        await q.edit_message_text(
            f"✅ Пользователь `{target}` разблокирован.", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return

    if d.startswith("unban_cancel_"):
        if not is_admin(uid): return
        await q.edit_message_text("❌ Разблокировка отменена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return

    # ── Управление новостями ─────────────────────────────────────────────
    if d == "admin_news":
        if not is_admin(uid): return
        db        = load_data()
        news_list = db.get("news", [])
        if not news_list:
            await q.edit_message_text("📰 Новостей нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
            return
        kb = [[InlineKeyboardButton(
                f"{"📌 " if n.get("pinned") else ""}#{i+1} {n.get('pub_date','')[:10]}",
                callback_data=f"admin_news_view_{i}")]
              for i, n in enumerate(news_list)]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        await q.edit_message_text("Выберите новость:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("admin_news_view_"):
        if not is_admin(uid): return
        idx       = int(d[16:])
        db        = load_data()
        news_list = db.get("news", [])
        if 0 <= idx < len(news_list):
            n      = news_list[idx]
            pinned = n.get("pinned", False)
            pin_icon = "📌 " if pinned else ""
            txt = (f"{pin_icon}🔔 *Новость #{idx+1}*\n📩 От: {n.get('sender')}\n📅 {n.get('pub_date')}\n"
                   f"📆 Дата события: {n.get('event_date', 'Не указана')}\n\n{n.get('text')}")
            pin_btn = InlineKeyboardButton("📌 Открепить", callback_data=f"unpin_news_{idx}") if pinned \
                      else InlineKeyboardButton("📌 Закрепить", callback_data=f"pin_news_{idx}")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Редактировать текст", callback_data=f"edit_news_{idx}")],
                [pin_btn],
                [InlineKeyboardButton("🗑 Удалить новость",     callback_data=f"del_news_{idx}")],
                [InlineKeyboardButton("🔙 Назад",               callback_data="admin_news")],
            ])
            await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
        return

    if d.startswith("del_news_"):
        if not is_admin(uid): return
        idx       = int(d[9:])
        db        = load_data()
        news_list = db.get("news", [])
        if 0 <= idx < len(news_list):
            news_list.pop(idx)
            db["news"] = news_list
            save_data(db)
        await q.edit_message_text("✅ Новость удалена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📰 Управление новостями", callback_data="admin_news")]]))
        return

    if d.startswith("pin_news_"):
        if not is_admin(uid): return
        idx       = int(d[9:])
        db        = load_data()
        news_list = db.get("news", [])
        if 0 <= idx < len(news_list):
            # Снимаем закрепление с других новостей
            for n in news_list: n["pinned"] = False
            news_list[idx]["pinned"] = True
            # Перемещаем закреплённую в начало
            pinned_item = news_list.pop(idx)
            news_list.insert(0, pinned_item)
            db["news"] = news_list
            save_data(db)
        await q.edit_message_text("📌 Новость закреплена и перемещена в начало!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📰 К новостям", callback_data="admin_news")]]))
        return

    if d.startswith("unpin_news_"):
        if not is_admin(uid): return
        idx       = int(d[11:])
        db        = load_data()
        news_list = db.get("news", [])
        if 0 <= idx < len(news_list):
            news_list[idx]["pinned"] = False
            db["news"] = news_list
            save_data(db)
        await q.edit_message_text("✅ Новость откреплена.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📰 К новостям", callback_data="admin_news")]]))
        return

    if d.startswith("edit_news_"):
        if not is_admin(uid): return
        idx = int(d[10:])
        ctx.user_data["edit_news_idx"] = idx
        ctx.user_data["state"] = "edit_news_text"
        db = load_data()
        news_list = db.get("news", [])
        old_text = news_list[idx].get("text", "") if 0 <= idx < len(news_list) else ""
        await q.edit_message_text(
            f"✏️ *Редактирование новости #{idx+1}*\n\n"
            f"Текущий текст:\n_{old_text}_\n\n"
            f"Введите новый текст:",
            parse_mode="Markdown")
        return

    # ── Экспорт данных ──────────────────────────────────────────────────
    if d.startswith("exp_"):
        if not is_admin(uid): return
        db = load_data()
        await delete_or_clear(q, send_menu=False)
        msg = q.message  # используем как target для reply

        if d == "exp_backup":
            if not is_main_admin(uid):
                await msg.reply_text("❌ Только для главного администратора.")
                return
            await send_export_backup(msg, db)

        elif d == "exp_reviews":
            await send_export_reviews(msg, db)

        elif d == "exp_users":
            await send_export_users(msg, db)

        elif d == "exp_stats":
            await send_export_stats(msg, db)

        elif d in ("exp_all", "exp_all_nodb"):
            await msg.reply_text("📦 Готовлю все файлы...")
            if d == "exp_all" and is_main_admin(uid):
                await send_export_backup(msg, db)
            await send_export_reviews(msg, db)
            await send_export_users(msg, db)
            await send_export_stats(msg, db)
            await msg.reply_text("✅ Все файлы отправлены!")
        return

    # ── Архив рассылок ──────────────────────────────────────────────────
    if d.startswith("barch_"):
        if not is_admin(uid): return
        if d.startswith("barch_repeat_"):
            pi  = int(d[13:])
            db  = load_data()
            arch = db.get("broadcasts", [])
            if pi < len(arch):
                ctx.user_data["broadcast_text"] = arch[pi]["text"]
                await show_broadcast_preview(q, ctx, arch[pi]["text"])
            return
        page = int(d[6:])
        await show_broadcast_archive(q, page, edit=True)
        return

    # ── История банов ────────────────────────────────────────────────────
    if d.startswith("banh_"):
        if not is_admin(uid): return
        page = int(d[5:])
        await show_ban_history(q, page, edit=True)
        return

    if d == "ban_history":
        if not is_admin(uid): return
        await show_ban_history(q, 0, edit=True)
        return

    # ── Закреплённое объявление ──────────────────────────────────────────
    if d == "pinned_set":
        if not is_main_admin(uid): return
        ctx.user_data["state"] = "pinned_set"
        await q.edit_message_text(
            "📌 Введите текст закреплённого объявления:\n\n"
            "_Оно будет показываться всем при /start_",
            parse_mode="Markdown")
        return

    if d == "pinned_clear":
        if not is_main_admin(uid): return
        db = load_data()
        db.pop("pinned_announcement", None)
        save_data(db)
        await q.edit_message_text("✅ Закреплённое объявление снято.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return

    if d == "pinned_view":
        if not is_main_admin(uid): return
        db     = load_data()
        pinned = db.get("pinned_announcement")
        if pinned:
            txt_p = f"📌 *Текущее объявление:*\n\n{pinned}"
        else:
            txt_p = "📌 Закреплённое объявление не установлено."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Установить/изменить", callback_data="pinned_set")],
            [InlineKeyboardButton("🗑 Снять объявление",    callback_data="pinned_clear")],
            [InlineKeyboardButton("🔙 Назад",               callback_data="admin_panel")],
        ])
        await q.edit_message_text(txt_p, parse_mode="Markdown", reply_markup=kb)
        return

    # ── Каникулы (для учеников) ──────────────────────────────────────────
    if d == "holidays_countdown":
        days = (HOLIDAY_DATE - datetime.now()).days
        if days < 0:
            txt_h = "🎉 Каникулы уже идут! Отдыхайте!"
        elif days == 0:
            txt_h = "🎉 Сегодня начинаются каникулы!"
        else:
            txt_h = f"📅 До каникул осталось: *{days} дн.*\n\nКаникулы с {HOLIDAY_DATE.strftime('%d.%m.%Y')}"
        await q.edit_message_text(txt_h, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="sec_students")]]))
        return

    # ── Статистика (кнопка в /admin) ────────────────────────────────────
    if d == "admin_stats":
        if not is_admin(uid): return
        db       = load_data()
        reviews  = db.get("reviews", [])
        tickets  = db.get("tickets", [])
        answered = db.get("answered", [])
        users    = db.get("users", [])
        news     = db.get("news", [])
        banned   = db.get("banned", [])
        admins   = db.get("admins", [])
        polls    = db.get("polls", [])
        visits   = db.get("section_visits", {})
        avg_str  = "—"
        if reviews:
            avg = sum(r.get("stars", 0) for r in reviews) / len(reviews)
            avg_str = f"{avg:.1f} ⭐️ ({len(reviews)} отзывов)"
        stars_dist = {i: 0 for i in range(1, 6)}
        for r in reviews:
            s = r.get("stars", 0)
            if s in stars_dist: stars_dist[s] += 1
        stars_bar = "  ".join(f"{i}⭐️:{stars_dist[i]}" for i in range(5, 0, -1))
        total_tickets = len(tickets) + len(answered)
        visits_txt = "\n".join(f"• {k}: {v}" for k, v in sorted(visits.items(), key=lambda x: -x[1])) or "—"
        txt = (
            "📊 *Статистика бота*\n\n"
            f"👥 *Пользователи:*\n"
            f"Зарегистрировано: {len(users)}\n"
            f"В чёрном списке: {len(banned)}\n"
            f"Администраторов: {len(admins) + 1}\n\n"
            f"📩 *Обращения:*\n"
            f"Открытых (ожидают ответа): {len(tickets)}\n"
            f"Закрытых (отвечено): {len(answered)}\n"
            f"Всего за всё время: {total_tickets}\n\n"
            f"⭐️ *Оценки бота:*\n"
            f"Средняя оценка: {avg_str}\n"
            f"Распределение: {stars_bar}\n\n"
            f"📰 *Контент:*\n"
            f"Новостей опубликовано: {len(news)}\n"
            f"Активных опросов: {len(polls)}\n\n"
            f"🗂 *Посещения разделов:*\n"
            f"{visits_txt}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]])
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)
        return

    # ── Изменение информации об учителе (ets_/eti_/etu_/etd_) ─────────────
    if d.startswith("ets_"):
        if not is_main_admin(uid): return
        si       = int(d[4:])
        subjects = list(SUBJECT_TEACHERS.keys())
        subject  = subjects[si]
        teachers = SUBJECT_TEACHERS[subject]
        indexed  = list(enumerate(teachers))
        rows     = list(chunks(indexed, 2))
        kb       = [[InlineKeyboardButton(t["name"], callback_data=f"eti_{si}_{ti}") for ti, t in row] for row in rows]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="edit_teacher_stub")])
        await q.edit_message_text(f"✏️ Предмет: {subject}\nВыберите учителя:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("eti_"):
        if not is_main_admin(uid): return
        _, si_str, ti_str = d.split("_", 2)
        si, ti   = int(si_str), int(ti_str)
        subjects = list(SUBJECT_TEACHERS.keys())
        subject  = subjects[si]
        teacher  = SUBJECT_TEACHERS[subject][ti]
        db       = load_data()
        t_key    = f"{si}_{ti}"
        t_info   = db.get("teacher_info", {}).get(t_key, "➖")
        t_room   = db.get("teacher_room", {}).get(t_key, "➖")
        txt_msg  = (
            f"👤 *{teacher['name']}*\n"
            f"📚 Предмет: {subject}\n"
            f"🚪 Кабинет: {t_room}\n\n"
            f"📝 *Информация от учителя:*\n{t_info}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить информацию",  callback_data=f"etu_{si}_{ti}")],
            [InlineKeyboardButton("🗑 Удалить информацию",   callback_data=f"etd_{si}_{ti}")],
            [InlineKeyboardButton("🚪 Изменить кабинет",     callback_data=f"etr_{si}_{ti}")],
            [InlineKeyboardButton("❌ Удалить кабинет",      callback_data=f"etrd_{si}_{ti}")],
            [InlineKeyboardButton("📸 Изменить фото",        callback_data=f"etph_{si}_{ti}")],
            [InlineKeyboardButton("🗑 Удалить фото",         callback_data=f"etphd_{si}_{ti}")],
            [InlineKeyboardButton("🔙 Назад",                callback_data=f"ets_{si}")],
        ])
        await q.edit_message_text(txt_msg, parse_mode="Markdown", reply_markup=kb)
        return

    if d.startswith("etu_"):
        if not is_main_admin(uid): return
        _, si_str, ti_str = d.split("_", 2)
        ctx.user_data["edit_teacher_key"] = f"{si_str}_{ti_str}"
        ctx.user_data["state"] = "edit_teacher_info"
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[int(si_str)]][int(ti_str)]
        await q.edit_message_text(
            f"✏️ Введите новую информацию для *{teacher['name']}*:\n\n"
            f"_Это будет показываться на странице учителя_",
            parse_mode="Markdown")
        return

    if d.startswith("etd_"):
        if not is_main_admin(uid): return
        _, si_str, ti_str = d.split("_", 2)
        t_key = f"{si_str}_{ti_str}"
        db    = load_data()
        db.setdefault("teacher_info", {}).pop(t_key, None)
        save_data(db)
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[int(si_str)]][int(ti_str)]
        await q.edit_message_text(
            f"✅ Информация для *{teacher['name']}* удалена (сброшена на ➖).",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data=f"eti_{si_str}_{ti_str}")]
            ]))
        return

    if d.startswith("etr_"):
        if not is_main_admin(uid): return
        _, si_str, ti_str = d.split("_", 2)
        ctx.user_data["edit_teacher_key"] = f"{si_str}_{ti_str}"
        ctx.user_data["state"] = "edit_teacher_room"
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[int(si_str)]][int(ti_str)]
        await q.edit_message_text(
            f"🚪 Введите номер кабинета для *{teacher['name']}*:\n\n"
            f"_Например: 214 или Спортивный зал_",
            parse_mode="Markdown")
        return

    if d.startswith("etrd_"):
        if not is_main_admin(uid): return
        _, si_str, ti_str = d.split("_", 2)
        t_key = f"{si_str}_{ti_str}"
        db    = load_data()
        db.setdefault("teacher_room", {}).pop(t_key, None)
        save_data(db)
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[int(si_str)]][int(ti_str)]
        await q.edit_message_text(
            f"✅ Кабинет для *{teacher['name']}* удалён (сброшен на ➖).",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data=f"eti_{si_str}_{ti_str}")]
            ]))
        return

    # ── Опросы ──────────────────────────────────────────────────────────
    if d == "polls_list":
        db    = load_data()
        polls = db.get("polls", [])
        if not polls:
            await q.edit_message_text(
                "📊 *Опросы*\n\nАктивных опросов пока нет.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="sec_about")]]))
            return
        kb = [[InlineKeyboardButton(f"📊 {p['question'][:40]}", callback_data=f"poll_view_{i}")]
              for i, p in enumerate(polls)]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="sec_about")])
        await q.edit_message_text("📊 *Опросы*\n\nВыберите опрос:", parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("poll_view_"):
        pi    = int(d[10:])
        db    = load_data()
        polls = db.get("polls", [])
        if pi >= len(polls):
            await q.answer("Опрос не найден")
            return
        p      = polls[pi]
        voters = p.get("voters", {})
        total  = sum(p.get("votes", {}).values()) or 1
        user_vote = voters.get(str(uid))
        lines  = [f"📊 *{p['question']}*\n"]
        for idx_opt, opt in enumerate(p.get("options", [])):
            cnt   = p.get("votes", {}).get(str(idx_opt), 0)
            pct   = int(cnt / total * 100)
            bar   = "█" * (pct // 10) + "░" * (10 - pct // 10)
            mark  = " ✅" if str(idx_opt) == str(user_vote) else ""
            lines.append(f"{opt}{mark}\n{bar} {pct}% ({cnt} гол.)")
        kb_rows = []
        if user_vote is None:
            kb_rows = [[InlineKeyboardButton(opt, callback_data=f"poll_vote_{pi}_{oi}")]
                        for oi, opt in enumerate(p.get("options", []))]
        kb_rows.append([InlineKeyboardButton("🔙 К списку", callback_data="polls_list")])
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if d.startswith("poll_vote_"):
        parts  = d[10:].split("_", 1)
        pi, oi = int(parts[0]), int(parts[1])
        db     = load_data()
        polls  = db.get("polls", [])
        if pi >= len(polls):
            await q.answer("Опрос не найден")
            return
        p = polls[pi]
        if str(uid) in p.get("voters", {}):
            await q.answer("Вы уже проголосовали!")
            return
        p.setdefault("votes", {})[str(oi)] = p.get("votes", {}).get(str(oi), 0) + 1
        p.setdefault("voters", {})[str(uid)] = str(oi)
        save_data(db)
        await q.answer("✅ Голос принят!")
        # Обновить отображение
        voters = p.get("voters", {})
        total  = sum(p.get("votes", {}).values()) or 1
        lines  = [f"📊 *{p['question']}*\n"]
        for idx_opt, opt in enumerate(p.get("options", [])):
            cnt  = p.get("votes", {}).get(str(idx_opt), 0)
            pct  = int(cnt / total * 100)
            bar  = "█" * (pct // 10) + "░" * (10 - pct // 10)
            mark = " ✅" if str(idx_opt) == str(oi) else ""
            lines.append(f"{opt}{mark}\n{bar} {pct}% ({cnt} гол.)")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку", callback_data="polls_list")]])
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=kb)
        return

    if d.startswith("poll_del_"):
        if not is_admin(uid): return
        pi    = int(d[9:])
        db    = load_data()
        polls = db.get("polls", [])
        if 0 <= pi < len(polls):
            polls.pop(pi)
            db["polls"] = polls
            save_data(db)
        await q.edit_message_text("🗑 Опрос удалён.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return

    if d == "admin_polls":
        if not is_admin(uid): return
        db    = load_data()
        polls = db.get("polls", [])
        if not polls:
            txt_p = "📊 Опросов пока нет."
        else:
            txt_p = "📊 *Активные опросы:*\n\n" + "\n".join(
                f"{i+1}. {p['question']} ({sum(p.get('votes',{}).values())} гол.)"
                for i, p in enumerate(polls))
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Создать опрос", callback_data="poll_create")],
            *[[InlineKeyboardButton(f"🗑 Удалить #{i+1}", callback_data=f"poll_del_{i}")]
              for i in range(len(polls))],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
        ])
        await q.edit_message_text(txt_p, parse_mode="Markdown", reply_markup=kb)
        return

    if d == "poll_create":
        if not is_admin(uid): return
        ctx.user_data["state"]        = "poll_question"
        ctx.user_data["poll_options"] = []
        await q.edit_message_text(
            "📊 *Создание опроса*\n\nВведите *вопрос* для опроса:",
            parse_mode="Markdown")
        return

    if d == "poll_add_option":
        if not is_admin(uid): return
        ctx.user_data["state"] = "poll_option"
        await q.edit_message_text(
            f"✏️ Введите вариант ответа #{len(ctx.user_data.get('poll_options', [])) + 1}:")
        return

    if d == "poll_finish_create":
        if not is_admin(uid): return
        opts = ctx.user_data.pop("poll_options", [])
        q_text = ctx.user_data.pop("poll_question", "")
        ctx.user_data.pop("state", None)
        if len(opts) < 2:
            await q.edit_message_text("❌ Нужно хотя бы 2 варианта ответа.")
            return
        db = load_data()
        db.setdefault("polls", []).append({
            "question": q_text,
            "options":  opts,
            "votes":    {str(i): 0 for i in range(len(opts))},
            "voters":   {},
            "created":  datetime.now().strftime("%d.%m.%Y %H:%M"),
        })
        save_data(db)
        await q.edit_message_text(
            f"✅ Опрос создан!\n\n*{q_text}*\nВариантов: {len(opts)}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К опросам", callback_data="admin_polls")]]))
        return

    # ── Назначение учителя (tassign_*) ────────────────────────────────────
    if d.startswith("tassign_si_"):
        if not is_main_admin(uid): return
        si       = int(d[11:])
        subjects = list(SUBJECT_TEACHERS.keys())
        subject  = subjects[si]
        teachers = SUBJECT_TEACHERS[subject]
        indexed  = list(enumerate(teachers))
        rows     = list(chunks(indexed, 2))
        kb       = [[InlineKeyboardButton(t["name"], callback_data=f"tassign_ti_{si}_{ti}") for ti, t in row] for row in rows]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        await q.edit_message_text(f"Предмет: *{subject}*\nВыберите учителя:", parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(kb))
        return

    if d.startswith("tassign_ti_"):
        if not is_main_admin(uid): return
        _, _, si_str, ti_str = d.split("_", 3)
        si, ti   = int(si_str), int(ti_str)
        t_key    = f"{si}_{ti}"
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[si]][ti]
        target_uid = ctx.user_data.pop("teacher_uid", None)
        if not target_uid:
            await q.edit_message_text("⚠️ Ошибка: пользователь не найден. Начните заново через /teacher.")
            return
        db = load_data()
        db.setdefault("assigned_teachers", {})[t_key] = {
            "uid": target_uid,
            "name": teacher["name"],
            "subject": subjects[si],
        }
        save_data(db)
        # Уведомляем назначенного пользователя
        try:
            await ctx.bot.send_message(
                target_uid,
                f"👨‍🏫 *Вы назначены учителем!*\n\n"
                f"Имя: {teacher['name']}\n"
                f"Предмет: {subjects[si]}\n\n"
                f"В разделе «Выбор Предмета» у вас теперь есть личная страница.",
                parse_mode="Markdown")
        except: pass
        await q.edit_message_text(
            f"✅ Пользователь `{target_uid}` назначен учителем!\n\n"
            f"👤 {teacher['name']}\n📚 {subjects[si]}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return

    if d.startswith("tassign_remove_"):
        if not is_main_admin(uid): return
        t_key = d[15:]
        db    = load_data()
        tv    = db.get("assigned_teachers", {}).pop(t_key, None)
        save_data(db)
        if tv:
            try:
                await ctx.bot.send_message(tv["uid"],
                    "ℹ️ Ваша роль учителя была снята администратором.")
            except: pass
        await q.edit_message_text("✅ Роль учителя снята.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]))
        return

    if d == "admin_teachers":
        if not is_main_admin(uid): return
        db       = load_data()
        teachers = db.get("assigned_teachers", {})
        if not teachers:
            txt_t = "👨‍🏫 Назначенных учителей нет."
        else:
            lines = []
            for tk, tv in teachers.items():
                lines.append(f"• {tv['name']} ({tv['subject']}) — ID: `{tv['uid']}`")
            txt_t = "👨‍🏫 *Назначенные учителя:*\n\n" + "\n".join(lines)
        kb = InlineKeyboardMarkup([
            *[[InlineKeyboardButton(f"❌ Снять {tv['name']}", callback_data=f"tassign_remove_{tk}")]
              for tk, tv in teachers.items()],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")],
        ])
        await q.edit_message_text(txt_t, parse_mode="Markdown", reply_markup=kb)
        return

    # ── Скачать файлы учителя (для пользователей) ──────────────────────────
    if d.startswith("tfiles_"):
        t_key  = d[7:]
        db     = load_data()
        t_files = db.get("teacher_files", {}).get(t_key, [])
        if not t_files:
            await q.answer("Файлов нет", show_alert=True)
            return
        await q.answer()
        for f in t_files:
            try:
                await ctx.bot.send_document(
                    uid, document=f["file_id"],
                    caption=f"📎 {f['name']}")
            except: pass
        return

    # ── Добавить файл (учитель) ──────────────────────────────────────────
    if d.startswith("tse_addfile_"):
        t_key = d[12:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        ctx.user_data["teacher_file_key"] = t_key
        ctx.user_data["state"] = "teacher_file"
        await q.edit_message_text(
            "📎 Отправьте файл (PDF, Word, Excel и др.)\n\n"
            "_Максимальный размер: 20 МБ_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data=f"my_teacher_page_{t_key}")
            ]]))
        return

    # ── Управление файлами (список + удаление) ───────────────────────────
    if d.startswith("tse_files_"):
        t_key  = d[10:]
        db     = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        t_files = db.get("teacher_files", {}).get(t_key, [])
        if not t_files:
            await q.edit_message_text("📎 Файлов пока нет.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data=f"my_teacher_page_{t_key}")
                ]]))
            return
        kb_rows = []
        for i, f in enumerate(t_files):
            kb_rows.append([InlineKeyboardButton(
                f"🗑 {f['name']}", callback_data=f"tse_delfile_{t_key}_{i}")])
        kb_rows.append([InlineKeyboardButton("🔙 Назад", callback_data=f"my_teacher_page_{t_key}")])
        await q.edit_message_text(
            "📎 *Ваши файлы:*\n\nНажмите на файл чтобы удалить его.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if d.startswith("tse_delfile_"):
        rest  = d[12:]  # t_key_idx
        parts = rest.rsplit("_", 1)
        t_key, idx = "_".join(parts[:-1]), int(parts[-1])
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        files = db.setdefault("teacher_files", {}).get(t_key, [])
        if 0 <= idx < len(files):
            removed = files.pop(idx)
            db["teacher_files"][t_key] = files
            save_data(db)
            name = removed.get("name", "файл")
        else:
            name = "файл"
            save_data(db)
        remaining = db.get("teacher_files", {}).get(t_key, [])
        if remaining:
            kb_rows = []
            for i, f in enumerate(remaining):
                kb_rows.append([InlineKeyboardButton(
                    f"🗑 {f['name']}", callback_data=f"tse_delfile_{t_key}_{i}")])
            kb_rows.append([InlineKeyboardButton("🔙 Назад", callback_data=f"my_teacher_page_{t_key}")])
            await q.edit_message_text(
                f"✅ Файл «{name}» удалён.\n\n📎 *Оставшиеся файлы:*\nНажмите чтобы удалить.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(kb_rows))
        else:
            await q.edit_message_text(
                f"✅ Файл «{name}» удалён. Файлов больше нет.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data=f"my_teacher_page_{t_key}")
                ]]))
        return

    # ── Фото учителя (etph_/etphd_/tse_photo_/tse_dphoto_) ─────────────────
    if d.startswith("etph_"):
        if not is_main_admin(uid): return
        _, si_str, ti_str = d.split("_", 2)
        t_key = f"{si_str}_{ti_str}"
        ctx.user_data["edit_teacher_key"] = t_key
        ctx.user_data["state"] = "teacher_photo"
        await q.edit_message_text("📸 Отправьте фото учителя:")
        return

    if d.startswith("etphd_"):
        if not is_main_admin(uid): return
        _, si_str, ti_str = d.split("_", 2)
        t_key = f"{si_str}_{ti_str}"
        db = load_data()
        db.setdefault("teacher_photo", {}).pop(t_key, None)
        save_data(db)
        await q.edit_message_text("✅ Фото учителя удалено.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data=f"eti_{si_str}_{ti_str}")
            ]]))
        return

    if d.startswith("tse_photo_"):
        t_key = d[10:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        ctx.user_data["edit_teacher_key"] = t_key
        ctx.user_data["state"] = "teacher_photo"
        ctx.user_data["teacher_self_edit"] = True
        await q.edit_message_text("📸 Отправьте ваше фото:")
        return

    if d.startswith("tse_dphoto_"):
        t_key = d[11:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        db.setdefault("teacher_photo", {}).pop(t_key, None)
        save_data(db)
        await q.edit_message_text("✅ Фото удалено.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад", callback_data=f"my_teacher_page_{t_key}")
            ]]))
        return

    # ── Личная страница учителя (назначенного) ──────────────────────────
    if d.startswith("my_teacher_page_"):
        t_key    = d[16:]
        db       = load_data()
        tv       = db.get("assigned_teachers", {}).get(t_key, {})
        if not tv or tv.get("uid") != uid:
            await q.answer("Это не ваша страница")
            return
        si_str, ti_str = t_key.split("_", 1)
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[int(si_str)]][int(ti_str)]
        t_info   = db.get("teacher_info", {}).get(t_key, "➖")
        t_room   = db.get("teacher_room", {}).get(t_key, "➖")
        t_files  = db.get("teacher_files", {}).get(t_key, [])
        files_str = ""
        if t_files:
            fnames = "\n".join(f"• {f['name']}" for f in t_files)
            files_str = f"\n\n📎 *Файлы ({len(t_files)}):*\n{fnames}"
        txt_msg  = (
            f"👤 *{teacher['name']}*\n"
            f"📚 Предмет: {subjects[int(si_str)]}\n"
            f"🚪 Кабинет: {t_room}\n\n"
            f"📝 *Информация от учителя:*\n{t_info}"
            f"{files_str}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить информацию",  callback_data=f"tse_info_{t_key}")],
            [InlineKeyboardButton("🗑 Удалить информацию",   callback_data=f"tse_dinfo_{t_key}")],
            [InlineKeyboardButton("🚪 Изменить кабинет",     callback_data=f"tse_room_{t_key}")],
            [InlineKeyboardButton("❌ Удалить кабинет",      callback_data=f"tse_droom_{t_key}")],
            [InlineKeyboardButton("📸 Изменить фото",        callback_data=f"tse_photo_{t_key}")],
            [InlineKeyboardButton("🗑 Удалить фото",         callback_data=f"tse_dphoto_{t_key}")],
            [InlineKeyboardButton("📎 Добавить файл",        callback_data=f"tse_addfile_{t_key}")],
            [InlineKeyboardButton("🗑 Управление файлами",   callback_data=f"tse_files_{t_key}")],
            [InlineKeyboardButton("📢 Написать объявление",  callback_data=f"tse_announce_{t_key}")],
            [InlineKeyboardButton("🔙 К выбору учителей",    callback_data=f"si_{si_str}")],
        ])
        await safe_send(q, txt_msg, kb)
        return

    if d.startswith("tse_info_"):
        t_key = d[9:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        ctx.user_data["edit_teacher_key"] = t_key
        ctx.user_data["state"] = "edit_teacher_info"
        ctx.user_data["teacher_self_edit"] = True
        await safe_send(q, "✏️ Введите новую информацию для вашей страницы:",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"my_teacher_page_{t_key}")]]))
        return

    if d.startswith("tse_dinfo_"):
        t_key = d[10:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        db.setdefault("teacher_info", {}).pop(t_key, None)
        save_data(db)
        await safe_send(q, "✅ Информация удалена.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"my_teacher_page_{t_key}")]]))
        return

    if d.startswith("tse_room_"):
        t_key = d[9:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        ctx.user_data["edit_teacher_key"] = t_key
        ctx.user_data["state"] = "edit_teacher_room"
        ctx.user_data["teacher_self_edit"] = True
        await safe_send(q, "🚪 Введите номер вашего кабинета:",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"my_teacher_page_{t_key}")]]))
        return

    if d.startswith("tse_droom_"):
        t_key = d[10:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        db.setdefault("teacher_room", {}).pop(t_key, None)
        save_data(db)
        await safe_send(q, "✅ Кабинет удалён.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"my_teacher_page_{t_key}")]]))
        return

    # ── FAQ ─────────────────────────────────────────────────────────────────
    if d == "faq_menu":
        db = load_data()
        # Определяем роль пользователя
        is_teacher = any(tv.get("uid") == uid for tv in db.get("assigned_teachers", {}).values())
        # Формируем набор разделов FAQ
        sections = [("👤 Для всех пользователей", "faq_cat_user")]
        if is_teacher or is_main_admin(uid):
            sections.append(("👨‍🏫 Для учителей", "faq_cat_teacher"))
        if is_main_admin(uid):
            sections.append(("👑 Для главного админа", "faq_cat_main_admin"))
            sections.append(("🔧 Для всех админов",    "faq_cat_admin"))
        elif is_admin(uid):
            sections.append(("🔧 Для администраторов", "faq_cat_admin"))
        kb_rows = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in sections]
        kb_rows.append([InlineKeyboardButton("🔙 Назад", callback_data="sec_about")])
        await q.edit_message_text(
            "❓ *FAQ — часто задаваемые вопросы*\n\nВыберите раздел:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if d.startswith("faq_cat_"):
        cat = d[8:]  # user / teacher / admin / main_admin
        items = FAQ.get(cat, [])
        if not items:
            await q.edit_message_text("Раздел пуст.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="faq_menu")]]))
            return
        kb_rows = [[InlineKeyboardButton(f"❓ {item['q']}", callback_data=f"faq_q_{cat}_{i}")]
                   for i, item in enumerate(items)]
        kb_rows.append([InlineKeyboardButton("🔙 Назад", callback_data="faq_menu")])
        cat_names = {"user": "Для всех", "teacher": "Для учителей",
                     "admin": "Для администраторов", "main_admin": "Для главного админа"}
        await q.edit_message_text(
            f"❓ *FAQ — {cat_names.get(cat, cat)}*\n\nВыберите вопрос:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(kb_rows))
        return

    if d.startswith("faq_q_"):
        rest = d[6:]  # cat_idx
        parts = rest.rsplit("_", 1)
        cat, idx = "_".join(parts[:-1]), int(parts[-1])
        items = FAQ.get(cat, [])
        if 0 <= idx < len(items):
            item = items[idx]
            txt_faq = f"❓ *{item['q']}*\n\n{item['a']}"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 К вопросам", callback_data=f"faq_cat_{cat}")],
                [InlineKeyboardButton("🏠 В меню",     callback_data="main_menu")],
            ])
            await q.edit_message_text(txt_faq, parse_mode="Markdown", reply_markup=kb)
        return

    # ── Объявление от учителя ───────────────────────────────────────────────
    if d.startswith("tse_announce_"):
        t_key = d[13:]
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        ctx.user_data["teacher_announce_key"] = t_key
        ctx.user_data["state"] = "teacher_announce"
        await safe_send(q,
            "📢 Введите текст объявления.\n\nОно будет отправлено всем пользователям бота "
            "с пометкой «от учителя» без звука.",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"my_teacher_page_{t_key}")]]))
        return

    # ── Вопрос учителю (ask_teacher_) ───────────────────────────────────────
    if d.startswith("ask_teacher_"):
        t_key = d[12:]
        db    = load_data()
        tv    = db.get("assigned_teachers", {}).get(t_key, {})
        if not tv:
            await safe_send(q,
                "❌ Задать вопрос этому учителю невозможно.\n\n"
                "К этому учителю не привязан ни один пользователь.",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=f"si_{t_key.split(chr(95))[0]}")]]))
            return
        # Проверяем лимит 1 вопрос в день
        today = datetime.now().strftime("%d.%m.%Y")
        key   = f"asked_{uid}_{t_key}_{today}"
        if db.get("daily_limits", {}).get(key):
            await q.answer("Вы уже задавали вопрос этому учителю сегодня.", show_alert=True)
            return
        ctx.user_data["ask_teacher_key"] = t_key
        ctx.user_data["state"] = "ask_teacher"
        subjects = list(SUBJECT_TEACHERS.keys())
        si_str = t_key.split("_")[0]
        subj = subjects[int(si_str)] if int(si_str) < len(subjects) else "предмет"
        await safe_send(q,
            f"❓ Задайте вопрос учителю {tv.get('name', '')} ({subj}).\n\n"
            "Не более 1 вопроса в день. Ответ придёт вам в этот чат.",
            InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=f"ti_{t_key.replace('_', '_', 1)}")]]))
        return

    # ── Ответ учителя на вопрос ─────────────────────────────────────────────
    if d.startswith("tq_reply_"):
        q_id = d[9:]
        db   = load_data()
        q_item = next((x for x in db.get("teacher_questions", []) if x.get("id") == q_id), None)
        if not q_item: return
        t_key = q_item.get("t_key")
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        ctx.user_data["tq_reply_id"] = q_id
        ctx.user_data["state"] = "tq_reply"
        await q.edit_message_text(
            f"✏️ Ответ на вопрос:\n«{q_item.get('text', '')}»\n\nВведите ответ:")
        return

    if d.startswith("tq_mute_"):
        q_id = d[8:]
        db   = load_data()
        q_item = next((x for x in db.get("teacher_questions", []) if x.get("id") == q_id), None)
        if not q_item: return
        t_key = q_item.get("t_key")
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        asker_uid = q_item.get("uid")
        # Замутить: добавляем в muted_by_teacher на 24ч
        db.setdefault("teacher_muted", {}).setdefault(t_key, [])
        if asker_uid not in db["teacher_muted"][t_key]:
            db["teacher_muted"][t_key].append(asker_uid)
        save_data(db)
        try:
            await ctx.bot.send_message(asker_uid,
                "⛔️ Учитель отклонил ваш вопрос и ограничил возможность задавать вопросы.")
        except: pass
        await q.edit_message_text("✅ Пользователь ограничен в вопросах.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 На мою страницу", callback_data=f"my_teacher_page_{t_key}")
            ]]))
        return

    # ── Графики статистики ──────────────────────────────────────────────────
    if d == "stats_graph_hours":
        if not is_admin(uid): return
        db = load_data()
        hours_data = db.get("visits_by_hour", {})
        if not hours_data:
            await q.answer("Данных пока нет.", show_alert=True)
            return
        # Строим ASCII-график по часам (0-23)
        max_val = max(hours_data.values()) if hours_data else 1
        lines = ["📈 *Активность по часам (сегодня и всего)*\n"]
        for h in range(24):
            key = f"{h:02d}"
            val = hours_data.get(key, 0)
            bar_len = int((val / max_val) * 15) if max_val else 0
            bar = "█" * bar_len + "░" * (15 - bar_len)
            lines.append(f"`{key}:00` {bar} {val}")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="stats_back")]])
        await safe_send(q, "\n".join(lines), kb)
        return

    if d == "stats_graph_week":
        if not is_admin(uid): return
        db = load_data()
        days_data = db.get("visits_by_day", {})
        if not days_data:
            await q.answer("Данных пока нет.", show_alert=True)
            return
        # Последние 7 дней
        today = datetime.now().date()
        week_keys = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        max_val = max((days_data.get(k, 0) for k in week_keys), default=1) or 1
        lines = ["📊 *Активность за последние 7 дней*\n"]
        for k in week_keys:
            val = days_data.get(k, 0)
            bar_len = int((val / max_val) * 12) if max_val else 0
            bar = "█" * bar_len + "░" * (12 - bar_len)
            short = k[5:]  # MM-DD
            lines.append(f"`{short}` {bar} {val}")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="stats_back")]])
        await safe_send(q, "\n".join(lines), kb)
        return

    if d == "stats_back":
        if not is_admin(uid): return
        await q.edit_message_text("Используйте /stats для просмотра статистики.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Статистика", callback_data="noop")]]))
        return

    # ── Подписка на учителя ──────────────────────────────────────────────────
    if d.startswith("sub_teacher_"):
        t_key = d[12:]
        db    = load_data()
        subs  = db.setdefault("teacher_subs", {}).setdefault(t_key, [])
        # Получаем имя и предмет учителя
        tv       = db.get("assigned_teachers", {}).get(t_key, {})
        t_name   = tv.get("name", "учителя")
        subjects = list(SUBJECT_TEACHERS.keys())
        try: subj = subjects[int(t_key.split("_")[0])]
        except: subj = ""
        if uid in subs:
            subs.remove(uid)
            db["teacher_subs"][t_key] = subs
            save_data(db)
            # Обновляем кнопку на карточке
            try:
                kb_new = []
                for row in q.message.reply_markup.inline_keyboard:
                    new_row = []
                    for btn in row:
                        if btn.callback_data == d:
                            new_row.append(InlineKeyboardButton("🔔 Подписаться на учителя", callback_data=d))
                        else:
                            new_row.append(btn)
                    kb_new.append(new_row)
                await q.edit_message_reply_markup(InlineKeyboardMarkup(kb_new))
            except: pass
            await q.answer("🔕 Вы отписались от уведомлений.", show_alert=False)
            await q.message.chat.send_message(
                f"🔕 Вы *отписались* от уведомлений учителя {t_name}\n"
                f"Предмет: {subj}",
                parse_mode="Markdown")
        else:
            subs.append(uid)
            save_data(db)
            # Обновляем кнопку на карточке
            try:
                kb_new = []
                for row in q.message.reply_markup.inline_keyboard:
                    new_row = []
                    for btn in row:
                        if btn.callback_data == d:
                            new_row.append(InlineKeyboardButton("🔕 Отписаться", callback_data=d))
                        else:
                            new_row.append(btn)
                    kb_new.append(new_row)
                await q.edit_message_reply_markup(InlineKeyboardMarkup(kb_new))
            except: pass
            await q.answer("🔔 Подписка оформлена!", show_alert=False)
            await q.message.chat.send_message(
                f"🔔 Вы *подписались* на учителя *{t_name}*\n"
                f"Предмет: {subj}\n\n"
                f"Теперь вы будете получать объявления этого учителя.",
                parse_mode="Markdown")
        return

    # ── Викторина ────────────────────────────────────────────────────────────
    if d == "quiz_start":
        import random
        q_idx = random.randint(0, len(QUIZ_QUESTIONS) - 1)
        ctx.user_data["quiz_q"] = q_idx
        ctx.user_data["quiz_score"] = ctx.user_data.get("quiz_score", 0)
        ctx.user_data["quiz_total"] = ctx.user_data.get("quiz_total", 0)
        item = QUIZ_QUESTIONS[q_idx]
        kb_rows = [[InlineKeyboardButton(opt, callback_data=f"quiz_ans_{i}")]
                   for i, opt in enumerate(item["opts"])]
        kb_rows.append([InlineKeyboardButton("🏠 В меню", callback_data="main_menu")])
        sc = ctx.user_data.get("quiz_score", 0)
        tot = ctx.user_data.get("quiz_total", 0)
        await safe_send(q,
            f"🧠 *Викторина*\nПравильных: {sc}/{tot}\n\n❓ {item['q']}",
            InlineKeyboardMarkup(kb_rows))
        return

    if d.startswith("quiz_ans_"):
        ans_idx = int(d[9:])
        q_idx   = ctx.user_data.get("quiz_q")
        if q_idx is None: return
        item    = QUIZ_QUESTIONS[q_idx]
        correct = item["ans"]
        ctx.user_data["quiz_total"] = ctx.user_data.get("quiz_total", 0) + 1
        if ans_idx == correct:
            ctx.user_data["quiz_score"] = ctx.user_data.get("quiz_score", 0) + 1
            result = f"✅ Верно! Правильный ответ: *{item['opts'][correct]}*"
        else:
            result = f"❌ Неверно! Правильный ответ: *{item['opts'][correct]}*"
        sc  = ctx.user_data["quiz_score"]
        tot = ctx.user_data["quiz_total"]
        kb  = InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="quiz_start")],
            [InlineKeyboardButton("🔄 Сбросить счёт",    callback_data="quiz_reset")],
            [InlineKeyboardButton("🏠 В меню",           callback_data="main_menu")],
        ])
        await safe_send(q, f"🧠 *Викторина*\nПравильных: {sc}/{tot}\n\n{result}", kb)
        return

    if d == "quiz_reset":
        ctx.user_data["quiz_score"] = 0
        ctx.user_data["quiz_total"] = 0
        await q.answer("Счёт сброшен!", show_alert=True)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧠 Начать викторину", callback_data="quiz_start")]])
        await safe_send(q, "🧠 *Викторина*\nСчёт сброшен. Начнём заново?", kb)
        return

    # ── Служебные ───────────────────────────────────────────────────────
    if d == "admin_panel":
        await show_admin_panel(q, ctx, uid, edit=True)
        return

    if d == "admin_close":
        await delete_or_clear(q, send_menu=False)
        return

    if d == "edit_teacher_stub":
        if not is_main_admin(uid): return
        subjects = list(SUBJECT_TEACHERS.keys())
        indexed  = list(enumerate(subjects))
        rows     = list(chunks(indexed, 2))
        kb       = [[InlineKeyboardButton(s, callback_data=f"ets_{i}") for i, s in row] for row in rows]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
        await q.edit_message_text("✏️ Выберите предмет:", reply_markup=InlineKeyboardMarkup(kb))
        return

# ══════════════════════════════════════════
#  ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ
# ══════════════════════════════════════════
async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов — для загрузки файлов учителем"""
    uid   = update.effective_user.id
    state = ctx.user_data.get("state", "")

    if state == "teacher_file":
        db = load_data()
        # Проверяем что это учитель
        t_key = ctx.user_data.pop("teacher_file_key", None)
        ctx.user_data.pop("state", None)
        if not t_key:
            await update.message.reply_text("⚠️ Ошибка: ключ не найден.")
            return
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid:
            await update.message.reply_text("⚠️ У вас нет доступа.")
            return
        doc     = update.message.document
        file_id = doc.file_id
        fname   = doc.file_name or "Без названия"
        # Ограничение: максимум 10 файлов
        files = db.setdefault("teacher_files", {}).setdefault(t_key, [])
        if len(files) >= 10:
            await update.message.reply_text(
                "⚠️ Максимум 10 файлов. Удалите старые через «🗑 Управление файлами».",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 На мою страницу", callback_data=f"my_teacher_page_{t_key}")
                ]]))
            return
        files.append({"file_id": file_id, "name": fname})
        db["teacher_files"][t_key] = files
        save_data(db)
        await update.message.reply_text(
            f"✅ Файл *{fname}* добавлен! Всего файлов: {len(files)}/10",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📎 Добавить ещё",      callback_data=f"tse_addfile_{t_key}")],
                [InlineKeyboardButton("🔙 На мою страницу",   callback_data=f"my_teacher_page_{t_key}")],
            ]))
        return

async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обработчик фотографий — используется в состояниях где ожидается фото"""
    uid   = update.effective_user.id
    user  = update.effective_user
    state = ctx.user_data.get("state", "")
    photo = update.message.photo[-1]  # берём наибольшее разрешение
    file_id = photo.file_id


    if state == "getfileid_wait":
        if is_main_admin(uid):
            ctx.user_data.pop("state", None)
            await update.message.reply_text(
                f"📎 file_id:\n<code>{file_id}</code>",
                parse_mode="HTML")
            return

    if state == "event_photo":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        ctx.user_data["event_photo"] = file_id
        ctx.user_data.pop("state", None)
        now     = datetime.now().strftime("%d.%m.%Y %H:%M")
        caption = (f"🔔 *Новая новость!*\n📩 От: {ctx.user_data.get('event_sender')}\n"
                   f"📅 Опубликовано: {now}\n"
                   f"📆 Дата проведения события: {ctx.user_data.get('event_date', 'Не указана')}\n\n"
                   f"Информация о событии:\n{ctx.user_data.get('event_text', '')}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Отправить", callback_data="event_confirm"),
             InlineKeyboardButton("❌ Отменить",  callback_data="event_cancel")],
        ])
        await update.message.reply_photo(file_id, caption=f"Предпросмотр:\n\n{caption}",
                                          parse_mode="Markdown", reply_markup=kb)
        return

    if state == "broadcast_photo":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        ctx.user_data["broadcast_photo"] = file_id
        ctx.user_data.pop("state", None)
        bc_text = ctx.user_data.get("broadcast_text", "")
        now     = datetime.now().strftime("%d.%m.%Y %H:%M")
        caption = f"📢 *Новая рассылка!*\n\nИнформация от администрации:\n\n📅 {now}\n\n{bc_text}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Отправить сейчас", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("⏰ Запланировать",     callback_data="broadcast_schedule")],
            [InlineKeyboardButton("❌ Отменить",          callback_data="broadcast_cancel")],
        ])
        await update.message.reply_photo(file_id, caption=f"Предпросмотр с фото:\n\n{caption}",
                                          parse_mode="Markdown", reply_markup=kb)
        return

    if state == "teacher_photo":
        if not (is_main_admin(uid) or any(
            tv.get("uid") == uid for tv in load_data().get("assigned_teachers", {}).values()
        )): return
        t_key = ctx.user_data.pop("edit_teacher_key", None)
        ctx.user_data.pop("state", None)
        if not t_key: return
        db = load_data()
        db.setdefault("teacher_photo", {})[t_key] = file_id
        save_data(db)
        is_self = ctx.user_data.pop("teacher_self_edit", False)
        back_cb = f"my_teacher_page_{t_key}" if is_self else f"eti_{t_key.split('_')[0]}_{t_key.split('_')[1]}"
        await update.message.reply_text("✅ Фото учителя обновлено!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data=back_cb)],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
            ]))
        return

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    if is_banned(uid):
        await update.message.reply_text("❌ Вы заблокированы в этом боте.")
        return

    txt   = update.message.text
    state = ctx.user_data.get("state")

    # ── Кнопки главного меню ─────────────────────────────────────────────
    if txt == "Для родителей":
        register_user(uid, user.username or "")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Сайт",      url="https://196spb.edusite.ru/")],
            [InlineKeyboardButton("VK ВКонтакте", url="https://vk.com/gym196")],
            [InlineKeyboardButton("📞 Связь",     callback_data="contact_mode")],
            [InlineKeyboardButton("🔙 Назад",     callback_data="main_menu")],
        ])
        txt_p = ("Гимназия №196 в Санкт-Петербурге – это образовательное учреждение, "
                 "предлагающее широкий спектр учебных программ.\n"
                 "Адрес: Санкт-Петербург, пр. Ударников, 31.\n\nКонтакты:\n"
                 "Телефон: +7 (812) 417-22-02\nЭлектронная почта: school196@bk.ru")
        db = load_data()
        await send_section_photo(update.message.chat, uid, "contact", txt_p, kb, db)
        return

    if txt == "Для учителей":
        txt_t = ('Дорогой учитель, если вы хотите, чтобы ваше сообщение/ссылки были в разделе '
                 '"Выбор Предмета", свяжитесь с нами лично в гимназии и мы все обсудим и разместим.')
        kb_t = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]])
        db = load_data()
        await send_section_photo(update.message.chat, uid, "teachers", txt_t, kb_t, db)
        return

    if txt == "Для учеников":
        track_section("Для учеников")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Расписание уроков",   url="https://drive.google.com/file/d/1YjKO0N7Pbvq2IHAkSy5cpr2cwvisV0OT/view")],
            [InlineKeyboardButton("🔔 Расписание звонков",  callback_data="bell_schedule")],
            [InlineKeyboardButton("🎮 Игра",                callback_data="game_start")],
            [InlineKeyboardButton("📅 До каникул",          callback_data="holidays_countdown")],
            [InlineKeyboardButton("🧠 Викторина",            callback_data="quiz_start")],
            [InlineKeyboardButton("🏠 В меню",              callback_data="main_menu")],
        ])
        caption_s = ("Привет, гимназист! Здесь ты можешь:\n"
                     "• Посмотреть расписание уроков\n"
                     "• Посмотреть расписание звонков\n"
                     "• Поиграть в игру\n"
                     "• Узнать сколько дней до каникул")
        db = load_data()
        await send_section_photo(update.message.chat, uid, "students", caption_s, kb, db)
        return

    if txt == "О разработке/оценить":
        track_section("О разработке")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Предложить идею", callback_data="idea_mode")],
            [InlineKeyboardButton("⭐️ Оценить бота",   callback_data="review_start")],
            [InlineKeyboardButton("📊 Опросы",          callback_data="polls_list")],
            [InlineKeyboardButton("❓ FAQ",              callback_data="faq_menu")],
            [InlineKeyboardButton("🔙 Назад",           callback_data="main_menu")],
        ])
        txt_a = ("Данный бот создан командой 8 класса. "
                 "Вы можете предложить идею, оставить оценку или пройти опрос.")
        db = load_data()
        await send_section_photo(update.message.chat, uid, "about", txt_a, kb, db)
        return

    if txt == "Выбор Предмета":
        register_user(uid, user.username or "")
        track_section("Выбор предмета")
        db = load_data()
        # Если пользователь — учитель, показываем выбор страницы
        teacher_key = next(
            (tk for tk, tv in db.get("assigned_teachers", {}).items() if tv.get("uid") == uid),
            None)
        if teacher_key:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 На свою страницу",  callback_data=f"my_teacher_page_{teacher_key}")],
                [InlineKeyboardButton("📚 В выбор предмета", callback_data="subjects_back")],
                [InlineKeyboardButton("🔙 Назад",            callback_data="main_menu")],
            ])
            await update.message.reply_text("Выберите страницу:", reply_markup=kb)
            return
        subjects = list(SUBJECT_TEACHERS.keys())
        indexed  = list(enumerate(subjects))
        rows     = list(chunks(indexed, 2))
        kb       = [[InlineKeyboardButton(s, callback_data=f"si_{i}") for i, s in row] for row in rows]
        kb.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
        await update.message.reply_text("Выберите предмет:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if txt == "Новости":
        track_section("Новости")
        db        = load_data()
        news_list = db.get("news", [])
        if not news_list:
            await update.message.reply_text("📰 Новостей пока нет.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="main_menu")]]))
            return
        n     = news_list[0]
        total = len(news_list)
        pin_icon = "📌 " if n.get("pinned") else ""
        t     = (f"{pin_icon}🔔 *Новая новость!*\n📩 От: {n.get('sender')}\n"
                 f"📅 Опубликовано: {n.get('pub_date')}\n"
                 f"📆 Дата проведения события: {n.get('event_date', 'Не указана')}\n\n"
                 f"Информация о событии:\n{n.get('text')}")
        nav = []
        if total > 1: nav.append(InlineKeyboardButton("➡️ Вперёд", callback_data="news_1"))
        kb  = []
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("🏠 В меню", callback_data="main_menu")])
        if n.get("photo"):
            await update.message.reply_photo(n["photo"], caption=t, parse_mode="Markdown",
                                             reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.message.reply_text(t, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    # ── Состояния ─────────────────────────────────────────────────────────

    if state == "contact":
        # Проверка запрещённых слов
        banned_word = contains_banned(txt)
        if banned_word:
            await update.message.reply_text(
                "⛔️ Ваше сообщение содержит недопустимые слова и не было отправлено.\n"
                "Пожалуйста, перефразируйте сообщение в корректной форме.",
            )
            return  # state остаётся — пользователь может попробовать снова
        uname    = f"@{user.username}" if user.username else "без username"
        # Сохраняем тикет в БД с уникальным ID
        db       = load_data()
        role_prefix = get_user_role_prefix(uid)
        uname_display = role_prefix + uname
        # Ограничение: не более 3 открытых обращений
        open_count = sum(1 for t in db.get("tickets", []) if t.get("uid") == uid)
        if open_count >= 3:
            await update.message.reply_text(
                "⚠️ У вас уже есть 3 открытых обращения, ожидающих ответа. "
                "Пожалуйста, дождитесь ответа на предыдущие сообщения.")
            ctx.user_data.pop("state", None)
            return
        ticket_id = f"{uid}_{int(datetime.now().timestamp())}"
        ticket   = {
            "id":       ticket_id,
            "uid":      uid,
            "username": uname_display,
            "text":     txt,
            "date":     datetime.now().strftime("%d.%m.%Y %H:%M"),
        }
        db.setdefault("tickets", []).append(ticket)
        save_data(db)
        # Уведомляем всех админов (без кнопки ответить — ответ через /tickets)
        notify = (f"📩 *Новое обращение!*\n"
                  f"👤 {uname_display} (ID: `{uid}`)\n"
                  f"📅 {ticket['date']}\n\n"
                  f"{txt}\n\n"
                  f"_Ответьте через /tickets_")
        all_adm = list(set([MAIN_ADMIN_ID] + db.get("admins", [])))
        for aid in all_adm:
            try: await ctx.bot.send_message(aid, notify, parse_mode="Markdown")
            except: pass
        await update.message.reply_text("✅ Ваше сообщение отправлено администратору.")
        ctx.user_data.pop("state", None)
        return

    if state == "idea":
        uname = f"@{user.username}" if user.username else "без username"
        # Сохраняем идею для счётчика в профиле
        _idb = load_data()
        _idb.setdefault("ideas", []).append({"uid": uid, "date": datetime.now().strftime("%d.%m.%Y %H:%M")})
        save_data(_idb)
        msg   = f"💡 *Новая идея от пользователя*\nID: `{uid}`\nUsername: {uname}\n\n{txt}"
        try: await ctx.bot.send_message(MAIN_ADMIN_ID, msg, parse_mode="Markdown")
        except: pass
        await update.message.reply_text("✅ Ваша идея отправлена разработчикам!")
        ctx.user_data.pop("state", None)
        return

    if state == "review_liked":
        ctx.user_data["review_liked"] = txt
        ctx.user_data["state"] = "review_disliked"
        await update.message.reply_text(
            "❌ Что вам *не понравилось* или что хотелось бы улучшить?\n_(напишите текстом или `-`)_",
            parse_mode="Markdown")
        return

    if state == "review_disliked":
        stars     = ctx.user_data.pop("review_stars", 0)
        liked     = ctx.user_data.pop("review_liked", "-")
        disliked  = txt
        is_change = ctx.user_data.pop("review_is_change", False)
        ctx.user_data.pop("state", None)
        db = load_data()
        db.setdefault("reviews_done", [])
        db.setdefault("reviews", [])
        uname = f"@{user.username}" if user.username else "без username"
        now   = datetime.now().strftime("%d.%m.%Y %H:%M")
        new_entry = {"uid": uid, "username": uname, "stars": stars,
                     "liked": liked, "disliked": disliked, "date": now}
        if is_change:
            # Обновляем существующую запись
            db["reviews"] = [x for x in db["reviews"] if x.get("uid") != uid]
            db["reviews"].append(new_entry)
            msg = f"✅ Оценка обновлена! Новая оценка: {'⭐️' * stars}"
        else:
            if str(uid) in db["reviews_done"]:
                await update.message.reply_text("⭐️ Вы уже оставили оценку. Спасибо!", reply_markup=main_kb())
                return
            db["reviews"].append(new_entry)
            db["reviews_done"].append(str(uid))
            msg = f"✅ Спасибо за оценку!\nВы поставили: {'⭐️' * stars}"
        save_data(db)
        await update.message.reply_text(msg, reply_markup=main_kb())
        return

    # ── Ответ на тикет (через /tickets → кнопка «Ответить») ─────────────
    if state == "reply_ticket":
        ticket_id = ctx.user_data.pop("reply_ticket_id", None)
        ctx.user_data.pop("state", None)
        if not ticket_id:
            await update.message.reply_text("⚠️ Ошибка: обращение не найдено.")
            return
        db      = load_data()
        tickets = db.get("tickets", [])
        ticket  = next((t for t in tickets if t.get("id") == ticket_id), None)
        if not ticket:
            await update.message.reply_text("⚠️ Это обращение уже было отвечено другим администратором.")
            return
        # Переносим из tickets → answered
        tickets.remove(ticket)
        admin_name = f"@{user.username}" if user.username else str(uid)
        ticket["reply"]       = txt
        ticket["answered_by"] = admin_name
        ticket["answered_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        db["tickets"]  = tickets
        db.setdefault("answered", []).append(ticket)
        save_data(db)
        # Отправляем ответ пользователю
        reply_msg = (f"📨 *Ответ от администрации*\n\n"
                     f"Ваше обращение:\n_{ticket.get('text','')}_\n\n"
                     f"Ответ: {txt}")
        sent_ok = False
        try:
            await ctx.bot.send_message(
                ticket["uid"], reply_msg,
                parse_mode="Markdown",
                disable_notification=False)  # со звуком!
            sent_ok = True
        except:
            pass
        # Показываем статус и следующее неотвеченное обращение
        status = "✅ Ответ отправлен!" if sent_ok else "⚠️ Ответ сохранён, но пользователь заблокировал бота."
        remaining = db.get("tickets", [])
        if remaining:
            n = remaining[0]
            stars_str = ""
            kb_next = ticket_kb(0, len(remaining), "tickets", n.get("id", ""))
            header = status + "\n\n📩 *Следующее обращение (1 из " + str(len(remaining)) + "):*\n\n"
            body   = ticket_text(n, 0, len(remaining), "tickets")
            await update.message.reply_text(
                header + body, parse_mode="Markdown", reply_markup=kb_next)
        else:
            await update.message.reply_text(
                status + "\n\n✅ Обращений, требующих ответа, больше нет.",
                reply_markup=main_kb())
        return

    if state == "admin_add":
        if not is_main_admin(uid): ctx.user_data.pop("state", None); return
        if not txt.strip().isdigit():
            await update.message.reply_text("❌ Неверный ID. Отправьте числовой ID.")
            return
        target = int(txt.strip())
        if target == MAIN_ADMIN_ID:
            await update.message.reply_text("⚠️ Это вы — главный админ!")
            return
        db = load_data()
        if target in db.get("admins", []):
            await update.message.reply_text("⚠️ Этот пользователь уже админ.")
            return
        db.setdefault("admins", []).append(target)
        save_data(db)
        await update.message.reply_text(f"✅ Пользователь `{target}` назначен админом.", parse_mode="Markdown")
        ctx.user_data.pop("state", None)
        return

    if state == "admin_ban":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        if not txt.strip().isdigit():
            await update.message.reply_text("❌ Неверный ID. Отправьте числовой ID.")
            return
        ctx.user_data["ban_target"] = int(txt.strip())
        ctx.user_data["state"] = "admin_ban_reason"
        await update.message.reply_text(
            f"🔎 ID: `{txt.strip()}`\n\nТеперь укажите *причину блокировки*:",
            parse_mode="Markdown")
        return

    if state == "admin_ban_reason":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        ctx.user_data["ban_reason"] = txt.strip()
        ctx.user_data["state"] = "admin_ban_days"
        await update.message.reply_text(
            "⏳ Укажите *срок бана*:\n\n"
            "• Введите число дней (например: `7`)\n"
            "• Введите `0` или `-` для *бессрочного* бана",
            parse_mode="Markdown")
        return

    if state == "admin_ban_days":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        target = ctx.user_data.pop("ban_target", None)
        reason = ctx.user_data.pop("ban_reason", "—")
        ctx.user_data.pop("state", None)
        if not target:
            await update.message.reply_text("⚠️ Ошибка: ID не найден.")
            return
        days_input = txt.strip()
        ban_until  = None
        until_str  = "бессрочно"
        if days_input.isdigit() and int(days_input) > 0:
            days = int(days_input)
            ban_until  = (datetime.now() + timedelta(days=days)).isoformat()
            until_dt   = datetime.fromisoformat(ban_until)
            until_str  = until_dt.strftime("%d.%m.%Y %H:%M")
        db = load_data()
        if target not in db.get("banned", []):
            db.setdefault("banned", []).append(target)
        db.setdefault("ban_reasons", {})[str(target)] = reason
        if ban_until:
            db.setdefault("ban_until", {})[str(target)] = ban_until
        else:
            db.get("ban_until", {}).pop(str(target), None)
        admin_name = f"@{user.username}" if user.username else str(uid)
        db.setdefault("ban_history", []).append({
            "target": target, "by": admin_name,
            "reason": reason, "until": until_str,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        })
        save_data(db)
        try:
            user_msg = (
                f"🚫 *Вы заблокированы администрацией.*\n\n"
                f"Причина: {reason}\n"
                f"Срок: *{until_str}*"
            )
            await ctx.bot.send_message(target, user_msg, parse_mode="Markdown")
        except: pass
        await update.message.reply_text(
            f"✅ Пользователь `{target}` заблокирован.\n"
            f"Причина: {reason}\nСрок: *{until_str}*",
            parse_mode="Markdown")
        return

    if state == "broadcast_text":
        ctx.user_data["broadcast_text"] = txt
        ctx.user_data["state"] = "broadcast_photo"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить (без фото)", callback_data="bc_skip_photo")],
            [InlineKeyboardButton("❌ Отменить",              callback_data="broadcast_cancel")],
        ])
        await update.message.reply_text(
            "📸 Прикрепите фото к рассылке или нажмите «Пропустить»:",
            reply_markup=kb)
        return

    if state == "broadcast_schedule_dt":
        raw = txt.strip()
        try:
            send_dt = datetime.strptime(raw, "%d.%m.%Y %H:%M")
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Используйте: `ДД.ММ.ГГГГ ЧЧ:ММ`\n_Например: 25.02.2026 18:00_",
                parse_mode="Markdown")
            return
        if send_dt <= datetime.now():
            await update.message.reply_text(
                "❌ Дата и время должны быть в будущем. Попробуйте ещё раз:")
            return
        bc_text = ctx.user_data.pop("broadcast_text", "")
        ctx.user_data.pop("state", None)
        delay = (send_dt - datetime.now()).total_seconds()
        await update.message.reply_text(
            f"✅ Рассылка запланирована на *{send_dt.strftime('%d.%m.%Y %H:%M')}*\n"
            f"Через {int(delay//3600)}ч {int((delay%3600)//60)}мин",
            parse_mode="Markdown")

        async def delayed_send():
            await asyncio.sleep(delay)
            db  = load_data()
            now = datetime.now().strftime("%d.%m.%Y %H:%M")
            msg = f"📢 *Новая рассылка!*\n\nИнформация от администрации:\n\n📅 {now}\n\n{bc_text}"
            ok, fail = 0, 0
            for u in db.get("users", []):
                try:
                    await ctx.bot.send_message(u, msg, parse_mode="Markdown"); ok += 1
                except: fail += 1
            try:
                await ctx.bot.send_message(
                    uid, f"✅ Запланированная рассылка отправлена!\nУспешно: {ok}, неудачно: {fail}")
            except: pass

        asyncio.create_task(delayed_send())
        return

    if state == "event_date":
        if txt.strip() == "-":
            ctx.user_data["event_date"] = "Не указана"
            ctx.user_data["state"]      = "event_text"
            await update.message.reply_text("Введите описание события:")
        else:
            try:
                datetime.strptime(txt.strip(), "%d.%m.%Y %H:%M")
                ctx.user_data["event_date"] = txt.strip()
                ctx.user_data["state"]      = "event_text"
                await update.message.reply_text("Введите описание события:")
            except ValueError:
                await update.message.reply_text(
                    "❌ Некорректный формат даты.\n\n"
                    "Используйте: ДД.ММ.ГГГГ ЧЧ:ММ (например: 15.02.2026 18:00)\n"
                    "Или напишите `-`, если дата неизвестна.")
        return

    if state == "event_text":
        ctx.user_data["event_text"] = txt
        ctx.user_data["state"] = "event_photo"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить (без фото)", callback_data="event_skip_photo")],
            [InlineKeyboardButton("❌ Отменить",              callback_data="event_cancel")],
        ])
        await update.message.reply_text(
            "📸 Прикрепите фото к новости или нажмите «Пропустить»:",
            reply_markup=kb)
        return

    if state == "edit_teacher_info":
        if not is_main_admin(uid): ctx.user_data.pop("state", None); return
        t_key = ctx.user_data.pop("edit_teacher_key", None)
        ctx.user_data.pop("state", None)
        if not t_key:
            await update.message.reply_text("⚠️ Ошибка: ключ учителя не найден.")
            return
        db = load_data()
        db.setdefault("teacher_info", {})[t_key] = txt
        save_data(db)
        si_str, ti_str = t_key.split("_", 1)
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[int(si_str)]][int(ti_str)]
        is_self = ctx.user_data.pop("teacher_self_edit", False)
        if is_self:
            kb_back = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Моя страница", callback_data=f"my_teacher_page_{t_key}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
            ])
        else:
            kb_back = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к учителю", callback_data=f"eti_{si_str}_{ti_str}")],
                [InlineKeyboardButton("🏠 Главное меню",    callback_data="main_menu")],
            ])
        await update.message.reply_text(
            f"✅ Информация для *{teacher['name']}* обновлена!\n\n📝 {txt}",
            parse_mode="Markdown", reply_markup=kb_back)
        return

    if state == "edit_teacher_room":
        if not is_main_admin(uid): ctx.user_data.pop("state", None); return
        t_key = ctx.user_data.pop("edit_teacher_key", None)
        ctx.user_data.pop("state", None)
        if not t_key:
            await update.message.reply_text("⚠️ Ошибка: ключ учителя не найден.")
            return
        db = load_data()
        db.setdefault("teacher_room", {})[t_key] = txt
        save_data(db)
        si_str, ti_str = t_key.split("_", 1)
        subjects = list(SUBJECT_TEACHERS.keys())
        teacher  = SUBJECT_TEACHERS[subjects[int(si_str)]][int(ti_str)]
        is_self = ctx.user_data.pop("teacher_self_edit", False)
        if is_self:
            kb_back = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Моя страница", callback_data=f"my_teacher_page_{t_key}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
            ])
        else:
            kb_back = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад к учителю", callback_data=f"eti_{si_str}_{ti_str}")],
                [InlineKeyboardButton("🏠 Главное меню",    callback_data="main_menu")],
            ])
        await update.message.reply_text(
            f"✅ Кабинет для *{teacher['name']}* обновлён!\n\n🚪 {txt}",
            parse_mode="Markdown", reply_markup=kb_back)
        return

    if state == "dm_target":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        raw = txt.strip()
        # Определяем — ID или юзернейм
        if raw.isdigit():
            ctx.user_data["dm_target_id"] = int(raw)
            ctx.user_data["dm_target_str"] = raw
        elif raw.startswith("@"):
            ctx.user_data["dm_target_id"] = None
            ctx.user_data["dm_target_str"] = raw  # попробуем при отправке
        else:
            await update.message.reply_text("❌ Введите числовой ID или @юзернейм.")
            return
        ctx.user_data["state"] = "dm_text"
        await update.message.reply_text(
            f"✉️ Получатель: `{raw}`\n\nТеперь введите текст сообщения:",
            parse_mode="Markdown")
        return

    if state == "dm_text":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        target_id  = ctx.user_data.pop("dm_target_id", None)
        target_str = ctx.user_data.pop("dm_target_str", "?")
        ctx.user_data.pop("state", None)
        dm_msg = f"✉️ *Сообщение от администрации:*\n\n{txt}"
        sent = False
        if target_id:
            try:
                await ctx.bot.send_message(target_id, dm_msg, parse_mode="Markdown")
                sent = True
            except: pass
        if not sent:
            await update.message.reply_text(
                f"❌ Не удалось отправить сообщение пользователю `{target_str}`.\n"
                f"Убедитесь что ID верный и пользователь не заблокировал бота.",
                parse_mode="Markdown")
        else:
            await update.message.reply_text(
                f"✅ Сообщение отправлено пользователю `{target_str}`.", parse_mode="Markdown")
        return

    if state == "pinned_set":
        if not is_main_admin(uid): ctx.user_data.pop("state", None); return
        ctx.user_data.pop("state", None)
        db = load_data()
        db["pinned_announcement"] = txt
        save_data(db)
        await update.message.reply_text(
            f"✅ Закреплённое объявление установлено!\n\n📌 {txt}",
            parse_mode="Markdown", reply_markup=main_kb())
        return

    if state == "find_user":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        ctx.user_data.pop("state", None)
        raw = txt.strip()
        db  = load_data()
        # Ищем по ID или юзернейму
        found_uid  = None
        found_info = {}
        if raw.isdigit():
            found_uid = int(raw)
        elif raw.startswith("@"):
            uname_search = raw[1:].lower()
            for fuid, info in db.get("users_info", {}).items():
                if info.get("username", "").lower() == uname_search:
                    found_uid  = int(fuid)
                    found_info = info
                    break
        else:
            uname_search = raw.lower()
            for fuid, info in db.get("users_info", {}).items():
                if info.get("username", "").lower() == uname_search:
                    found_uid  = int(fuid)
                    found_info = info
                    break
        if not found_uid:
            await update.message.reply_text("❌ Пользователь не найден. Проверьте ID или юзернейм.")
            return
        if not found_info:
            found_info = db.get("users_info", {}).get(str(found_uid), {})
        # Собираем карточку
        uname_str  = found_info.get("username", "—")
        reg_dt     = found_info.get("registered", "—")
        banned     = found_uid in db.get("banned", [])
        ban_reason = db.get("ban_reasons", {}).get(str(found_uid), "—")
        open_t     = sum(1 for t in db.get("tickets", [])  if t.get("uid") == found_uid)
        clos_t     = sum(1 for t in db.get("answered", []) if t.get("uid") == found_uid)
        stars      = next((r.get("stars") for r in db.get("reviews", []) if r.get("uid") == found_uid), None)
        stars_str  = ("⭐️" * stars) if stars else "не оставлял"
        role_str   = get_user_role_prefix(found_uid).strip("[] ")
        status_str = f"🚫 Заблокирован (причина: {ban_reason})" if banned else "✅ Активен"
        card = (
            f"🔍 *Карточка пользователя*\n\n"
            f"🆔 ID: `{found_uid}`\n"
            f"👤 Юзернейм: @{uname_str}\n"
            f"📅 Регистрация: {reg_dt}\n"
            f"🏷 Роль: {role_str}\n"
            f"🔘 Статус: {status_str}\n\n"
            f"📩 Обращений открытых: {open_t}\n"
            f"📩 Обращений закрытых: {clos_t}\n"
            f"⭐️ Оценка бота: {stars_str}"
        )
        await update.message.reply_text(card, parse_mode="Markdown")
        return

    if state == "teacher_target":
        if not is_main_admin(uid): ctx.user_data.pop("state", None); return
        raw = txt.strip()
        db  = load_data()
        found_uid = None
        if raw.isdigit():
            found_uid = int(raw)
        elif raw.startswith("@"):
            uname_s = raw[1:].lower()
            for fuid, info in db.get("users_info", {}).items():
                if info.get("username", "").lower() == uname_s:
                    found_uid = int(fuid); break
        if not found_uid:
            await update.message.reply_text("❌ Пользователь не найден. Введите правильный ID или @юзернейм.")
            return
        ctx.user_data["teacher_uid"] = found_uid
        ctx.user_data["state"] = "teacher_surname"
        # Предлагаем выбрать предмет
        subjects = list(SUBJECT_TEACHERS.keys())
        indexed  = list(enumerate(subjects))
        rows     = list(chunks(indexed, 2))
        kb = [[InlineKeyboardButton(s, callback_data=f"tassign_si_{i}") for i, s in row] for row in rows]
        await update.message.reply_text(
            f"✅ Пользователь найден: `{found_uid}`\n\nВыберите *предмет* учителя:",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        ctx.user_data.pop("state", None)
        return

    if state == "edit_news_text":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        idx = ctx.user_data.pop("edit_news_idx", None)
        ctx.user_data.pop("state", None)
        if idx is None:
            await update.message.reply_text("⚠️ Ошибка: новость не найдена.")
            return
        db        = load_data()
        news_list = db.get("news", [])
        if 0 <= idx < len(news_list):
            news_list[idx]["text"] = txt
            db["news"] = news_list
            save_data(db)
            await update.message.reply_text(
                f"✅ Текст новости #{idx+1} обновлён!\n\n{txt}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📰 К новости",          callback_data=f"admin_news_view_{idx}")],
                    [InlineKeyboardButton("📰 Управление новостями", callback_data="admin_news")],
                ]))
        else:
            await update.message.reply_text("⚠️ Новость не найдена.")
        return

    if state == "teacher_announce":
        t_key = ctx.user_data.pop("teacher_announce_key", None)
        ctx.user_data.pop("state", None)
        if not t_key: return
        db = load_data()
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        tv       = db["assigned_teachers"][t_key]
        subjects = list(SUBJECT_TEACHERS.keys())
        si_str   = t_key.split("_")[0]
        subj     = subjects[int(si_str)] if int(si_str) < len(subjects) else ""
        header   = f"📢 Объявление от учителя\n👨\u200d🏫 {tv.get('name', '')} | {subj}\n\n{txt}"
        ok, fail = 0, 0
        for u in db.get("users", []):
            try:
                await ctx.bot.send_message(u, header, disable_notification=True)
                ok += 1
            except: fail += 1
        await update.message.reply_text(
            f"✅ Объявление отправлено!\nДоставлено: {ok} | Ошибок: {fail}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 На мою страницу", callback_data=f"my_teacher_page_{t_key}")
            ]]))
        return

    if state == "ask_teacher":
        t_key = ctx.user_data.pop("ask_teacher_key", None)
        ctx.user_data.pop("state", None)
        if not t_key: return
        db = load_data()
        tv = db.get("assigned_teachers", {}).get(t_key, {})
        if not tv:
            await update.message.reply_text("⚠️ Учитель не найден.")
            return
        if uid in db.get("teacher_muted", {}).get(t_key, []):
            await update.message.reply_text("⛔️ Вы не можете задавать вопросы этому учителю.")
            return
        banned_word = contains_banned(txt)
        if banned_word:
            await update.message.reply_text(
                "⛔️ Вопрос содержит недопустимые слова и не был отправлен.\nПерефразируйте вопрос.")
            return
        today = datetime.now().strftime("%d.%m.%Y")
        limit_key = f"asked_{uid}_{t_key}_{today}"
        db.setdefault("daily_limits", {})[limit_key] = True
        q_id  = f"{uid}_{t_key}_{int(datetime.now().timestamp())}"
        uname = f"@{user.username}" if user.username else f"ID {uid}"
        question = {"id": q_id, "uid": uid, "uname": uname, "t_key": t_key, "text": txt,
                    "date": datetime.now().strftime("%d.%m.%Y %H:%M")}
        db.setdefault("teacher_questions", []).append(question)
        save_data(db)
        teacher_uid = tv.get("uid")
        subjects = list(SUBJECT_TEACHERS.keys())
        si_str = t_key.split("_")[0]
        subj = subjects[int(si_str)] if int(si_str) < len(subjects) else ""
        notify = f"❓ Новый вопрос\n👤 {uname} | {question['date']}\n\n{txt}"
        kb_t = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Ответить", callback_data=f"tq_reply_{q_id}")],
            [InlineKeyboardButton("🔇 Замутить", callback_data=f"tq_mute_{q_id}")],
        ])
        try:
            await ctx.bot.send_message(teacher_uid, notify, reply_markup=kb_t)
        except: pass
        await update.message.reply_text("✅ Ваш вопрос отправлен учителю. Ответ придёт в этот чат.")
        return

    if state == "tq_reply":
        q_id = ctx.user_data.pop("tq_reply_id", None)
        ctx.user_data.pop("state", None)
        if not q_id: return
        db = load_data()
        q_item = next((x for x in db.get("teacher_questions", []) if x.get("id") == q_id), None)
        if not q_item: return
        t_key = q_item.get("t_key")
        if db.get("assigned_teachers", {}).get(t_key, {}).get("uid") != uid: return
        tv = db["assigned_teachers"][t_key]
        subjects = list(SUBJECT_TEACHERS.keys())
        si_str = t_key.split("_")[0]
        subj = subjects[int(si_str)] if int(si_str) < len(subjects) else ""
        asker_uid = q_item.get("uid")
        reply_msg = (f"💬 Ответ от учителя {tv.get('name', '')} ({subj})\n\n"
                     f"Ваш вопрос: {q_item.get('text', '')}\n\nОтвет: {txt}")
        try:
            await ctx.bot.send_message(asker_uid, reply_msg)
        except: pass
        await update.message.reply_text("✅ Ответ отправлен!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 На мою страницу", callback_data=f"my_teacher_page_{t_key}")
            ]]))
        return

    if state == "poll_question":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        ctx.user_data["poll_question"] = txt
        ctx.user_data["state"]         = "poll_option"
        ctx.user_data.setdefault("poll_options", [])
        await update.message.reply_text(
            f"✅ Вопрос сохранён: *{txt}*\n\nТеперь введите *вариант ответа #1*:",
            parse_mode="Markdown")
        return

    if state == "poll_option":
        if not is_admin(uid): ctx.user_data.pop("state", None); return
        ctx.user_data.setdefault("poll_options", []).append(txt)
        opts     = ctx.user_data["poll_options"]
        q_text   = ctx.user_data.get("poll_question", "")
        opts_txt = "\n".join(f"{i+1}. {o}" for i, o in enumerate(opts))
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить ещё вариант",    callback_data="poll_add_option")],
            [InlineKeyboardButton("✅ Завершить создание опроса", callback_data="poll_finish_create")],
            [InlineKeyboardButton("❌ Отменить",                 callback_data="admin_polls")],
        ])
        await update.message.reply_text(
            f"📊 *{q_text}*\n\nВарианты ({len(opts)}):\n{opts_txt}\n\n"
            f"Добавьте ещё или завершите:",
            parse_mode="Markdown", reply_markup=kb)
        ctx.user_data.pop("state", None)
        return

async def cmd_polls(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    db    = load_data()
    polls = db.get("polls", [])
    if not polls:
        txt_p = "📊 Опросов пока нет."
    else:
        txt_p = "📊 *Активные опросы:*\n\n" + "\n".join(
            f"{i+1}. {p['question']} ({sum(p.get('votes',{}).values())} гол.)"
            for i, p in enumerate(polls))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать опрос", callback_data="poll_create")],
        *[[InlineKeyboardButton(f"🗑 Удалить #{i+1}", callback_data=f"poll_del_{i}")]
          for i in range(len(polls))],
        [InlineKeyboardButton("🔙 Закрыть", callback_data="admin_close")],
    ])
    await update.message.reply_text(txt_p, parse_mode="Markdown", reply_markup=kb)

async def cmd_dm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    ctx.user_data["state"] = "dm_target"
    await update.message.reply_text(
        "✉️ *Личное сообщение пользователю*\n\n"
        "Введите ID или @юзернейм пользователя:",
        parse_mode="Markdown")

async def cmd_broadcasts_archive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    db   = load_data()
    arch = db.get("broadcasts", [])
    if not arch:
        await update.message.reply_text("📭 Архив рассылок пуст.")
        return
    # Показываем последнюю (страница 0 от конца)
    await show_broadcast_archive(update.message, len(arch)-1, send=True)

async def show_broadcast_archive(target, page: int, edit=False, send=False):
    db   = load_data()
    arch = db.get("broadcasts", [])
    if not arch:
        return
    page  = max(0, min(page, len(arch)-1))
    b     = arch[page]
    total = len(arch)
    txt   = (
        f"📢 *Архив рассылок — {page+1} из {total}*\n\n"
        f"📅 Дата: {b.get('date','—')}\n"
        f"👤 Отправил: {b.get('sent_by','—')}\n"
        f"✅ Доставлено: {b.get('ok',0)} | ❌ Неудачно: {b.get('fail',0)}\n\n"
        f"Текст:\n{b.get('text','')}"
    )
    nav = []
    if page > 0:       nav.append(InlineKeyboardButton("⬅️", callback_data=f"barch_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if page < total-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"barch_{page+1}"))
    kb = InlineKeyboardMarkup([
        nav,
        [InlineKeyboardButton("🔁 Повторить рассылку", callback_data=f"barch_repeat_{page}")],
        [InlineKeyboardButton("❌ Закрыть",             callback_data="pager_close")],
    ])
    if send:   await target.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    elif edit: await target.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

async def show_ban_history(target, page: int, edit=False, send=False):
    db      = load_data()
    history = db.get("ban_history", [])
    if not history:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Закрыть", callback_data="pager_close")]])
        txt = "📋 История банов пуста."
        if send:   await target.reply_text(txt, reply_markup=kb)
        elif edit: await target.edit_message_text(txt, reply_markup=kb)
        return
    page  = max(0, min(page, len(history)-1))
    total = len(history)
    h     = history[page]
    txt   = (
        f"📋 *История банов — {page+1} из {total}*\n\n"
        f"👤 Заблокирован: `{h.get('target','?')}`\n"
        f"🛡 Кем: {h.get('by','—')}\n"
        f"📅 Когда: {h.get('date','—')}\n"
        f"📝 Причина: {h.get('reason','—')}"
    )
    nav = []
    if page > 0:       nav.append(InlineKeyboardButton("⬅️", callback_data=f"banh_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
    if page < total-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"banh_{page+1}"))
    kb = InlineKeyboardMarkup([nav, [InlineKeyboardButton("❌ Закрыть", callback_data="pager_close")]])
    if send:   await target.reply_text(txt, parse_mode="Markdown", reply_markup=kb)
    elif edit: await target.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

async def cmd_find(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    ctx.user_data["state"] = "find_user"
    await update.message.reply_text(
        "🔍 *Поиск пользователя*\n\nВведите ID или @юзернейм:",
        parse_mode="Markdown")

async def cmd_teacher(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_main_admin(uid):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return
    ctx.user_data["state"] = "teacher_target"
    await update.message.reply_text(
        "👨‍🏫 *Назначение учителя*\n\nВведите ID или @юзернейм пользователя:",
        parse_mode="Markdown")

async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    user = update.effective_user
    register_user(uid, user.username or "")
    db   = load_data()

    info      = db.get("users_info", {}).get(str(uid), {})
    reg_date  = info.get("registered", "—")
    uname     = info.get("username", "—")
    role_str  = get_user_role_prefix(uid).strip("[] ")

    # Победы в игре (из текущей сессии — храним в БД)
    game_wins = db.get("game_wins", {}).get(str(uid), 0)

    # Обращения
    open_t = sum(1 for t in db.get("tickets",  []) if t.get("uid") == uid)
    clos_t = sum(1 for t in db.get("answered", []) if t.get("uid") == uid)

    # Оценка бота
    review = next((r for r in db.get("reviews", []) if r.get("uid") == uid), None)
    stars_str = ("⭐️" * review["stars"]) if review else "не оставлял"

    # Идеи (считаем по записям в ideas)
    ideas_cnt = sum(1 for i in db.get("ideas", []) if i.get("uid") == uid)

    # Заблокирован?
    banned_str = "🚫 Заблокирован" if uid in db.get("banned", []) else "✅ Активен"

    txt = (
        f"👤 *Ваш профиль*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"📛 Юзернейм: @{uname}\n"
        f"🏷 Роль: {role_str}\n"
        f"📅 Дата регистрации: {reg_date}\n"
        f"🔘 Статус: {banned_str}\n\n"
        f"🎮 Побед в игре: {game_wins}\n"
        f"📩 Обращений открытых: {open_t}\n"
        f"📩 Обращений закрытых: {clos_t}\n"
        f"💡 Идей предложено: {ideas_cnt}\n"
        f"⭐️ Оценка бота: {stars_str}"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Закрыть", callback_data="pager_close")]])
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

# ══════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    is_teacher = any(
        tv.get("uid") == uid
        for tv in load_data().get("assigned_teachers", {}).values()
    )

    # Базовые команды для всех
    txt = (
        "📖 *Справка по командам*\n\n"
        "👤 *Для всех пользователей:*\n"
        "/start — главное меню\n"
        "/profile — ваш профиль\n"
        "/contact — написать администрации\n"
        "/idea — предложить идею\n"
        "/help — эта справка\n"
    )

    if is_teacher:
        txt += (
            "\n👨‍🏫 *Для учителей:*\n"
            "/teacher — моя страница учителя\n"
            "Используйте кнопки на своей странице для:\n"
            "• Публикации объявлений\n"
            "• Загрузки файлов\n"
            "• Ответов на вопросы учеников\n"
        )

    if is_admin(uid):
        txt += (
            "\n🔧 *Для администраторов:*\n"
            "/admin — панель управления\n"
            "/tickets — открытые обращения\n"
            "/answered — закрытые обращения\n"
            "/broadcast — рассылка\n"
            "/banlist — список заблокированных\n"
            "/stats — статистика\n"
            "/export — экспорт данных\n"
            "/find — найти пользователя\n"
            "/dm — личное сообщение пользователю\n"
            "/backup — резервная копия БД\n"
            "/botstatus — статус бота\n"
        )

    if is_main_admin(uid):
        txt += (
            "\n👑 *Только для главного админа:*\n"
            "/setphoto — загрузить фото раздела\n"
            "/checkphotos — статус фото разделов\n"
            "/polls — управление опросами\n"
        )

    await update.message.reply_text(txt, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 В меню", callback_data="main_menu")
        ]]))

async def cmd_botstatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("У вас нет доступа.")
        return
    import os, time as _time
    db      = load_data()
    users   = db.get("users", [])
    banned  = db.get("banned", [])
    tickets = db.get("tickets", [])
    db_size = os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    db_size_str = f"{db_size/1024:.1f} КБ" if db_size < 1024*1024 else f"{db_size/1024/1024:.2f} МБ"
    start_t = ctx.application.bot_data.get("start_time", _time.time())
    uptime_sec = int(_time.time() - start_t)
    h, rem = divmod(uptime_sec, 3600)
    m, s   = divmod(rem, 60)
    total_subs = sum(len(v) for v in db.get("teacher_subs", {}).values())
    await update.message.reply_text(
        f"🤖 *Статус бота*\n\n"
        f"⏱ Аптайм: `{h}ч {m}м {s}с`\n"
        f"👥 Пользователей: `{len(users)}`\n"
        f"🚫 Заблокировано: `{len(banned)}`\n"
        f"📩 Открытых тикетов: `{len(tickets)}`\n"
        f"🔔 Подписок на учителей: `{total_subs}`\n"
        f"💾 Размер БД: `{db_size_str}`\n"
        f"📅 Дата/время: `{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`",
        parse_mode="Markdown")

async def cleanup_old_tickets():
    """Автоочистка тикетов старше 7 дней"""
    db       = load_data()
    tickets  = db.get("tickets", [])
    answered = db.get("answered", [])
    cutoff   = datetime.now() - timedelta(days=7)
    def is_old(t):
        try:
            return datetime.strptime(t.get("date", ""), "%d.%m.%Y %H:%M") < cutoff
        except: return False
    old_open     = [t for t in tickets  if is_old(t)]
    old_answered = [t for t in answered if is_old(t)]
    if old_open or old_answered:
        db["tickets"]  = [t for t in tickets  if not is_old(t)]
        db["answered"] = [t for t in answered if not is_old(t)]
        save_data(db)
        logger.info(f"Автоочистка: удалено {len(old_open)} открытых и {len(old_answered)} закрытых тикетов.")

async def cmd_getfileid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Временная команда для получения file_id фото. Только для главного админа."""
    uid = update.effective_user.id
    if not is_main_admin(uid):
        return
    if update.message.photo:
        fid = update.message.photo[-1].file_id
        await update.message.reply_text(
            f"📎 file_id:\n<code>{fid}</code>",
            parse_mode="HTML")
    else:
        await update.message.reply_text(
            "📸 Отправьте фото с подписью /getfileid\n\n"
            "Или: сначала /getfileid, затем отправьте фото следующим сообщением.\n\n"
            "<b>Разделы:</b>\n"
            "• students — Для учеников\n"
            "• teachers — Для учителей\n"  
            "• about — О разработке\n"
            "• contact — Связь\n"
            "• schedule — Расписание звонков",
            parse_mode="HTML")
        ctx.user_data["state"] = "getfileid_wait"

async def cmd_checkphotos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_main_admin(update.effective_user.id): return
    import os
    db = load_data()
    lines = []
    for key, path in SECTION_PHOTOS.items():
        exists = "✅ файл есть" if os.path.exists(path) else "❌ файл НЕ найден"
        cached = "💾 file_id в БД" if db.get("section_photo_ids", {}).get(key) else "⬜ нет в БД"
        lines.append(f"<b>{key}</b>: {exists} | {cached}\n  └ {path}")
    cwd = os.getcwd()
    files = os.listdir(".")
    photo_files = [f for f in files if f.lower().endswith((".jpg",".jpeg",".png",".gif"))]
    await update.message.reply_text(
        f"📁 Рабочая папка: <code>{cwd}</code>\n\n"
        + "\n".join(lines)
        + f"\n\n🖼 Все картинки в папке:\n" + ("\n".join(photo_files) if photo_files else "нет"),
        parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    async def auto_backup_loop(bot):
        """Автобэкап раз в неделю через asyncio.sleep"""
        await asyncio.sleep(7 * 24 * 3600)
        while True:
            if os.path.exists(DATA_FILE):
                try:
                    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    with open(DATA_FILE, "rb") as f:
                        await bot.send_document(
                            MAIN_ADMIN_ID, document=f,
                            filename=f"autobackup_{now_str}.json",
                            caption=f"🔄 Автобэкап\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
                except: pass
            await asyncio.sleep(7 * 24 * 3600)

    async def on_startup(app):
        asyncio.create_task(auto_backup_loop(app.bot))

    app.post_init = on_startup
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("clear",     cmd_clear))
    app.add_handler(CommandHandler("admin",     cmd_admin))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("event",     cmd_event))
    app.add_handler(CommandHandler("banlist",   cmd_banlist))
    app.add_handler(CommandHandler("contact",   cmd_contact))
    app.add_handler(CommandHandler("idea",      cmd_idea))
    app.add_handler(CommandHandler("tickets",   cmd_tickets))
    app.add_handler(CommandHandler("answered",  cmd_answered))
    app.add_handler(CommandHandler("reviews",      cmd_reviews))
    app.add_handler(CommandHandler("backup",       cmd_backup))
    app.add_handler(CommandHandler("stats",        cmd_stats))
    app.add_handler(CommandHandler("exportreviews",cmd_exportreviews))
    app.add_handler(CommandHandler("export",       cmd_export))
    app.add_handler(CommandHandler("polls",        cmd_polls))
    app.add_handler(CommandHandler("dm",           cmd_dm))
    app.add_handler(CommandHandler("broadcasts",   cmd_broadcasts_archive))
    app.add_handler(CommandHandler("find",         cmd_find))
    app.add_handler(CommandHandler("teacher",      cmd_teacher))
    app.add_handler(CommandHandler("profile",      cmd_profile))
    app.add_handler(CommandHandler("getfileid",    cmd_getfileid))
    app.add_handler(CommandHandler("checkphotos",  cmd_checkphotos))
    app.add_handler(CommandHandler("help",         cmd_help))
    app.add_handler(CommandHandler("botstatus",    cmd_botstatus))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    logger.info("Бот запущен...")
    import time as _t
    app.bot_data["start_time"] = _t.time()
    async def _post_init(application):
        await cleanup_old_tickets()
    app.post_init = _post_init
    app.run_polling()

if __name__ == "__main__":
    main()
