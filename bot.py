import os
import asyncio
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- БЛОК ДЛЯ ПОДДЕРЖКИ РАБОТЫ 24/7 (ОБЯЗАТЕЛЬНО ДЛЯ KOYEB) ---
app = Flask('')

@app.route('/')
def home():
    return "Бот запущен и работает!"

def run_web():
    # Хостинг будет видеть активность на этом порту и не выключит бота
    app.run(host='0.0.0.0', port=8080)

# Запуск веб-сервера в фоновом потоке
Thread(target=run_web).start()
# ------------------------------------------------------------

# Берем токен из переменных окружения (настроим в панели Koyeb)
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(f"Привет, {message.from_user.full_name}! Я работаю 24/7 на облачном сервере.")

# Эхо-ответ на любое сообщение
@dp.message()
async def echo_handler(message: types.Message):
    if message.text:
        await message.answer(f"Ты написал: {message.text}")

# Запуск бота
async def main():
    print("Логи: Бот успешно вышел в сеть!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Ошибка: {e}")
