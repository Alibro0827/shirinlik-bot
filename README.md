# 🍰 Shirinlik do'koni Telegram boti

Chiroyli menyu, savat va buyurtma berish. Telefon raqam va manzil **majburiy**:
ular to'g'ri kiritilmaguncha buyurtma tasdiqlanmaydi.

## Imkoniyatlar
- 🍰 Kategoriyalar bo'yicha menyu (tortlar, pirojniylar, pechenye, konfetlar)
- ➕➖ Mahsulot sonini tanlash, 🛒 savat, o'chirish va tozalash
- 📱 Telefon raqam (tugma orqali yoki yozib, formati tekshiriladi) — majburiy
- 📍 Manzil (matn yoki lokatsiya) yoki olib ketish — majburiy
- 💳 To'lov usuli, buyurtmani tasdiqlash
- 🔔 Har bir buyurtma adminga keladi, admin holatini o'zgartiradi (qabul / yetkazildi / bekor) va mijozga xabar boradi
- 📦 Mijoz o'z buyurtmalarini ko'ra oladi

## O'rnatish
1. Python 3.10+ o'rnatilgan bo'lsin.
2. Telegramda **@BotFather** ga `/newbot` yozing, nom bering va **token** oling.
3. Kutubxonalarni o'rnating:
   ```
   pip install -r requirements.txt
   ```
4. `.env.example` faylini `.env` deb nusxalang va tokenni yozing:
   ```
   BOT_TOKEN=123456:ABC...
   ADMIN_ID=123456789
   ```
   `ADMIN_ID` — sizning Telegram ID'ngiz. Avval `ADMIN_ID=0` bilan ishga tushirib, botga `/id` yozsangiz ID'ni ko'rsatadi, keyin `.env` ga yozib botni qayta ishga tushiring.
5. Ishga tushiring:
   ```
   python bot.py
   ```

## Moslash
`products.py` faylida do'kon nomi, telefon, ish vaqti, yetkazish narxi, kategoriyalar va mahsulotlar (nom, narx, tavsif) bor. Mahsulotga rasm qo'shish uchun `"photo"` ga rasm havolasini (`https://...`) yozing.

## Buyruqlar
- Mijoz: `/start`, `/menu`, `/cart`
- Admin: `/orders` (oxirgi 10 ta buyurtma), `/id`

## Eslatma
Savat xotirada saqlanadi (bot qayta ishga tushsa tozalanadi). Buyurtmalar `orders.db` (SQLite) faylida saqlanadi.
Botni doim ishlatish uchun uni serverga (VPS) joylashtiring.
