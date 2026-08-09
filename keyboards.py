from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def user_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Kabinet"), KeyboardButton(text="Yordam")],
            [KeyboardButton(text="Bot haqida")]
        ],
        resize_keyboard=True
    )

def admin_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Video qo‘shish"), KeyboardButton(text="Video o'chirish")],
            [KeyboardButton(text="Statistika"), KeyboardButton(text="Sozlamalar")]
        ],
        resize_keyboard=True
    )

def cabinet_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Vip sotib olish", callback_data="buy_vip")],
            [InlineKeyboardButton(text="Sotib olingan videolar", callback_data="my_videos_1")]
        ]
    )

def vip_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1 kunlik 5 000 so'm", callback_data="vip_1")],
            [InlineKeyboardButton(text="1 haftalik 15 000 so'm", callback_data="vip_7")],
            [InlineKeyboardButton(text="1 oylik 25 000 so'm", callback_data="vip_30")],
            [InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet")]
        ]
    )

def payment_done_kb(item_type, item_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="To'lov qildim", callback_data=f"paid_{item_type}_{item_id}")]
        ]
    )

def admin_approve_kb(user_id, item_type, item_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tasdiqlash", callback_data=f"approve_{user_id}_{item_type}_{item_id}")],
            [InlineKeyboardButton(text="Rad qilish", callback_data=f"reject_{user_id}_{item_type}_{item_id}")]
        ]
    )

def video_post_kb(video_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Video sifatini tanlash", callback_data=f"choose_quality_{video_id}")],
            [InlineKeyboardButton(text="Videoni ko'rish", callback_data=f"watch_video_{video_id}")]
        ]
    )

def quality_select_kb(video_id, qualities, exclude=None):
    builder = InlineKeyboardBuilder()
    for q in qualities:
        if q != exclude:
            builder.button(text=q, callback_data=f"quality_{video_id}_{q}")
    builder.adjust(2)
    return builder.as_markup()

def admin_quality_select_kb(added_qualities):
    all_q = ["360p", "480p", "720p", "1080p"]
    builder = InlineKeyboardBuilder()
    for q in all_q:
        if q not in added_qualities:
            builder.button(text=q, callback_data=f"addq_{q}")
    if added_qualities:
        builder.button(text="Bo'ldi", callback_data="addq_done")
    builder.adjust(2)
    return builder.as_markup()

def watch_video_buy_kb(video_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Videoni sotib olish", callback_data=f"buy_video_{video_id}")],
            [InlineKeyboardButton(text="Vip sotib olish", callback_data="buy_vip")]
        ]
    )

def video_action_kb(video_id, likes, dislikes):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Sifatini almashtirish", callback_data=f"change_quality_{video_id}")],
            [InlineKeyboardButton(text=f"👍🏻 {likes}", callback_data=f"like_{video_id}"), 
             InlineKeyboardButton(text=f"👎🏻 {dislikes}", callback_data=f"dislike_{video_id}")],
            [InlineKeyboardButton(text="Bosh menyu", callback_data="main_menu")]
        ]
    )

def admin_settings_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Kanallar", callback_data="set_channels")],
            [InlineKeyboardButton(text="Karta raqam", callback_data="set_card")],
            [InlineKeyboardButton(text="Admin havolasi", callback_data="set_adminlink")],
            [InlineKeyboardButton(text="Orqaga", callback_data="admin_back")]
        ]
    )

def admin_channels_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Baza kanal", callback_data="set_basechannel")],
            [InlineKeyboardButton(text="Majburiy kanal", callback_data="set_mandatorychannel")],
            [InlineKeyboardButton(text="Kanallarni o'chirish", callback_data="del_channels")],
            [InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]
        ]
    )

def mandatory_channels_kb(channels):
    builder = InlineKeyboardBuilder()
    for i, ch in enumerate(channels, 1):
        builder.button(text=f"Kanal {i}", url=ch[1])
    builder.button(text="Tekshirish", callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()

def base_channel_kb(url):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Kodlarni olish", url=url)]])

def confirm_kb(action_data):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ha", callback_data=f"yes_{action_data}"), InlineKeyboardButton(text="Yo'q", callback_data="no_action")]
        ]
    )

def my_videos_kb(videos, page, total_pages):
    builder = InlineKeyboardBuilder()
    start = (page - 1) * 10
    end = start + 10
    
    for i, video in enumerate(videos[start:end], start=start+1):
        builder.button(text=f"Video {i}", callback_data=f"watch_video_{video[0]}")
    builder.adjust(2)
    
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"my_videos_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="Oldinga ➡️", callback_data=f"my_videos_{page+1}"))
        
    if nav:
        builder.row(*nav)
        
    return builder.as_markup()
