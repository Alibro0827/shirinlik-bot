# Mahsulotlarni shu yerda o'zgartirasiz: nom, narx, tavsif.
# "photo" - ixtiyoriy. Rasm havolasi (https://...) yoki Telegram file_id qo'ysangiz bo'ladi.
# Narxlar so'mda.

SHOP_NAME = "Shirin Dunyo"
CURRENCY = "so'm"
DELIVERY_FEE = 15000          # yetkazib berish narxi
FREE_DELIVERY_FROM = 300000   # shu summadan oshsa yetkazish bepul
WORK_HOURS = "09:00 - 22:00"
CONTACT_PHONE = "+998 90 123 45 67"

CATEGORIES = {
    "cakes": {"title": "🎂 Tortlar", "items": [
        {"id": "c1", "name": "Napoleon torti", "price": 180000,
         "desc": "Qatlamli xamir va nozik qaymoqli krem. 1 kg.", "photo": None},
        {"id": "c2", "name": "Medovik torti", "price": 170000,
         "desc": "Asalli, yumshoq va mazali klassik tort. 1 kg.", "photo": None},
        {"id": "c3", "name": "Shokoladli tort", "price": 210000,
         "desc": "Boy shokolad kremi va yumshoq biskvit. 1 kg.", "photo": None},
    ]},
    "pastry": {"title": "🥐 Pirojniylar", "items": [
        {"id": "p1", "name": "Eklyer", "price": 15000,
         "desc": "Vanilli krem bilan to'ldirilgan, shokolad bilan qoplangan.", "photo": None},
        {"id": "p2", "name": "Tiramisu", "price": 28000,
         "desc": "Italyancha kofeli desert, 1 porsiya.", "photo": None},
        {"id": "p3", "name": "Cheesecake", "price": 30000,
         "desc": "Nozik tvorogli cheesecake, 1 porsiya.", "photo": None},
    ]},
    "cookies": {"title": "🍪 Pechenyelar", "items": [
        {"id": "k1", "name": "Shokoladli pechenye", "price": 60000,
         "desc": "Shokolad bo'laklari bilan, 500 g.", "photo": None},
        {"id": "k2", "name": "Yong'oqli pechenye", "price": 65000,
         "desc": "Grek yong'og'i bilan, 500 g.", "photo": None},
    ]},
    "sweets": {"title": "🍬 Konfet va shirinliklar", "items": [
        {"id": "s1", "name": "Sovg'a to'plami", "price": 120000,
         "desc": "Turli konfetlar, chiroyli qutida. Sovg'a uchun ideal.", "photo": None},
        {"id": "s2", "name": "Sharq shirinliklari", "price": 95000,
         "desc": "Halva, navvot va quruq mevalar assortisi, 1 kg.", "photo": None},
    ]},
}

PRODUCTS = {item["id"]: item for cat in CATEGORIES.values() for item in cat["items"]}
