import asyncio
import os
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Если токена нет, выводим ошибку, чтобы бот не висел в пустую
if not BOT_TOKEN:
    raise ValueError("Токен не найден! Проверьте переменные окружения или файл .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------- ДАННЫЕ ----------
CASES = {
    "free": {
        "name": "🎁 Бесплатный кейс",
        "price": 0,
        "items": [
            {"name": "Мелкий брейнрот", "rarity": "common", "value": 10, "chance": 70},
            {"name": "Скибиди-стакан", "rarity": "rare", "value": 50, "chance": 25},
            {"name": "Сигма-брейнрот", "rarity": "epic", "value": 150, "chance": 5},
        ],
    },
    "common": {
        "name": "📦 Обычный кейс",
        "price": 100,
        "items": [
            {"name": "Мелкий брейнрот", "rarity": "common", "value": 30, "chance": 60},
            {"name": "Скибиди-стакан", "rarity": "rare", "value": 120, "chance": 30},
            {"name": "Сигма-брейнрот", "rarity": "epic", "value": 400, "chance": 10},
        ],
    },
    "legendary": {
        "name": "🔥 Легендарный кейс",
        "price": 500,
        "items": [
            {"name": "Скибиди-стакан", "rarity": "rare", "value": 200, "chance": 50},
            {"name": "Сигма-брейнрот", "rarity": "epic", "value": 700, "chance": 40},
            {"name": "Огайо-легенда", "rarity": "legendary", "value": 2000, "chance": 10},
        ],
    },
}

users_db = {}

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "balance": 100,
            "last_free_case": None,
            "inventory": [],
            "referral_count": 0,
            "pending_ref_bonus": 0,
        }
    return users_db[user_id]

def roll_item(case_key):
    items = CASES[case_key]["items"]
    total = sum(i["chance"] for i in items)
    r = random.uniform(0, total)
    upto = 0
    for item in items:
        upto += item["chance"]
        if r <= upto:
            return item
    return items[-1]

def can_open_free(user):
    if not user["last_free_case"]:
        return True
    return datetime.now() - user["last_free_case"] >= timedelta(days=1)

# ---------- ХЕНДЛЕРЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = get_user(message.from_user.id)
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = int(args[1].replace("ref_", ""))
        if referrer_id != message.from_user.id and referrer_id in users_db:
            ref_user = get_user(referrer_id)
            ref_user["referral_count"] += 1
            ref_user["pending_ref_bonus"] += 1
            try:
                await bot.send_message(
                    referrer_id,
                    f"👤 По твоей ссылке пришел новый игрок! Тебе начислен 🎟 кейс за юзернейм. Открой его командой /refcase"
                )
            except Exception:
                pass # Если пользователь заблокировал бота

    await message.answer(
        f"🧠 Добро пожаловать в <b>BrainWorld</b>, {message.from_user.first_name}!\n\n"
        f"💰 Баланс: <b>{user['balance']}</b> монет\n"
        f"🎟 Кейсов за юзернейм: <b>{user['pending_ref_bonus']}</b>\n\n"
        f"/cases — кейсы\n"
        f"/daily — бесплатный кейс\n"
        f"/balance — баланс\n"
        f"/refcase — открыть кейс за юзернейм\n"
        f"/ref — моя реферальная ссылка\n"
        f"/buy — пополнить монеты за Stars"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(f"💰 Баланс: <b>{user['balance']}</b> монет\n🎒 Предметов: {len(user['inventory'])}")

@dp.message(Command("cases"))
async def cmd_cases(message: Message):
    builder = InlineKeyboardBuilder()
    for key, case in CASES.items():
        if key == "free":
            continue
        builder.button(text=f"{case['name']} — {case['price']} монет", callback_data=f"case_{key}")
    builder.adjust(1)
    await message.answer("Выбери кейс:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("case_"))
async def open_paid_case(callback: CallbackQuery):
    case_key = callback.data.replace("case_", "")
    case = CASES[case_key]
    user = get_user(callback.from_user.id)

    if user["balance"] < case["price"]:
        await callback.answer("Недостаточно монет!", show_alert=True)
        return

    user["balance"] -= case["price"]
    item = roll_item(case_key)
    user["inventory"].append(item["name"])
    user["balance"] += item["value"]

    await callback.message.edit_text(
        f"{case['name']} открыт!\n\n"
        f"🎉 Выпало: <b>{item['name']}</b> ({item['rarity']})\n"
        f"💰 +{item['value']} монет\n\n"
        f"Текущий баланс: {user['balance']}"
    )
    await callback.answer()

@dp.message(Command("daily"))
async def cmd_daily(message: Message):
    user = get_user(message.from_user.id)
    if not can_open_free(user):
        next_time = user["last_free_case"] + timedelta(days=1)
        await message.answer(f"⏳ Бесплатный кейс уже открыт. Следующий доступен после {next_time.strftime('%d.%m %H:%M')}")
        return

    user["last_free_case"] = datetime.now()
    item = roll_item("free")
    user["inventory"].append(item["name"])
    user["balance"] += item["value"]

    await message.answer(
        f"🎁 Бесплатный кейс открыт!\n\n"
        f"Выпало: <b>{item['name']}</b> ({item['rarity']})\n"
        f"💰 +{item['value']} монет"
    )

@dp.message(Command("ref"))
async def cmd_ref(message: Message):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"
    user = get_user(message.from_user.id)
    await message.answer(
        f"🔗 Твоя ссылка:\n{link}\n\n"
        f"За каждого друга — 🎟 кейс за юзернейм.\n"
        f"Приглашено: {user['referral_count']}"
    )

@dp.message(Command("refcase"))
async def cmd_refcase(message: Message):
    user = get_user(message.from_user.id)
    if user["pending_ref_bonus"] <= 0:
        await message.answer("У тебя нет кейсов за юзернейм. Пригласи друга через /ref!")
        return

    user["pending_ref_bonus"] -= 1
    items = CASES["legendary"]["items"]
    item = random.choice(items)
    user["inventory"].append(item["name"])
    user["balance"] += item["value"]

    await message.answer(
        f"👤 Кейс за юзернейм открыт!\n\n"
        f"Выпало: <b>{item['name']}</b> ({item['rarity']})\n"
        f"💰 +{item['value']} монет\n"
        f"Осталось кейсов: {user['pending_ref_bonus']}"
    )

# ---------- ОПЛАТА STARS ----------
@dp.message(Command("buy"))
async def cmd_buy(message: Message):
    prices = [LabeledPrice(label="1000 BrainWorld монет", amount=100)]
    await message.answer_invoice(
        title="Пополнение BrainWorld",
        description="Получи 1000 монет для открытия кейсов",
        payload="buy_1000_coins",
        currency="XTR",
        prices=prices,
        provider_token="",
    )

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def on_successful_payment(message: Message):
    user = get_user(message.from_user.id)
    payment = message.successful_payment

    if payment.invoice_payload == "buy_1000_coins":
        user["balance"] += 1000
        await message.answer(
            f"✅ Оплата получена! Начислено 1000 монет.\n"
            f"💰 Текущий баланс: {user['balance']}"
        )

# ---------- ЗАПУСК ----------
async def main():
    print("Бот BrainWorld запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
