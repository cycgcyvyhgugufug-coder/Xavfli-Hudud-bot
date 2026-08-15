import os

# BOT_TOKEN va ADMIN_ID kod ichida saqlanmaydi.
# Railway.com da: Project -> Variables bo'limiga quyidagilarni qo'shing:
#   BOT_TOKEN = <BotFather bergan token>
#   ADMIN_ID  = <sizning shaxsiy Telegram ID raqamingiz>
#
# Lokal (kompyuteringizda) ishga tushirish uchun loyihaning ildizida
# ".env" fayl yarating va ichiga shu ikkala qatorni yozing.

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi! Railway -> Variables bo'limiga BOT_TOKEN qo'shing "
        "(yoki lokal ishlatayotgan bo'lsangiz .env faylga yozing)."
    )

if not ADMIN_ID_RAW:
    raise RuntimeError(
        "ADMIN_ID topilmadi! Railway -> Variables bo'limiga ADMIN_ID qo'shing "
        "(yoki lokal ishlatayotgan bo'lsangiz .env faylga yozing)."
    )

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    raise RuntimeError("ADMIN_ID faqat raqamlardan iborat bo'lishi kerak.")

# Referal bonusi (har bir yangi taklif qilingan do'st uchun, so'mda)
REFERRAL_BONUS = 500

# Bepul foydalanuvchi (default) uchun ish stolidagi standart huquqlar.
# Bular ADMIN_ID uchun emas, faqat ikkinchi darajali (qo'shimcha) adminlar uchun ishlaydi.
DEFAULT_ADMIN_PERMISSIONS = {
    "can_edit": 0,             # Karta / VIP narx / Info / Admin link edit
    "can_confirm_payments": 0, # Hisob to'ldirish cheklarini tasdiqlash/rad etish
    "can_manage_admins": 0,    # Admin qilish / admindan olish
    "can_view_users": 0,       # Sozlamalar -> Foydalanuvchilar bo'limi
}
