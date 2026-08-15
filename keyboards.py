from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

VIP_LABELS = {1: "1 kunlik", 7: "1 haftalik", 30: "1 oylik"}


# ==================== FOYDALANUVCHI ====================

def user_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Kabinet"), KeyboardButton(text="Yordam")],
            [KeyboardButton(text="Bot haqida")]
        ],
        resize_keyboard=True
    )


def cabinet_kb(is_vip: bool):
    rows = [[InlineKeyboardButton(text="Hisobni to'ldirish", callback_data="topup_start"),
             InlineKeyboardButton(text="Pul ishlash", callback_data="earn_money")]]
    if is_vip:
        rows.append([InlineKeyboardButton(text="Videolarim", callback_data="my_videos_1")])
    else:
        rows.append([InlineKeyboardButton(text="VIP obuna olish", callback_data="buy_vip"),
                     InlineKeyboardButton(text="Videolarim", callback_data="my_videos_1")])
    rows.append([InlineKeyboardButton(text="Orqaga", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def help_kb(contact_url):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Bog'lanish", url=contact_url)],
        [InlineKeyboardButton(text="Orqaga", callback_data="main_menu")]
    ])


def vip_tariff_kb(prices):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{VIP_LABELS[1]} {prices[1]:,} so'm".replace(",", " "), callback_data="vip_1")],
        [InlineKeyboardButton(text=f"{VIP_LABELS[7]} {prices[7]:,} so'm".replace(",", " "), callback_data="vip_7")],
        [InlineKeyboardButton(text=f"{VIP_LABELS[30]} {prices[30]:,} so'm".replace(",", " "), callback_data="vip_30")],
        [InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet")]
    ])


def rules_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ha", callback_data="rules_yes"),
         InlineKeyboardButton(text="Yo'q", callback_data="rules_no")]
    ])


def video_post_paid_kb(video_id, owned: bool):
    text = "Videoni ko'rish" if owned else "Videoni sotib olish"
    action = "watch_paid" if owned else "buy_video"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"{action}_{video_id}")]
    ])


def video_action_kb(video_id, likes, dislikes, show_quality_switch: bool):
    rows = []
    if show_quality_switch:
        rows.append([InlineKeyboardButton(text="Video sifatini almashtirish", callback_data=f"change_quality_{video_id}")])
    rows.append([
        InlineKeyboardButton(text=f"Yoqdi {likes}", callback_data=f"like_{video_id}"),
        InlineKeyboardButton(text=f"Yoqmadi {dislikes}", callback_data=f"dislike_{video_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quality_select_kb(video_id, qualities, exclude=None):
    builder = InlineKeyboardBuilder()
    for q in qualities:
        if q != exclude:
            builder.button(text=q, callback_data=f"quality_{video_id}_{q}")
    builder.adjust(2)
    if exclude:
        builder.row(InlineKeyboardButton(text="Orqaga", callback_data=f"quality_{video_id}_{exclude}"))
    return builder.as_markup()


def my_videos_kb(videos, page, total_pages):
    builder = InlineKeyboardBuilder()
    start = (page - 1) * 10
    end = start + 10
    for i, video in enumerate(videos[start:end], start=start + 1):
        builder.button(text=f"Video {i}", callback_data=f"watch_paid_{video[0]}")
    builder.adjust(2)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="Oldingi", callback_data=f"my_videos_{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="Keyingi", callback_data=f"my_videos_{page + 1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet"))
    return builder.as_markup()


def mandatory_channels_kb(channels):
    builder = InlineKeyboardBuilder()
    for i, ch in enumerate(channels, 1):
        builder.button(text=f"Kanal {i}", url=ch[1])
    builder.button(text="Tekshirish", callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()


def back_main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Orqaga", callback_data="main_menu")]])


def admin_topup_approve_kb(req_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tasdiqlash", callback_data=f"topup_approve_{req_id}"),
         InlineKeyboardButton(text="Rad etish", callback_data=f"topup_reject_{req_id}")]
    ])


# ==================== ADMIN: ASOSIY ====================

def admin_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ish stoli"), KeyboardButton(text="Sozlamalar")],
            [KeyboardButton(text="Statistika")]
        ],
        resize_keyboard=True
    )


def admin_desk_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Video qo'shish"), KeyboardButton(text="Video o'chirish")],
            [KeyboardButton(text="Reklama jo'natish"), KeyboardButton(text="Gift o'tkazish")],
            [KeyboardButton(text="Bosh menyu")]
        ],
        resize_keyboard=True
    )


def admin_settings_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Kanallar qo'shish"), KeyboardButton(text="Foydalanuvchilar")],
            [KeyboardButton(text="Admin qilish"), KeyboardButton(text="Admindan olish")],
            [KeyboardButton(text="Karta edit"), KeyboardButton(text="Vip narx edit")],
            [KeyboardButton(text="Info edit"), KeyboardButton(text="Admin link edit")],
            [KeyboardButton(text="Bosh menyu")]
        ],
        resize_keyboard=True
    )


def confirm_kb(yes_cb, no_cb):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ha", callback_data=yes_cb),
         InlineKeyboardButton(text="Yo'q", callback_data=no_cb)]
    ])


def orqaga_kb(callback_data: str):
    """Ko'p bosqichli jarayonlarning istalgan qadamida ishlatiladigan universal Orqaga tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Orqaga", callback_data=callback_data)]
    ])


# ---------- VIDEO QO'SHISH ----------

def video_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Pullik", callback_data="addvideo_paid"),
         InlineKeyboardButton(text="Bepul", callback_data="addvideo_free")],
        [InlineKeyboardButton(text="Orqaga", callback_data="cancel_to_desk")]
    ])


def admin_quality_select_kb(added_qualities):
    all_q = ["360p", "480p", "720p", "1080p"]
    builder = InlineKeyboardBuilder()
    for q in all_q:
        if q not in added_qualities:
            builder.button(text=q, callback_data=f"addq_{q}")
    if added_qualities:
        builder.button(text="Bo'ldi", callback_data="addq_done")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Orqaga", callback_data="cancel_to_desk"))
    return builder.as_markup()


# ---------- REKLAMA ----------

def broadcast_content_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugmalar qo'shish", callback_data="bc_add_buttons")],
        [InlineKeyboardButton(text="Reklama tayyor", callback_data="bc_ready")],
        [InlineKeyboardButton(text="Reklamani to'xtatish", callback_data="bc_cancel")]
    ])


def broadcast_content_with_buttons_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugmalarni o'chirish", callback_data="bc_clear_buttons")],
        [InlineKeyboardButton(text="Reklama tayyor", callback_data="bc_ready")],
        [InlineKeyboardButton(text="Reklamani to'xtatish", callback_data="bc_cancel")]
    ])


def broadcast_url_buttons_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Orqaga", callback_data="bc_back_to_content")]])


def broadcast_target_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VIP obunachilarga", callback_data="broadcast_vip")],
        [InlineKeyboardButton(text="Oddiy obunachilarga", callback_data="broadcast_regular")],
        [InlineKeyboardButton(text="Barcha obunachilarga", callback_data="broadcast_all")]
    ])


# ---------- GIFT ----------

def gift_tariff_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 kunlik", callback_data="gift_days_1")],
        [InlineKeyboardButton(text="1 haftalik", callback_data="gift_days_7")],
        [InlineKeyboardButton(text="1 oylik", callback_data="gift_days_30")],
        [InlineKeyboardButton(text="Orqaga", callback_data="cancel_to_desk")]
    ])


# ---------- SOZLAMALAR: KANALLAR ----------

def channels_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Majburiy kanal qo'shish", callback_data="ch_add_mandatory")],
        [InlineKeyboardButton(text="Reklama kanal qo'shish", callback_data="ch_add_ad")],
        [InlineKeyboardButton(text="Kanallarni o'chirish", callback_data="ch_delete_menu")],
        [InlineKeyboardButton(text="Orqaga", callback_data="cancel_to_settings")]
    ])


def ad_channel_video_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Pullik", callback_data="adch_type_paid"),
         InlineKeyboardButton(text="Bepul", callback_data="adch_type_free")],
        [InlineKeyboardButton(text="Orqaga", callback_data="back_channels_menu")]
    ])


def delete_channels_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Majburiy kanallar", callback_data="delch_mandatory")],
        [InlineKeyboardButton(text="Reklama kanallar", callback_data="delch_ad")],
        [InlineKeyboardButton(text="Orqaga", callback_data="back_channels_menu")]
    ])


def mandatory_channels_delete_kb(channels):
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.button(text=ch[1] or str(ch[0]), callback_data=f"delmch_{ch[0]}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Orqaga", callback_data="back_delete_channels_type"))
    return builder.as_markup()


def ad_channels_delete_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Pullik", callback_data="deladch_paid")],
        [InlineKeyboardButton(text="Bepul", callback_data="deladch_free")],
        [InlineKeyboardButton(text="Orqaga", callback_data="back_delete_channels_type")]
    ])


# ---------- SOZLAMALAR: VIP NARX ----------

def vip_price_tariff_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 kunlik", callback_data="vipprice_1")],
        [InlineKeyboardButton(text="1 haftalik", callback_data="vipprice_7")],
        [InlineKeyboardButton(text="1 oylik", callback_data="vipprice_30")],
        [InlineKeyboardButton(text="Orqaga", callback_data="cancel_to_settings")]
    ])


# ---------- SOZLAMALAR: FOYDALANUVCHILAR ----------

def user_profile_kb(user_id, is_vip, is_blocked):
    rows = [
        [InlineKeyboardButton(text="Pul qo'shish", callback_data=f"uadd_{user_id}"),
         InlineKeyboardButton(text="Pul ayirish", callback_data=f"usub_{user_id}")],
    ]
    if is_vip:
        rows.append([InlineKeyboardButton(text="Vipini olish", callback_data=f"uviprevoke_{user_id}")])
    else:
        rows.append([InlineKeyboardButton(text="Vip berish", callback_data=f"uvipgive_{user_id}")])
    if is_blocked:
        rows.append([InlineKeyboardButton(text="Blockdan chiqarish", callback_data=f"uunblock_{user_id}")])
    else:
        rows.append([InlineKeyboardButton(text="Blocklash", callback_data=f"ublock_{user_id}")])
    rows.append([InlineKeyboardButton(text="Xabar yuborish", callback_data=f"umsg_{user_id}")])
    rows.append([InlineKeyboardButton(text="Orqaga", callback_data="cancel_to_settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_vip_give_tariff_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 kunlik", callback_data=f"uvipset_{user_id}_1")],
        [InlineKeyboardButton(text="1 haftalik", callback_data=f"uvipset_{user_id}_7")],
        [InlineKeyboardButton(text="1 oylik", callback_data=f"uvipset_{user_id}_30")],
        [InlineKeyboardButton(text="Orqaga", callback_data=f"back_profile_{user_id}")]
    ])


# ---------- SOZLAMALAR: ADMINLARNI BOSHQARISH ----------

PERMISSION_LABELS = {
    "can_edit": "Edit imkoniyatlari",
    "can_confirm_payments": "Chek tasdiqlash",
    "can_manage_admins": "Admin qilish/olish",
    "can_view_users": "Foydalanuvchilarni ko'rish",
}


def admin_permissions_kb(perms: dict):
    builder = InlineKeyboardBuilder()
    for key, label in PERMISSION_LABELS.items():
        mark = "\u2705\ufe0f" if perms.get(key) else "\u274c\ufe0f"
        builder.button(text=f"{mark} {label}", callback_data=f"perm_{key}")
    builder.button(text="Bo'ldi", callback_data="perm_done")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Orqaga", callback_data="perm_cancel"))
    return builder.as_markup()
