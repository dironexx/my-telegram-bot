import asyncio
import sqlite3
import logging
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command, or_f
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN") 
OWNER_ID = 5065061081 # ЗАМЕНИ НА СВОЙ ID (цифрами)
NEWS_URL = "https://t.me/vanilandes"

if not BOT_TOKEN:
    logger.error("ОШИБКА: Токен не найден в Environment Variables!")
    exit(1)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('vanilla_admin.db')
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, user_name TEXT, type TEXT, text TEXT)')
    cur.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    cur.execute('CREATE TABLE IF NOT EXISTS blacklist (user_id INTEGER PRIMARY KEY)')
    cur.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class States(StatesGroup):
    report_nick = State()      
    report_reason = State()    
    waiting_support = State()  
    admin_reply = State()
    admin_broadcast = State()
    admin_ban_id = State()
    admin_add_id = State()

# --- КЛАВИАТУРЫ ---
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 IP Сервера", callback_data="ip"), InlineKeyboardButton(text="📚 Правила", callback_data="rules")],
        [InlineKeyboardButton(text="📢 Новости", url=NEWS_URL)],
        [InlineKeyboardButton(text="🚨 Репорт", callback_data="req_report"), InlineKeyboardButton(text="📩 Связь", callback_data="req_support")]
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Репорты", callback_data="view_REPORT"), InlineKeyboardButton(text="📩 Обращения", callback_data="view_SUPPORT")],
        [InlineKeyboardButton(text="🛡 Бан / Разбан", callback_data="admin_ban_system"), InlineKeyboardButton(text="📢 Рассылка", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add_new")],
        [InlineKeyboardButton(text="❌ Закрыть меню", callback_data="admin_close")]
    ])

# --- ПРОВЕРКИ ---
async def is_admin(user_id):
    if user_id == OWNER_ID: return True
    conn = sqlite3.connect('vanilla_admin.db')
    res = conn.cursor().execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return res is not None

async def check_access(m):
    user_id = m.from_user.id
    conn = sqlite3.connect('vanilla_admin.db')
    res = conn.cursor().execute("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return res is None

# --- ОБРАБОТЧИКИ ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if not await check_access(message): return
    await state.clear()  # Сбрасываем зависшие репорты
    conn = sqlite3.connect('vanilla_admin.db')
    conn.cursor().execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit(); conn.close()
    await message.answer(f"👋 Привет, {message.from_user.first_name}!\nДобро пожаловать в VanillaLand.", reply_markup=main_kb())

@router.message(or_f(F.text.lower().in_({"админ", "админка", "ап"}), Command("admin")))
async def admin_entry(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("🛠 Панель управления:", reply_markup=admin_kb())

# --- ЛОГИКА РЕПОРТА (Коротко) ---
@router.callback_query(F.data == "req_report")
async def report_1(cb: CallbackQuery, state: FSMContext):
    await cb.message.delete()
    msg = await cb.message.answer("🚨 Введите <b>точный никнейм</b> нарушителя:", parse_mode="HTML")
    await state.set_state(States.report_nick); await state.update_data(last_id=msg.message_id)

@router.message(States.report_nick)
async def report_2(m: Message, state: FSMContext):
    d = await state.get_data()
    try: await bot.delete_message(m.chat.id, d['last_id']); await m.delete()
    except: pass
    await state.update_data(nick=m.text)
    msg = await m.answer(f"📝 Теперь введите <b>причину</b> для {m.text}:", parse_mode="HTML")
    await state.set_state(States.report_reason); await state.update_data(last_id=msg.message_id)

@router.message(States.report_reason)
async def report_3(m: Message, state: FSMContext):
    d = await state.get_data()
    try: await bot.delete_message(m.chat.id, d['last_id']); await m.delete()
    except: pass
    txt = f"<b>Нарушитель:</b> <code>{d['nick']}</code>\n<b>Причина:</b> {m.text}"
    conn = sqlite3.connect('vanilla_admin.db')
    conn.cursor().execute("INSERT INTO tickets (user_id, user_name, type, text) VALUES (?, ?, ?, ?)", (m.from_user.id, m.from_user.full_name, "REPORT", txt))
    conn.commit(); conn.close()
    await m.answer("✅ Репорт отправлен!", reply_markup=main_kb()); await state.clear()

# --- СВЯЗЬ ---
@router.callback_query(F.data == "req_support")
async def supp_1(cb: CallbackQuery, state: FSMContext):
    await cb.message.delete()
    msg = await cb.message.answer("📩 Напишите ваше обращение администрации:")
    await state.set_state(States.waiting_support); await state.update_data(last_id=msg.message_id)

@router.message(States.waiting_support)
async def supp_2(m: Message, state: FSMContext):
    d = await state.get_data()
    try: await bot.delete_message(m.chat.id, d['last_id']); await m.delete()
    except: pass
    conn = sqlite3.connect('vanilla_admin.db')
    conn.cursor().execute("INSERT INTO tickets (user_id, user_name, type, text) VALUES (?, ?, ?, ?)", (m.from_user.id, m.from_user.full_name, "SUPPORT", m.text))
    conn.commit(); conn.close()
    await m.answer("✅ Отправлено!", reply_markup=main_kb()); await state.clear()

# --- АДМИНКА (Просмотр и Ответы) ---
async def show_next(m_or_cb, t_type):
    conn = sqlite3.connect('vanilla_admin.db')
    t = conn.cursor().execute("SELECT id, user_name, text, user_id FROM tickets WHERE type = ? ORDER BY id ASC LIMIT 1", (t_type,)).fetchone()
    conn.close()
    if not t:
        if isinstance(m_or_cb, CallbackQuery): await m_or_cb.message.edit_text(f"✅ Список {t_type} пуст.", reply_markup=admin_kb())
        else: await m_or_cb.answer(f"✅ Список {t_type} пуст.", reply_markup=admin_kb())
        return
    txt = f"<b>{t_type} #{t[0]}</b>\nОт: {t[1]}\nID: <code>{t[3]}</code>\n\n{t[2]}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✍️ Ответить", callback_data=f"ans_{t[0]}_{t_type}")],[InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{t[0]}_{t_type}")]])
    if isinstance(m_or_cb, CallbackQuery): await m_or_cb.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")
    else: await m_or_cb.answer(txt, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("view_"))
async def v_t(cb: CallbackQuery): await show_next(cb, cb.data.split("_")[1])

@router.callback_query(F.data.startswith("del_"))
async def d_t(cb: CallbackQuery):
    p = cb.data.split("_")
    conn = sqlite3.connect('vanilla_admin.db'); conn.cursor().execute("DELETE FROM tickets WHERE id = ?", (p[1],)); conn.commit(); conn.close()
    await show_next(cb, p[2])

@router.callback_query(F.data.startswith("ans_"))
async def a_t(cb: CallbackQuery, state: FSMContext):
    p = cb.data.split("_")
    await state.update_data(aid=p[1], atype=p[2]); await state.set_state(States.admin_reply)
    await cb.message.answer(f"✍️ Ответ для #{p[1]}:")

@router.message(States.admin_reply)
async def a_s(m: Message, state: FSMContext):
    d = await state.get_data()
    conn = sqlite3.connect('vanilla_admin.db'); res = conn.cursor().execute("SELECT user_id FROM tickets WHERE id = ?", (d['aid'],)).fetchone()
    if res:
        try: await bot.send_message(res[0], f"✉️ <b>Ответ администрации:</b>\n\n{m.text}", parse_mode="HTML")
        except: pass
        conn.cursor().execute("DELETE FROM tickets WHERE id = ?", (d['aid'],)); conn.commit()
    conn.close(); await state.clear(); await show_next(m, d['atype'])

# --- АДМИН КНОПКИ ---
@router.callback_query(F.data == "admin_ban_system")
async def ban_s(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("🛡 Введите ID для Бана/Разбана:"); await state.set_state(States.admin_ban_id)

@router.message(States.admin_ban_id)
async def ban_p(m: Message, state: FSMContext):
    try:
        tid = int(m.text)
        conn = sqlite3.connect('vanilla_admin.db'); cur = conn.cursor()
        if cur.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (tid,)).fetchone():
            cur.execute("DELETE FROM blacklist WHERE user_id = ?", (tid,)); await m.answer(f"✅ {tid} разбанен.")
        else:
            cur.execute("INSERT INTO blacklist VALUES (?)", (tid,)); await m.answer(f"🚫 {tid} забанен.")
        conn.commit(); conn.close()
    except: await m.answer("❌ Ошибка в ID.")
    await state.clear()

@router.callback_query(F.data == "admin_add_new")
async def add_a(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID: return
    await cb.message.answer("➕ Введите ID нового админа:"); await state.set_state(States.admin_add_id)

@router.message(States.admin_add_id)
async def add_a_p(m: Message, state: FSMContext):
    try:
        conn = sqlite3.connect('vanilla_admin.db'); conn.cursor().execute("INSERT OR IGNORE INTO admins VALUES (?)", (int(m.text),)); conn.commit(); conn.close()
        await m.answer(f"✅ {m.text} назначен админом.")
    except: await m.answer("❌ Ошибка.")
    await state.clear()

@router.callback_query(F.data == "start_broadcast")
async def br_s(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("📢 Введите текст рассылки:"); await state.set_state(States.admin_broadcast)

@router.message(States.admin_broadcast)
async def br_p(m: Message, state: FSMContext):
    conn = sqlite3.connect('vanilla_admin.db'); users = conn.cursor().execute("SELECT user_id FROM users").fetchall(); conn.close()
    for u in users:
        try: await bot.send_message(u[0], m.text)
        except: pass
    await m.answer("✅ Рассылка завершена!", reply_markup=admin_kb()); await state.clear()

# --- ИНФО ---
@router.callback_query(F.data == "ip")
async def s_ip(c: CallbackQuery):
    await c.message.answer("🌐 IP: <code>ig01.incloudgame.ru:27119</code>", parse_mode="HTML"); await c.answer()

@router.callback_query(F.data == "rules")
async def s_rl(c: CallbackQuery):
    await c.message.answer("📖 <b>Наши правила:</b>\n\n🔹 <a href='https://telegra.ph/Pravila-Socialnogo-Vzaimodejstviya-VanillaLand-01-30'>Правила Чата</a>\n🔹 <a href='https://telegra.ph/Pravila-Vanilnogo-Servera-Vanilla-Land-12-03'>Правила Сервера</a>", parse_mode="HTML", disable_web_page_preview=True); await c.answer()

@router.callback_query(F.data == "admin_close")
async def cl(c: CallbackQuery): await c.message.delete()

# --- ЭХО (ОТВЕТ НА ВСЁ ОСТАЛЬНОЕ) ---
@router.message()
async def echo(m: Message):
    if not await check_access(m): return
    await m.answer("🤔 Я не понимаю вас. Напишите /start, чтобы открыть меню.")

# --- ЗАПУСК ---
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
