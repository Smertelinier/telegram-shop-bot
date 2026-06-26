import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, Message,
    CallbackQuery
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8623571350:AAGPaTk3CJCfsYxs0DPU_QW0x0FeWLERpb0")
ADMIN_USERNAME = "Saidikcs"
BOT_USERNAME = "SaidikMarketBot"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

PRODUCTS_FILE = "products.json"
USERS_FILE = "users.json"

_products_cache = None
_products_lock = asyncio.Lock()

_users_cache = None
_users_lock = asyncio.Lock()

_state = {"products_dirty": False, "users_dirty": False}

class AddProduct(StatesGroup):
    name = State()
    desc = State()
    price = State()
    category = State()
    delivery = State()

def _load_products():
    global _products_cache
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            _products_cache = json.load(f)
    else:
        _products_cache = {"products": [], "categories": ["keys", "accounts", "services"]}
        _save_products()
    return _products_cache

def _save_products():
    global _products_cache
    tmp = PRODUCTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_products_cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PRODUCTS_FILE)

def _get_products():
    global _products_cache
    if _products_cache is None:
        _load_products()
    return _products_cache

async def _flush_products():
    if _state["products_dirty"]:
        async with _products_lock:
            if _state["products_dirty"]:
                _save_products()
                _state["products_dirty"] = False

async def _periodic_flush_products():
    while True:
        await asyncio.sleep(30)
        await _flush_products()

def _load_users():
    global _users_cache
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            _users_cache = json.load(f)
    else:
        _users_cache = {}
        _save_users()
    return _users_cache

def _save_users():
    global _users_cache
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_users_cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, USERS_FILE)

def _get_users():
    global _users_cache
    if _users_cache is None:
        _load_users()
    return _users_cache

async def _flush_users():
    if _state["users_dirty"]:
        async with _users_lock:
            if _state["users_dirty"]:
                _save_users()
                _state["users_dirty"] = False

async def _periodic_flush_users():
    while True:
        await asyncio.sleep(30)
        await _flush_users()

def get_or_create_user(user_id, username=None, full_name=None):
    users = _get_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "username": username,
            "full_name": full_name,
            "purchases": []
        }
        _state["users_dirty"] = True
    return users[uid]

def is_admin(username):
    return username == ADMIN_USERNAME

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Каталог", callback_data="catalog")]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Add product", callback_data="admin_addproduct")],
        [InlineKeyboardButton(text="📋 List products", callback_data="admin_list")],
        [InlineKeyboardButton(text="❌ Remove product", callback_data="admin_remove")],
        [InlineKeyboardButton(text="🔄 Toggle availability", callback_data="admin_toggle")],
        [InlineKeyboardButton(text="📊 Stats", callback_data="admin_stats")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: Message):
    get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer(
        f"👋 Добро пожаловать в магазин цифровых товаров!\n\n"
        f"Здесь вы можете приобрести ключи, аккаунты и услуги.\n"
        f"Оплата принимается в Telegram Stars ⭐",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("catalog"))
async def cmd_catalog(message: Message):
    products = _get_products()
    categories = products["categories"]
    if not categories:
        await message.answer("Каталог пуст.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat_{cat}")]
        for cat in categories
    ])
    await message.answer("Выберите категорию:", reply_markup=kb)

@dp.message(Command("my"))
async def cmd_my(message: Message):
    user = get_or_create_user(message.from_user.id)
    purchases = user.get("purchases", [])
    if not purchases:
        await message.answer("У вас пока нет покупок.")
        return
    products = _get_products()
    text = "📋 Ваши покупки:\n\n"
    for p in purchases:
        prod = next((x for x in products["products"] if x["id"] == p["product_id"]), None)
        name = prod["name"] if prod else f"Товар #{p['product_id']}"
        text += f"• {name} — {p['date']}\n{p['delivery']}\n\n"
    await message.answer(text)

@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    await message.answer(
        "💎 Оплата принимается через Telegram Stars ⭐\n\n"
        "Для покупки выберите товар в каталоге /catalog"
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 Помощь:\n\n"
        "/start — Главное меню\n"
        "/catalog — Каталог товаров\n"
        "/my — Мои покупки\n"
        "/pay — Информация об оплате\n"
        "/help — Эта справка"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.username):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("⚙️ Панель администратора:", reply_markup=get_admin_keyboard())

@dp.message(Command("addproduct"))
async def cmd_addproduct(message: Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        await message.answer("⛔ Доступ запрещён.")
        return
    await state.set_state(AddProduct.name)
    await message.answer("Введите название товара:")

@dp.callback_query(lambda c: c.data == "admin_addproduct")
async def admin_addproduct_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddProduct.name)
    await callback.message.answer("Введите название товара:")

@dp.message(AddProduct.name)
async def addproduct_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.desc)
    await message.answer("Введите описание товара:")

@dp.message(AddProduct.desc)
async def addproduct_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("Введите цену (в звёздах):")

@dp.message(AddProduct.price)
async def addproduct_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Цена должна быть положительным числом. Попробуйте ещё раз:")
        return
    await state.update_data(price=price)
    await state.set_state(AddProduct.category)
    products = _get_products()
    cats = products["categories"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=c.capitalize(), callback_data=f"ap_cat_{c}")]
        for c in cats
    ] + [[InlineKeyboardButton(text="➕ Новая категория", callback_data="ap_cat_new")]])
    await message.answer("Выберите категорию:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("ap_cat_"))
async def addproduct_category_cb(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    cat = callback.data.replace("ap_cat_", "")
    if cat == "new":
        await state.set_state(AddProduct.category)
        await callback.message.answer("Введите название новой категории:")
        return
    await state.update_data(category=cat)
    await state.set_state(AddProduct.delivery)
    await callback.message.answer("Введите содержимое доставки (текст ключа/данные):")

@dp.message(AddProduct.category)
async def addproduct_category_text(message: Message, state: FSMContext):
    cat = message.text.strip().lower()
    products = _get_products()
    if cat not in products["categories"]:
        products["categories"].append(cat)
        _state["products_dirty"] = True
    await state.update_data(category=cat)
    await state.set_state(AddProduct.delivery)
    await message.answer("Введите содержимое доставки (текст ключа/данные):")

@dp.message(AddProduct.delivery)
async def addproduct_delivery(message: Message, state: FSMContext):
    data = await state.get_data()
    products = _get_products()
    new_id = max((p["id"] for p in products["products"]), default=0) + 1
    products["products"].append({
        "id": new_id,
        "name": data["name"],
        "desc": data["desc"],
        "price": data["price"],
        "category": data["category"],
        "delivery": message.text,
        "available": True
    })
    _state["products_dirty"] = True
    await state.clear()
    await message.answer(f"✅ Товар «{data['name']}» добавлен (ID: {new_id})")

@dp.callback_query(lambda c: c.data == "admin_list")
async def admin_list_cb(callback: CallbackQuery):
    await callback.answer()
    products = _get_products()
    if not products["products"]:
        await callback.message.answer("Товаров нет.")
        return
    text = "📋 Список товаров:\n\n"
    for p in products["products"]:
        status = "✅" if p["available"] else "❌"
        text += f"{status} ID {p['id']}: {p['name']} — {p['price']}⭐ ({p['category']})\n"
    await callback.message.answer(text)

@dp.callback_query(lambda c: c.data == "admin_remove")
async def admin_remove_cb(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Введите ID товара для удаления:")
    _pending_actions[callback.from_user.id] = "remove"

@dp.callback_query(lambda c: c.data == "admin_toggle")
async def admin_toggle_cb(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Введите ID товара для переключения доступности:")
    _pending_actions[callback.from_user.id] = "toggle"

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_cb(callback: CallbackQuery):
    await callback.answer()
    users = _get_users()
    products = _get_products()
    total_users = len(users)
    total_sales = 0
    total_revenue = 0
    for uid, u in users.items():
        for p in u.get("purchases", []):
            total_sales += 1
            prod = next((x for x in products["products"] if x["id"] == p["product_id"]), None)
            if prod:
                total_revenue += prod["price"]
    await callback.message.answer(
        f"📊 Статистика:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🛒 Всего продаж: {total_sales}\n"
        f"⭐ Выручка: {total_revenue} Stars"
    )

@dp.callback_query(lambda c: c.data == "catalog")
async def catalog_cb(callback: CallbackQuery):
    await callback.answer()
    products = _get_products()
    categories = products["categories"]
    if not categories:
        await callback.message.answer("Каталог пуст.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"cat_{cat}")]
        for cat in categories
    ])
    await callback.message.answer("Выберите категорию:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def category_cb(callback: CallbackQuery):
    await callback.answer()
    cat = callback.data.replace("cat_", "")
    products = _get_products()
    items = [p for p in products["products"] if p["category"] == cat and p["available"]]
    if not items:
        await callback.message.answer("В этой категории пока нет товаров.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p["name"], callback_data=f"prod_{p['id']}")]
        for p in items
    ])
    await callback.message.answer(f"Категория: {cat}", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("prod_"))
async def product_cb(callback: CallbackQuery):
    await callback.answer()
    pid = int(callback.data.replace("prod_", ""))
    products = _get_products()
    prod = next((p for p in products["products"] if p["id"] == pid), None)
    if not prod:
        await callback.message.answer("Товар не найден.")
        return
    if not prod["available"]:
        await callback.message.answer("❌ Этот товар временно недоступен.")
        return
    text = (
        f"📦 {prod['name']}\n\n"
        f"{prod['desc']}\n\n"
        f"💰 Цена: {prod['price']} ⭐"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Купить за {prod['price']}⭐", callback_data=f"buy_{pid}")]
    ])
    await callback.message.answer(text, reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def buy_cb(callback: CallbackQuery):
    await callback.answer()
    pid = int(callback.data.replace("buy_", ""))
    products = _get_products()
    prod = next((p for p in products["products"] if p["id"] == pid), None)
    if not prod:
        await callback.message.answer("Товар не найден.")
        return
    if not prod["available"]:
        await callback.message.answer("❌ Этот товар временно недоступен.")
        return
    prices = [LabeledPrice(label=prod["name"], amount=prod["price"])]
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=prod["name"],
        description=prod["desc"],
        payload=f"product_{pid}",
        provider_token="",
        currency="XTR",
        prices=prices,
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.message(lambda m: m.successful_payment is not None)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    pid = int(payload.replace("product_", ""))
    products = _get_products()
    prod = next((p for p in products["products"] if p["id"] == pid), None)
    if not prod:
        await message.answer("Ошибка: товар не найден.")
        return
    user = get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    user["purchases"].append({
        "product_id": pid,
        "date": datetime.now().isoformat(),
        "delivery": prod["delivery"]
    })
    _state["users_dirty"] = True
    await message.answer(
        f"✅ Оплата получена!\n\n"
        f"📦 Ваш товар:\n{prod['delivery']}\n\n"
        f"Спасибо за покупку! 🎉"
    )

_pending_actions = {}

@dp.message()
async def handle_text(message: Message):
    uid = message.from_user.id
    text = message.text.strip()
    action = _pending_actions.pop(uid, None)

    if action == "remove":
        try:
            pid = int(text)
            products = _get_products()
            products["products"] = [p for p in products["products"] if p["id"] != pid]
            _state["products_dirty"] = True
            await message.answer(f"✅ Товар ID {pid} удалён.")
        except ValueError:
            await message.answer("Некорректный ID.")
        return

    if action == "toggle":
        try:
            pid = int(text)
            products = _get_products()
            prod = next((p for p in products["products"] if p["id"] == pid), None)
            if not prod:
                await message.answer("Товар не найден.")
                return
            prod["available"] = not prod["available"]
            _state["products_dirty"] = True
            status = "доступен" if prod["available"] else "недоступен"
            await message.answer(f"✅ Товар ID {pid} теперь {status}.")
        except ValueError:
            await message.answer("Некорректный ID.")
        return

async def main():
    _get_products()
    _get_users()

    asyncio.create_task(_periodic_flush_products())
    asyncio.create_task(_periodic_flush_users())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
