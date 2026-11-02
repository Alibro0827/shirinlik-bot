import asyncio
import html
import json
import logging
import os
import re
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    WebAppInfo,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from products import (
    CATEGORIES,
    CONTACT_PHONE,
    CURRENCY,
    DELIVERY_FEE,
    FREE_DELIVERY_FROM,
    PRODUCTS,
    SHOP_NAME,
    WORK_HOURS,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "orders.db")
# Mini App (index.html) joylashgan HTTPS manzil, masalan GitHub Pages havolasi
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
BTN_APP = "🌈 Ilovani ochish"

logging.basicConfig(level=logging.INFO)
router = Router()

# ---------------------------------------------------------------- tugma matnlari
BTN_MENU = "🍰 Menyu"
BTN_CART = "🛒 Savat"
BTN_ORDERS = "📦 Buyurtmalarim"
BTN_CONTACT = "☎️ Aloqa"
BTN_CANCEL = "❌ Bekor qilish"
BTN_PICKUP = "🏪 O'zim olib ketaman"
BTN_LOCATION = "📍 Lokatsiyamni yuborish"
BTN_CASH = "💵 Naqd pul"
BTN_CARD = "💳 Karta (olganda to'layman)"

# savat: {user_id: {product_id: miqdor}}  (bot qayta ishga tushsa tozalanadi)
CARTS: dict[int, dict[str, int]] = {}


# ---------------------------------------------------------------- baza
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT, phone TEXT, address TEXT, payment TEXT,
                items TEXT, subtotal INTEGER, delivery INTEGER, total INTEGER,
                status TEXT DEFAULT 'new',
                created TEXT
            )"""
        )


STATUS_TEXT = {
    "new": "🕐 Yangi",
    "accepted": "✅ Qabul qilindi",
    "delivered": "🎉 Yetkazildi",
    "cancelled": "❌ Bekor qilindi",
}


# ---------------------------------------------------------------- yordamchilar
def money(n: int) -> str:
    return f"{n:,}".replace(",", " ") + f" {CURRENCY}"


def esc(s: str) -> str:
    return html.escape(s or "")


def cart_of(uid: int) -> dict[str, int]:
    return CARTS.setdefault(uid, {})


def cart_subtotal(cart: dict[str, int]) -> int:
    return sum(PRODUCTS[p]["price"] * q for p, q in cart.items() if p in PRODUCTS)


def delivery_fee(subtotal: int, pickup: bool) -> int:
    if pickup or subtotal >= FREE_DELIVERY_FROM:
        return 0
    return DELIVERY_FEE


def valid_phone(text: str) -> str | None:
    """+998901234567 ko'rinishiga keltiradi, noto'g'ri bo'lsa None."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return None


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_MENU), KeyboardButton(text=BTN_CART)],
        [KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_CONTACT)],
    ]
    if WEBAPP_URL.startswith("https://"):
        rows.insert(0, [KeyboardButton(text=BTN_APP, web_app=WebAppInfo(url=WEBAPP_URL))])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Pastdagi tugmalardan tanlang 👇",
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True
    )


async def show(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup, photo=None):
    """Xabarni tahrirlaydi; turi mos kelmasa o'chirib qayta yuboradi."""
    msg = call.message
    try:
        if photo and msg.photo:
            await msg.edit_media(
                InputMediaPhoto(media=photo, caption=text, parse_mode=ParseMode.HTML),
                reply_markup=kb,
            )
        elif not photo and not msg.photo:
            await msg.edit_text(text, reply_markup=kb)
        else:
            raise ValueError("tur mos emas")
    except TelegramBadRequest as e:
        if "not modified" in str(e):
            return
        await _resend(msg, text, kb, photo)
    except ValueError:
        await _resend(msg, text, kb, photo)


async def _resend(msg: Message, text, kb, photo):
    try:
        await msg.delete()
    except TelegramBadRequest:
        pass
    if photo:
        await msg.answer_photo(photo, caption=text, reply_markup=kb)
    else:
        await msg.answer(text, reply_markup=kb)


# ---------------------------------------------------------------- inline klaviaturalar
def categories_kb(uid: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, cat in CATEGORIES.items():
        b.button(text=cat["title"], callback_data=f"cat:{key}")
    b.adjust(2)
    count = sum(cart_of(uid).values())
    if count:
        b.row(
            InlineKeyboardButton(
                text=f"🛒 Savat ({count}) — {money(cart_subtotal(cart_of(uid)))}",
                callback_data="cart:view",
            )
        )
    return b.as_markup()


def category_kb(key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for item in CATEGORIES[key]["items"]:
        b.row(
            InlineKeyboardButton(
                text=f"{item['name']} — {money(item['price'])}",
                callback_data=f"prod:{item['id']}",
            )
        )
    b.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu"))
    return b.as_markup()


def product_kb(pid: str, qty: int) -> InlineKeyboardMarkup:
    price = PRODUCTS[pid]["price"] * qty
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="➖", callback_data=f"qty:{pid}:{max(1, qty - 1)}"),
        InlineKeyboardButton(text=f"{qty} dona", callback_data="noop"),
        InlineKeyboardButton(text="➕", callback_data=f"qty:{pid}:{min(50, qty + 1)}"),
    )
    b.row(
        InlineKeyboardButton(
            text=f"🛒 Savatga qo'shish · {money(price)}", callback_data=f"add:{pid}:{qty}"
        )
    )
    cat_key = next(k for k, c in CATEGORIES.items() if any(i["id"] == pid for i in c["items"]))
    b.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"cat:{cat_key}"))
    return b.as_markup()


def product_text(pid: str, qty: int) -> str:
    p = PRODUCTS[pid]
    return (
        f"<b>{esc(p['name'])}</b>\n\n"
        f"{esc(p['desc'])}\n\n"
        f"💰 Narxi: <b>{money(p['price'])}</b>"
    )


def cart_text_kb(uid: int):
    cart = cart_of(uid)
    if not cart:
        b = InlineKeyboardBuilder()
        b.button(text="🍰 Menyuga o'tish", callback_data="menu")
        return "🛒 <b>Savatingiz bo'sh</b>\n\nMazali shirinliklarni tanlang 😋", b.as_markup()

    lines = ["🛒 <b>Sizning savatingiz</b>\n"]
    for pid, q in cart.items():
        p = PRODUCTS[pid]
        lines.append(f"▫️ {esc(p['name'])}\n    {q} × {money(p['price'])} = <b>{money(p['price'] * q)}</b>")
    sub = cart_subtotal(cart)
    lines.append(f"\n💰 Mahsulotlar: <b>{money(sub)}</b>")
    if sub >= FREE_DELIVERY_FROM:
        lines.append("🚚 Yetkazib berish: <b>BEPUL</b> 🎁")
    else:
        lines.append(
            f"🚚 Yetkazib berish: {money(DELIVERY_FEE)}\n"
            f"<i>({money(FREE_DELIVERY_FROM - sub)} qo'shsangiz yetkazish bepul bo'ladi)</i>"
        )

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Buyurtma berish", callback_data="cart:checkout"))
    for pid in cart:
        b.row(InlineKeyboardButton(text=f"❌ {PRODUCTS[pid]['name']}", callback_data=f"cart:del:{pid}"))
    b.row(
        InlineKeyboardButton(text="➕ Yana qo'shish", callback_data="menu"),
        InlineKeyboardButton(text="🗑 Tozalash", callback_data="cart:clear"),
    )
    return "\n".join(lines), b.as_markup()


# ---------------------------------------------------------------- FSM
class Order(StatesGroup):
    phone = State()
    address = State()
    payment = State()
    confirm = State()


# ---------------------------------------------------------------- start va asosiy menyu
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    name = esc(message.from_user.first_name)
    await message.answer(
        f"Assalomu alaykum, <b>{name}</b>! 👋\n\n"
        f"🍰 <b>{esc(SHOP_NAME)}</b> do'koniga xush kelibsiz!\n"
        "Bizda eng mazali tortlar, pirojniylar va shirinliklar sizni kutmoqda 😋\n\n"
        "Buyurtma berish uchun <b>«🍰 Menyu»</b> tugmasini bosing 👇",
        reply_markup=main_menu(),
    )


@router.message(F.text == BTN_CANCEL)
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi. Asosiy menyuga qaytdik 🏠", reply_markup=main_menu())


@router.message(F.text == BTN_MENU)
@router.message(Command("menu"))
async def open_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🍰 <b>Menyu</b>\n\nQaysi bo'limni ko'rmoqchisiz?",
        reply_markup=categories_kb(message.from_user.id),
    )


@router.message(F.text == BTN_CART)
@router.message(Command("cart"))
async def open_cart(message: Message, state: FSMContext):
    await state.clear()
    text, kb = cart_text_kb(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.message(F.text == BTN_CONTACT)
async def contact(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"☎️ <b>Biz bilan bog'lanish</b>\n\n"
        f"📞 Telefon: {esc(CONTACT_PHONE)}\n"
        f"🕘 Ish vaqti: {esc(WORK_HOURS)}\n"
        f"🚚 Yetkazib berish: {money(DELIVERY_FEE)} "
        f"({money(FREE_DELIVERY_FROM)} dan yuqori buyurtmada bepul)"
    )


@router.message(F.text == BTN_ORDERS)
async def my_orders(message: Message, state: FSMContext):
    await state.clear()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5",
            (message.from_user.id,),
        ).fetchall()
    if not rows:
        await message.answer("📦 Sizda hali buyurtmalar yo'q.\n«🍰 Menyu» orqali birinchi buyurtmangizni bering!")
        return
    parts = ["📦 <b>Oxirgi buyurtmalaringiz</b>\n"]
    for r in rows:
        items = json.loads(r["items"])
        names = ", ".join(f"{i['name']} ×{i['qty']}" for i in items)
        parts.append(
            f"<b>№{r['id']}</b> · {STATUS_TEXT.get(r['status'], r['status'])}\n"
            f"{esc(names)}\n💰 {money(r['total'])} · {r['created']}\n"
        )
    await message.answer("\n".join(parts))


# ---------------------------------------------------------------- inline callbacklar
@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    await show(call, "🍰 <b>Menyu</b>\n\nQaysi bo'limni ko'rmoqchisiz?", categories_kb(call.from_user.id))
    await call.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(call: CallbackQuery):
    key = call.data.split(":")[1]
    if key not in CATEGORIES:
        return await call.answer()
    await show(call, f"{CATEGORIES[key]['title']}\n\nTanlang 👇", category_kb(key))
    await call.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(call: CallbackQuery):
    pid = call.data.split(":")[1]
    if pid not in PRODUCTS:
        return await call.answer()
    await show(call, product_text(pid, 1), product_kb(pid, 1), PRODUCTS[pid].get("photo"))
    await call.answer()


@router.callback_query(F.data.startswith("qty:"))
async def cb_qty(call: CallbackQuery):
    _, pid, qty = call.data.split(":")
    if pid not in PRODUCTS:
        return await call.answer()
    qty = int(qty)
    await show(call, product_text(pid, qty), product_kb(pid, qty), PRODUCTS[pid].get("photo"))
    await call.answer()


@router.callback_query(F.data.startswith("add:"))
async def cb_add(call: CallbackQuery):
    _, pid, qty = call.data.split(":")
    if pid not in PRODUCTS:
        return await call.answer()
    cart = cart_of(call.from_user.id)
    cart[pid] = min(50, cart.get(pid, 0) + int(qty))
    await call.answer(f"✅ {PRODUCTS[pid]['name']} savatga qo'shildi!", show_alert=False)
    cat_key = next(k for k, c in CATEGORIES.items() if any(i["id"] == pid for i in c["items"]))
    await show(call, f"{CATEGORIES[cat_key]['title']}\n\n✅ Savatga qo'shildi! Yana tanlang 👇", category_kb(cat_key))


@router.callback_query(F.data == "cart:view")
async def cb_cart_view(call: CallbackQuery):
    text, kb = cart_text_kb(call.from_user.id)
    await show(call, text, kb)
    await call.answer()


@router.callback_query(F.data.startswith("cart:del:"))
async def cb_cart_del(call: CallbackQuery):
    pid = call.data.split(":")[2]
    cart_of(call.from_user.id).pop(pid, None)
    text, kb = cart_text_kb(call.from_user.id)
    await show(call, text, kb)
    await call.answer("O'chirildi")


@router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(call: CallbackQuery):
    CARTS[call.from_user.id] = {}
    text, kb = cart_text_kb(call.from_user.id)
    await show(call, text, kb)
    await call.answer("Savat tozalandi")


# ---------------------------------------------------------------- buyurtma berish (majburiy: telefon + manzil)
@router.callback_query(F.data == "cart:checkout")
async def cb_checkout(call: CallbackQuery, state: FSMContext):
    if not cart_of(call.from_user.id):
        return await call.answer("Savat bo'sh", show_alert=True)
    await call.answer()
    await state.set_state(Order.phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )
    await call.message.answer(
        "📱 <b>Telefon raqamingiz</b> (majburiy)\n\n"
        "Operator siz bilan bog'lanishi uchun kerak.\n"
        "Pastdagi tugmani bosing yoki raqamni yozing: <code>+998901234567</code>",
        reply_markup=kb,
    )


@router.message(Order.phone, F.contact)
async def got_contact(message: Message, state: FSMContext):
    phone = valid_phone(message.contact.phone_number) or ("+" + re.sub(r"\D", "", message.contact.phone_number))
    await _ask_address(message, state, phone)


@router.message(Order.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    phone = valid_phone(message.text)
    if not phone:
        return await message.answer(
            "⚠️ Telefon raqami noto'g'ri.\nIltimos, shunday yozing: <code>+998901234567</code> yoki <code>901234567</code>"
        )
    await _ask_address(message, state, phone)


@router.message(Order.phone)
async def phone_other(message: Message):
    await message.answer("📱 Iltimos, telefon raqamingizni yuboring (tugma orqali yoki yozib).")


async def _ask_address(message: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    await state.set_state(Order.address)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_LOCATION, request_location=True)],
            [KeyboardButton(text=BTN_PICKUP)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "📍 <b>Yetkazib berish manzili</b> (majburiy)\n\n"
        "Manzilni yozing (ko'cha, uy, mo'ljal) yoki lokatsiyangizni yuboring.\n"
        "O'zingiz olib ketmoqchi bo'lsangiz, «🏪 O'zim olib ketaman» ni bosing.",
        reply_markup=kb,
    )


async def _go_payment(message: Message, state: FSMContext, address: str, pickup: bool):
    await state.update_data(address=address, pickup=pickup)
    await state.set_state(Order.payment)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CASH), KeyboardButton(text=BTN_CARD)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )
    await message.answer("💳 <b>To'lov usulini tanlang</b>", reply_markup=kb)


@router.message(Order.address, F.location)
async def got_location(message: Message, state: FSMContext):
    loc = message.location
    link = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
    await _go_payment(message, state, f"📍 Lokatsiya: {link}", False)


@router.message(Order.address, F.text == BTN_PICKUP)
async def got_pickup(message: Message, state: FSMContext):
    await _go_payment(message, state, "🏪 Do'kondan olib ketadi", True)


@router.message(Order.address, F.text)
async def got_address_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 8:
        return await message.answer(
            "⚠️ Manzil juda qisqa. Iltimos, ko'cha, uy raqami va mo'ljalni to'liq yozing\n"
            "yoki lokatsiyangizni yuboring."
        )
    await _go_payment(message, state, text, False)


@router.message(Order.address)
async def address_other(message: Message):
    await message.answer("📍 Iltimos, manzilni yozing yoki lokatsiya yuboring.")


@router.message(Order.payment, F.text.in_({BTN_CASH, BTN_CARD}))
async def got_payment(message: Message, state: FSMContext):
    await state.update_data(payment=message.text)
    data = await state.get_data()
    cart = cart_of(message.from_user.id)
    if not cart:
        await state.clear()
        return await message.answer("Savat bo'sh.", reply_markup=main_menu())

    sub = cart_subtotal(cart)
    fee = delivery_fee(sub, data["pickup"])
    lines = ["🧾 <b>Buyurtmangizni tekshiring</b>\n"]
    for pid, q in cart.items():
        p = PRODUCTS[pid]
        lines.append(f"▫️ {esc(p['name'])} — {q} × {money(p['price'])}")
    lines += [
        "",
        f"📱 Telefon: <b>{esc(data['phone'])}</b>",
        f"📍 Manzil: {esc(data['address'])}",
        f"💳 To'lov: {esc(message.text)}",
        "",
        f"Mahsulotlar: {money(sub)}",
        f"Yetkazish: {money(fee) if fee else 'bepul'}",
        f"💰 <b>Jami: {money(sub + fee)}</b>",
    ]
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="order:confirm"))
    b.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="order:cancel"))
    await state.set_state(Order.confirm)
    await message.answer("Ma'lumotlar qabul qilindi 👌", reply_markup=ReplyKeyboardRemove())
    await message.answer("\n".join(lines), reply_markup=b.as_markup())


@router.message(Order.payment)
async def payment_other(message: Message):
    await message.answer("💳 Iltimos, pastdagi tugmalardan birini tanlang.")


@router.callback_query(Order.confirm, F.data == "order:cancel")
async def order_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Buyurtma bekor qilindi. Savatingiz saqlanib qoldi.")
    await call.message.answer("Asosiy menyu 🏠", reply_markup=main_menu())
    await call.answer()


@router.callback_query(Order.confirm, F.data == "order:confirm")
async def order_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    uid = call.from_user.id
    cart = cart_of(uid)
    # majburiy maydonlarni oxirgi marta tekshiramiz
    if not cart or not data.get("phone") or not data.get("address"):
        await state.clear()
        await call.answer("Ma'lumotlar to'liq emas, qaytadan boshlang", show_alert=True)
        return

    sub = cart_subtotal(cart)
    fee = delivery_fee(sub, data["pickup"])
    total = sub + fee
    items = [
        {"id": pid, "name": PRODUCTS[pid]["name"], "qty": q, "price": PRODUCTS[pid]["price"]}
        for pid, q in cart.items()
    ]
    name = call.from_user.full_name
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO orders (user_id, name, phone, address, payment, items,
               subtotal, delivery, total, status, created)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, name, data["phone"], data["address"], data["payment"],
             json.dumps(items, ensure_ascii=False), sub, fee, total, "new",
             datetime.now().strftime("%d.%m.%Y %H:%M")),
        )
        order_id = cur.lastrowid

    CARTS[uid] = {}
    await state.clear()
    await call.message.edit_text(
        f"🎉 <b>Rahmat! Buyurtmangiz qabul qilindi!</b>\n\n"
        f"Buyurtma raqami: <b>№{order_id}</b>\n"
        f"💰 Jami: <b>{money(total)}</b>\n\n"
        "Tez orada operator siz bilan bog'lanadi 📞"
    )
    await call.message.answer("Yana nimadir buyurtma qilasizmi? 😋", reply_markup=main_menu())
    await call.answer()

    # adminga xabar
    if ADMIN_ID:
        lines = [f"🆕 <b>Yangi buyurtma №{order_id}</b>\n"]
        for i in items:
            lines.append(f"▫️ {esc(i['name'])} — {i['qty']} × {money(i['price'])}")
        username = f"@{call.from_user.username}" if call.from_user.username else "—"
        lines += [
            "",
            f"👤 {esc(name)} ({esc(username)})",
            f"📱 {esc(data['phone'])}",
            f"📍 {esc(data['address'])}",
            f"💳 {esc(data['payment'])}",
            "",
            f"Mahsulotlar: {money(sub)}",
            f"Yetkazish: {money(fee) if fee else 'bepul'}",
            f"💰 <b>Jami: {money(total)}</b>",
        ]
        try:
            await bot.send_message(ADMIN_ID, "\n".join(lines), reply_markup=admin_kb(order_id))
        except Exception as e:  # noqa: BLE001
            logging.error("Adminga yuborib bo'lmadi: %s", e)


# ---------------------------------------------------------------- admin
def admin_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"adm:{order_id}:accepted"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm:{order_id}:cancelled"),
    )
    b.row(InlineKeyboardButton(text="🎉 Yetkazildi", callback_data=f"adm:{order_id}:delivered"))
    return b.as_markup()


@router.callback_query(F.data.startswith("adm:"))
async def admin_status(call: CallbackQuery, bot: Bot):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Ruxsat yo'q", show_alert=True)
    _, oid, status = call.data.split(":")
    with db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not row:
            return await call.answer("Buyurtma topilmadi", show_alert=True)
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    label = STATUS_TEXT[status]
    base = (call.message.html_text or "").split("\n\n📌")[0]
    try:
        await call.message.edit_text(f"{base}\n\n📌 Holat: <b>{label}</b>", reply_markup=admin_kb(int(oid)))
    except TelegramBadRequest:
        pass
    try:
        await bot.send_message(row["user_id"], f"📦 Buyurtma <b>№{oid}</b> holati: <b>{label}</b>")
    except Exception:  # noqa: BLE001
        pass
    await call.answer("Yangilandi")


@router.message(Command("orders"))
async def admin_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    with db() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10").fetchall()
    if not rows:
        return await message.answer("Hozircha buyurtmalar yo'q.")
    text = "\n".join(
        f"№{r['id']} · {STATUS_TEXT.get(r['status'])} · {esc(r['name'])} · {esc(r['phone'])} · {money(r['total'])}"
        for r in rows
    )
    await message.answer(f"📋 <b>Oxirgi 10 ta buyurtma</b>\n\n{text}")


@router.message(Command("id"))
async def my_id(message: Message):
    await message.answer(f"Sizning ID: <code>{message.from_user.id}</code>")


# ---------------------------------------------------------------- ishga tushirish
async def start_web():
    """Render kabi hostinglar uchun kichik veb-server (PORT berilgan bo'lsa)."""
    port = int(os.getenv("PORT", "0") or 0)
    if not port:
        return
    from aiohttp import web

    async def health(_request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info("Veb-server %s portda ishga tushdi", port)


async def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylini to'ldiring (README ga qarang).")
    init_db()
    await start_web()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logging.info("Bot ishga tushdi ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
