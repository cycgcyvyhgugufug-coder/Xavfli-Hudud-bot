import datetime
from config import ADMIN_ID


def fmt_money(amount) -> str:
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return str(amount)
    return f"{amount:,}".replace(",", " ") + " so'm"


def display_username(username):
    return f"@{username}" if username else "Mavjud emas"


def build_contact_url(admin_link: str) -> str:
    admin_link = (admin_link or "").strip()
    if admin_link.startswith(("http://", "https://")):
        return admin_link
    cleaned = (
        admin_link
        .replace("https://t.me/", "")
        .replace("http://t.me/", "")
        .replace("t.me/", "")
        .lstrip("@")
        .strip("/")
    )
    return f"https://t.me/{cleaned}"


async def build_referral_link(bot, user_id: int) -> str:
    me = await bot.get_me()
    return f"https://t.me/{me.username}?start=ref{user_id}"


async def is_admin(db, user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    admin_row = await db.get_admin(user_id)
    return admin_row is not None


async def get_permissions(db, user_id: int) -> dict:
    """ADMIN_ID uchun har doim to'liq huquq. Boshqa adminlar uchun DB'dagi qiymatlar."""
    if user_id == ADMIN_ID:
        return {"can_edit": True, "can_confirm_payments": True, "can_manage_admins": True, "can_view_users": True}
    row = await db.get_admin(user_id)
    if not row:
        return {"can_edit": False, "can_confirm_payments": False, "can_manage_admins": False, "can_view_users": False}
    # admins jadval tuzilishi: user_id, can_edit, can_confirm_payments, can_manage_admins, can_view_users, added_by, created_at
    return {
        "can_edit": bool(row[1]),
        "can_confirm_payments": bool(row[2]),
        "can_manage_admins": bool(row[3]),
        "can_view_users": bool(row[4]),
    }


def vip_until_str(vip_until_raw) -> str:
    if not vip_until_raw:
        return "-"
    try:
        dt = datetime.datetime.fromisoformat(str(vip_until_raw))
    except (TypeError, ValueError):
        return "-"
    return dt.strftime("%d.%m.%Y")


NO_PERMISSION_EDIT = "Afsuski sizni adminlik darajangiz buni o'zgartirishga yetmaydi."
NO_PERMISSION_USERS = "Afsuski sizni adminlik darajangiz bu ma'lumotlarni olishga yetmaydi."
NO_PERMISSION_ADMIN_MANAGE = "Afsuski sizni adminlik darajangiz admin tayinlashga ( yoxud adminlikdan bekor qilishga) yetmaydi."
