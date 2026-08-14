
from aiogram.types import ReplyKeyboardMarkup,KeyboardButton,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Kabinet"),KeyboardButton(text="Yordam")],
        [KeyboardButton(text="Bot haqida")]
    ],resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Video qo'shish"),KeyboardButton(text="Video o'chirish")],
        [KeyboardButton(text="Reklama"),KeyboardButton(text="Hadyalar")],
        [KeyboardButton(text="Statistika"),KeyboardButton(text="Sozlamalar")]
    ],resize_keyboard=True)

def cabinet_kb(vip):
    rows=[]
    if not vip:
        rows.append([InlineKeyboardButton(text="VIP obuna olish",callback_data="vip_menu")])
    rows.append([InlineKeyboardButton(text="Videolarim",callback_data="my_1")])
    rows.append([InlineKeyboardButton(text="Hisobni to'ldirish",callback_data="balance")])
    rows.append([InlineKeyboardButton(text="Pul ishlash",callback_data="referral")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def vip_kb(tariffs):
    return InlineKeyboardMarkup(inline_keyboard=[
        *[[InlineKeyboardButton(text=f"{t['name']} {t['price']:,} so'm".replace(","," "),callback_data=f"vip:{t['days']}")] for t in tariffs],
        [InlineKeyboardButton(text="Orqaga",callback_data="cabinet")]
    ])

def back(cb="cabinet"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Orqaga",callback_data=cb)]])

def pay(cb):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="To'lov qildim",callback_data=cb)]])

def admin_payment(user_id,kind,item):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Tasdiqlash",callback_data=f"payok:{user_id}:{kind}:{item}"),
        InlineKeyboardButton(text="Rad qilish",callback_data=f"payno:{user_id}:{kind}:{item}")
    ]])

def video_post(vid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sifatni tanlash",callback_data=f"qmenu:{vid}")],
        [InlineKeyboardButton(text="Videoni ko'rish",callback_data=f"watch:{vid}")]
    ])

def qualities(vid,qs,exclude=None):
    b=InlineKeyboardBuilder()
    for q in qs:
        if q!=exclude: b.button(text=q,callback_data=f"quality:{vid}:{q}")
    b.adjust(2)
    return b.as_markup()

def watch_actions(vid,likes,dislikes):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Sifatni almashtirish",callback_data=f"changeq:{vid}")],
        [InlineKeyboardButton(text="👍🏻",callback_data=f"like:{vid}"),InlineKeyboardButton(text="👎🏻",callback_data=f"dislike:{vid}")]
    ])

def buy_video(vid,vip=True):
    rows=[[InlineKeyboardButton(text="Videoni sotib olish",callback_data=f"buy:{vid}")]]
    if vip: rows.append([InlineKeyboardButton(text="VIP obuna olish",callback_data="vip_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def my_videos(videos,page):
    total=(len(videos)+9)//10
    b=InlineKeyboardBuilder()
    start=(page-1)*10
    for i,v in enumerate(videos[start:start+10],start=start+1):
        b.button(text=f"Video {i}",callback_data=f"myvideo:{v['id']}")
    b.adjust(2)
    nav=[]
    if page>1: nav.append(InlineKeyboardButton(text="Orqaga",callback_data=f"my:{page-1}"))
    if page<total: nav.append(InlineKeyboardButton(text="Keyingi",callback_data=f"my:{page+1}"))
    if nav: b.row(*nav)
    return b.as_markup()

def mandatory(channels):
    b=InlineKeyboardBuilder()
    for c in channels: b.button(text=c["title"] or "Kanal",url=c["url"])
    b.button(text="Tekshirish",callback_data="check")
    b.adjust(1)
    return b.as_markup()

def admin_settings():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanallar",callback_data="channels")],
        [InlineKeyboardButton(text="Tariflar",callback_data="tariffs")],
        [InlineKeyboardButton(text="Karta raqam",callback_data="card")],
        [InlineKeyboardButton(text="Admin havolasi",callback_data="adminlink")],
        [InlineKeyboardButton(text="Info almashtirish",callback_data="info")],
        [InlineKeyboardButton(text="Adminlar",callback_data="admins")],
        [InlineKeyboardButton(text="Orqaga",callback_data="admin")]
    ])

def channels():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanal qo'shish",callback_data="channel_add")],
        [InlineKeyboardButton(text="Kanallarni o'chirish",callback_data="channel_del")],
        [InlineKeyboardButton(text="Orqaga",callback_data="settings")]
    ])

def tariffs(ts):
    return InlineKeyboardMarkup(inline_keyboard=[
        *[[InlineKeyboardButton(text=f"{t['name']} ({t['price']:,} so'm)".replace(","," "),callback_data=f"edit_tariff:{t['days']}")] for t in ts],
        [InlineKeyboardButton(text="Orqaga",callback_data="settings")]
    ])

def admins():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Admin qo'shish",callback_data="admin_add")],
        [InlineKeyboardButton(text="Adminni bekor qilish",callback_data="admin_del")],
        [InlineKeyboardButton(text="Orqaga",callback_data="settings")]
    ])

def broadcast_editor(has_buttons=False):
    rows=[]
    if has_buttons: rows.append([InlineKeyboardButton(text="Tugmalarni o'chirish",callback_data="broadcast_clear")])
    rows.append([InlineKeyboardButton(text="Tugmalar qo'shish",callback_data="broadcast_buttons")])
    rows.append([InlineKeyboardButton(text="Tayyor bo'ldi",callback_data="broadcast_done")])
    rows.append([InlineKeyboardButton(text="Bekor qilish",callback_data="broadcast_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def broadcast_targets():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oddiy obunachilar",callback_data="target:regular")],
        [InlineKeyboardButton(text="VIP obunachilar",callback_data="target:vip")],
        [InlineKeyboardButton(text="Barchaga",callback_data="target:all")]
    ])

def gifts():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ID orqali",callback_data="gift_id")],
        [InlineKeyboardButton(text="Random",callback_data="gift_random")],
        [InlineKeyboardButton(text="VIPni qaytarish",callback_data="revoke")],
        [InlineKeyboardButton(text="Orqaga",callback_data="admin")]
    ])

def gift_tariffs(ts,prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        *[[InlineKeyboardButton(text=f"{t['name']} {t['price']:,} so'm".replace(","," "),callback_data=f"{prefix}:{t['days']}")] for t in ts]
    ])

def yesno(yes,no):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ha",callback_data=yes),
        InlineKeyboardButton(text="Yo'q",callback_data=no)
    ]])

def claim(gid):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Sovg'ani olish",callback_data=f"claim:{gid}")]])
