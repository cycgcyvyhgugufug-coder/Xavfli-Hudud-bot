import logging
import math
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext

import keyboards as kb
from states import TopUp, RejectReason
from config import ADMIN_ID, REFERRAL_BONUS
from utils import fmt_money, display_username, build_contact_url, build_referral_link, vip_until_str, is_admin, get_permissions
from db import Database

router = Router()


# ==================== YORDAMCHI FUNKSIYALAR ====================

async def check_sub(bot: Bot, db: Database, user_id: int) -> bool:
    channels = await db.get_mandatory_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch[0], user_id)
            if member.status in ['left', 'kicked', 'restricted']:
                return False
        except Exception:
            logging.exception("Majburiy obuna tekshiruvida xato: channel=%s user=%s", ch[0], user_id)
            return False
    return True


async def send_welcome(message: types.Message):
    await message.answer(
        f"Salom {message.from_user.first_name}, Xavfli Hududga xush kelibsiz!\n\n"
        "Ko'rmoqchi bo'lgan videongizni kodini jo'nating yoki o'zingizga kerak "
        "bo'lgan bo'limlardan birini tanlang!",
        reply_markup=kb.user_main_kb()
    )


async def notify_admin_new_user(bot: Bot, name, username, user_id, referrer_id=None):
    uname = display_username(username)
    if referrer_id:
        text = (
            f"Referral orqali yangi foydalanuvchi\n\n"
            f"Ismi: {name}\n"
            f"Useri: {uname}\n"
            f"IDsi: {user_id}\n"
            f"Taklif qiluvchi: {referrer_id}"
        )
    else:
        text = (
            f"Yangi foydalanuvchi\n\n"
            f"Ismi: {name}\n"
            f"Useri: {uname}\n"
            f"IDsi: {user_id}"
        )
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logging.exception("Adminga yangi foydalanuvchi haqida xabar yuborilmadi")


# ==================== /start ====================

@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext, command: CommandObject, db: Database, bot: Bot):
    await state.clear()
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        await message.answer(
            "Assalomu alekum xo'jayin hush kelibsiz bugun nima qilamiz?",
            reply_markup=kb.admin_main_kb()
        )
        return

    if await is_admin(db, user_id):
        await message.answer(
            "Assalomu alekum xo'jayin hush kelibsiz bugun nima qilamiz?",
            reply_markup=kb.admin_main_kb()
        )
        return

    referrer_id = None
    payload = command.args
    if payload and payload.startswith("ref"):
        try:
            candidate = int(payload[3:])
            if candidate != user_id and await db.get_user(candidate):
                referrer_id = candidate
        except ValueError:
            referrer_id = None

    is_new, user_row = await db.add_user(
        user_id, message.from_user.first_name, message.from_user.username, referred_by=referrer_id
    )

    if is_new:
        await notify_admin_new_user(bot, message.from_user.first_name, message.from_user.username, user_id, referrer_id)
        if referrer_id:
            ok, new_balance = await db.change_balance(
                referrer_id, REFERRAL_BONUS, "referral_bonus", f"Referral: {user_id}"
            )
            if ok:
                try:
                    await bot.send_message(
                        referrer_id,
                        "Sizning havolangiz orqali yangi do'st qo'shildi.\n"
                        f"Do'stingiz IDsi: {user_id}\n"
                        f"Hisobingizga {fmt_money(REFERRAL_BONUS)} qo'shildi.\n"
                        f"Balans: {fmt_money(new_balance)}"
                    )
                except Exception:
                    logging.warning("Referal egasiga xabar yuborilmadi: %s", referrer_id)

    if await db.is_blocked(user_id):
        from middlewares import BLOCKED_TEXT, blocked_kb
        await message.answer(BLOCKED_TEXT, reply_markup=blocked_kb())
        return

    if not await check_sub(bot, db, user_id):
        channels = await db.get_mandatory_channels()
        await message.answer(
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!",
            reply_markup=kb.mandatory_channels_kb(channels)
        )
        return

    await send_welcome(message)


@router.callback_query(F.data == "check_sub")
async def check_sub_handler(call: types.CallbackQuery, db: Database, bot: Bot):
    if await check_sub(bot, db, call.from_user.id):
        await call.message.delete()
        await send_welcome(call.message)
    else:
        await call.answer("Hali barcha kanallarga obuna bo'lmapsiz!", show_alert=True)


@router.message(Command("data"))
async def get_data_handler(message: types.Message, db: Database):
    if message.from_user.id != ADMIN_ID:
        return
    doc = types.FSInputFile(db.db_path)
    await message.answer_document(doc, caption="Botning ma'lumotlar bazasi")


@router.callback_query(F.data == "main_menu")
async def main_menu_handler(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("Bosh menyu", reply_markup=kb.user_main_kb())


# ==================== KABINET ====================

@router.message(F.text == "Kabinet")
async def cabinet_handler(message: types.Message, db: Database):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi. Iltimos /start ni bosing.")
        return

    is_vip = await db.is_vip(user_id)
    friends = await db.get_referral_count(user_id)
    balance = user[3]

    text = (
        f"Ism: {user[1]}\n"
        f"User: {display_username(user[2])}\n"
        f"ID: {user[0]}\n"
        f"Hisobim: {fmt_money(balance)}\n"
        f"Holatim: {'VIP obunachi' if is_vip else 'Oddiy obunachi'}\n"
    )
    if is_vip:
        text += f"Muddati: {vip_until_str(user[4])} da tugaydi\n"
    text += f"Do'stlarim: {friends} ta"

    await message.answer(text, reply_markup=kb.cabinet_kb(is_vip))


@router.callback_query(F.data == "back_cabinet")
async def back_cabinet_handler(call: types.CallbackQuery, db: Database):
    user_id = call.from_user.id
    user = await db.get_user(user_id)
    is_vip = await db.is_vip(user_id)
    friends = await db.get_referral_count(user_id)
    text = (
        f"Ism: {user[1]}\n"
        f"User: {display_username(user[2])}\n"
        f"ID: {user[0]}\n"
        f"Hisobim: {fmt_money(user[3])}\n"
        f"Holatim: {'VIP obunachi' if is_vip else 'Oddiy obunachi'}\n"
    )
    if is_vip:
        text += f"Muddati: {vip_until_str(user[4])} da tugaydi\n"
    text += f"Do'stlarim: {friends} ta"
    await call.message.edit_text(text, reply_markup=kb.cabinet_kb(is_vip))


# ==================== YORDAM / BOT HAQIDA ====================

@router.message(F.text == "Yordam")
async def help_handler(message: types.Message, db: Database):
    admin_link = await db.get_setting("admin_link") or "@admin"
    contact_url = build_contact_url(admin_link)
    await message.answer(
        "Agar sizda muammolar yoki qanaqadur savollar paydo bo'lgan bo'lsa "
        "admin bilan bog'lanishingiz mumkin",
        reply_markup=kb.help_kb(contact_url)
    )


@router.message(F.text == "Bot haqida")
async def about_handler(message: types.Message, db: Database):
    text = await db.get_setting("bot_info")
    await message.answer(text or "Ma'lumot topilmadi.")


# ==================== HISOBNI TO'LDIRISH ====================

@router.callback_query(F.data == "topup_start")
async def topup_start_handler(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Hisobingizni qanchaga to'ldirmoqchisiz?\nSummani yozing!\n\nMasalan 5000",
        reply_markup=kb.orqaga_kb("topup_cancel")
    )
    await state.set_state(TopUp.waiting_for_amount)


@router.callback_query(F.data == "topup_cancel")
async def topup_cancel_handler(call: types.CallbackQuery, state: FSMContext, db: Database):
    await state.clear()
    await back_cabinet_handler(call, db)


@router.message(TopUp.waiting_for_amount, F.text)
async def topup_amount_handler(message: types.Message, state: FSMContext, db: Database):
    raw = message.text.strip().replace(" ", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer(
            "Iltimos, summani faqat musbat raqam bilan kiriting. Masalan: 5000",
            reply_markup=kb.orqaga_kb("topup_cancel")
        )
        return
    amount = int(raw)
    card = await db.get_setting("card")
    await state.update_data(amount=amount)
    await message.answer(
        f"Quyidagi karta raqamiga kerakli summani o'tkazing!\n\n"
        f"Summa: {fmt_money(amount)}\n"
        f"Karta: {card}\n\n"
        "To'lovni amalga oshirgach, to'lov chek rasmini jo'nating!",
        reply_markup=kb.orqaga_kb("topup_cancel")
    )
    await state.set_state(TopUp.waiting_for_receipt)


@router.message(TopUp.waiting_for_receipt, F.photo)
async def topup_receipt_handler(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount")
    user_id = message.from_user.id

    req_id = await db.create_balance_request(user_id, amount, message.photo[-1].file_id)

    caption = (
        "Hisobni to'ldirish so'rovi\n\n"
        f"Ismi: {message.from_user.first_name}\n"
        f"User: {display_username(message.from_user.username)}\n"
        f"ID: {user_id}\n"
        f"Summa: {fmt_money(amount)}"
    )

    recipients = {ADMIN_ID, *(await db.get_payment_confirm_admins())}
    for admin_id in recipients:
        try:
            await bot.send_photo(
                admin_id, message.photo[-1].file_id,
                caption=caption,
                reply_markup=kb.admin_topup_approve_kb(req_id)
            )
        except Exception:
            logging.warning("Balans so'rovi adminga yuborilmadi: %s", admin_id)

    await message.answer(
        "To'lov chekingiz adminga yuborildi.\n"
        f"Admin to'lovni tasdiqlaganidan so'ng, {fmt_money(amount)} hisobingizga qo'shiladi."
    )
    await state.clear()


@router.callback_query(F.data.startswith("topup_approve_"))
async def topup_approve_handler(call: types.CallbackQuery, db: Database, bot: Bot):
    if not await is_admin(db, call.from_user.id):
        return
    perms = await get_permissions(db, call.from_user.id)
    if not perms["can_confirm_payments"]:
        await call.answer("Afsuski sizni adminlik darajangiz to'lovlarni tasdiqlashga yetmaydi.", show_alert=True)
        return
    req_id = int(call.data.split("_")[2])
    req = await db.get_balance_request(req_id)
    if not req:
        await call.answer("So'rov topilmadi.", show_alert=True)
        return
    if req[4] != "pending":
        await call.answer("Bu so'rov allaqachon qayta ishlangan.", show_alert=True)
        return

    user_id, amount = req[1], req[2]
    await db.set_balance_request_status(req_id, "approved")
    ok, new_balance = await db.change_balance(user_id, amount, "topup", f"Hisob to'ldirish #{req_id}")

    user = await db.get_user(user_id)
    user_name = user[1] if user else str(user_id)

    try:
        if call.message.photo:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\nTASDIQLANDI")
        else:
            await call.message.edit_text((call.message.text or "") + "\n\nTASDIQLANDI")
    except Exception:
        pass

    await call.answer(f"To'lov tasdiqlandi.\n{user_name} foydalanuvchisining hisobiga {fmt_money(amount)} qo'shildi.", show_alert=True)

    try:
        await bot.send_message(
            user_id,
            "To'lovingiz tasdiqlandi.\n"
            f"Hisobingizga {fmt_money(amount)} qo'shildi.\n"
            f"Balans: {fmt_money(new_balance)}"
        )
    except Exception:
        logging.warning("Foydalanuvchiga tasdiq xabari yuborilmadi: %s", user_id)


@router.callback_query(F.data.startswith("topup_reject_"))
async def topup_reject_handler(call: types.CallbackQuery, state: FSMContext, db: Database):
    if not await is_admin(db, call.from_user.id):
        return
    perms = await get_permissions(db, call.from_user.id)
    if not perms["can_confirm_payments"]:
        await call.answer("Afsuski sizni adminlik darajangiz to'lovlarni tasdiqlashga yetmaydi.", show_alert=True)
        return
    req_id = int(call.data.split("_")[2])
    req = await db.get_balance_request(req_id)
    if not req:
        await call.answer("So'rov topilmadi.", show_alert=True)
        return
    if req[4] != "pending":
        await call.answer("Bu so'rov allaqachon qayta ishlangan.", show_alert=True)
        return
    await state.update_data(reject_req_id=req_id)
    await call.answer()
    await call.message.answer("Rad etish sababini yozing!")
    await state.set_state(RejectReason.waiting_for_reason)


@router.message(RejectReason.waiting_for_reason, F.text)
async def topup_reject_reason_handler(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_confirm_payments"]:
        return
    data = await state.get_data()
    req_id = data.get("reject_req_id")
    reason = message.text.strip()
    req = await db.get_balance_request(req_id)
    if not req or req[4] != "pending":
        await message.answer("Bu so'rov allaqachon qayta ishlangan yoki topilmadi.")
        await state.clear()
        return

    await db.set_balance_request_status(req_id, "rejected", reason)
    user_id, amount = req[1], req[2]

    await message.answer("To'lov rad etildi.\nFoydalanuvchining hisobiga pul qo'shilmadi.")

    try:
        await bot.send_message(
            user_id,
            "To'lovingiz rad etildi.\n"
            "Hisobingizga pul qo'shilmadi.\n"
            f"Sababi: {reason}"
        )
    except Exception:
        logging.warning("Foydalanuvchiga rad etish xabari yuborilmadi: %s", user_id)

    await state.clear()


# ==================== PUL ISHLASH / REFERAL ====================

@router.callback_query(F.data == "earn_money")
async def earn_money_handler(call: types.CallbackQuery, db: Database):
    user_id = call.from_user.id
    if await db.has_accepted_rules(user_id):
        await send_referral_link(call.message, db, call.bot, user_id, edit=True)
        return

    await call.message.edit_text(
        "Pul ishlash uchun botimizga do'stlaringizni taklif qilishingiz kerak bo'ladi.\n"
        "Sizga havola beriladi, shu havolani do'stingizga jo'natasiz, u shu havoladan "
        "o'tib botga start bossa sizga pul beriladi.\n"
        f"Har bir yangi do'st uchun bot sizga {fmt_money(REFERRAL_BONUS)}dan beradi.\n"
        "U pullarni faqat bot ichidagi video yoki VIP obuna sotib olish uchun "
        "ishlatishingiz mumkin.\n"
        "Havola qoidalar bilan tanishib olgandan keyin beriladi.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Qoidalar", callback_data="show_rules")],
            [types.InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet")]
        ])
    )


@router.callback_query(F.data == "show_rules")
async def show_rules_handler(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer(
        "Qoidalar\n\n"
        "1) Havolani ommaviy kanal yoki guruhlarda tarqatish taqiqlanadi. "
        "Faqat shaxsiy xabar orqali, ishonchli do'stlaringizga birma-bir yuborishingiz mumkin.\n\n"
        "2) Bitta qurilmadan bir nechta Telegram hisob ochib, o'zingizga o'zingiz "
        "referal yig'ish taqiqlanadi. Biz faqat jonli, haqiqiy foydalanuvchilar uchun "
        "mukofot beramiz, soxta hisoblar uchun emas.\n\n"
        "3) Foydalanuvchilarni yolg'on ma'lumot bilan aldab taklif qilish taqiqlanadi. "
        "Bunday holatda taklif qilingan foydalanuvchi botdan ham, sizdan ham norozi "
        "bo'ladi va bu ko'plab kelishmovchiliklarni keltirib chiqaradi.\n\n"
        "Qoida buzilsa nima bo'ladi?\n"
        "Tizim buzilishni darhol aniqlaydi va sizni botdan butunlay bloklaydi. "
        "Bundan keyin botdan foydalana olmaysiz.\n\n"
        "Barcha qoidalarga rioya qilishga rozimisiz? Agar \"Ha\" tugmasini bossangiz, "
        "sizga referal havolangiz taqdim etiladi.",
        reply_markup=kb.rules_kb()
    )


@router.callback_query(F.data == "rules_no")
async def rules_no_handler(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("Bosh menyu", reply_markup=kb.user_main_kb())


@router.callback_query(F.data == "rules_yes")
async def rules_yes_handler(call: types.CallbackQuery, db: Database):
    await db.set_rules_accepted(call.from_user.id)
    await send_referral_link(call.message, db, call.bot, call.from_user.id, edit=True)


async def send_referral_link(message, db: Database, bot: Bot, user_id: int, edit=False):
    link = await build_referral_link(bot, user_id)
    text = (
        f"Sizning shaxsiy referal havolangiz:\n{link}\n\n"
        "Ushbu havolani ishonchli do'stlaringizga yuboring. Ular havola orqali "
        f"botga kirib start bossa, hisobingizga {fmt_money(REFERRAL_BONUS)} qo'shiladi."
    )
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet")]
    ])
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=markup)


# ==================== VIP OBUNA ====================

@router.callback_query(F.data == "buy_vip")
async def buy_vip_handler(call: types.CallbackQuery, db: Database):
    prices = await db.get_vip_prices()
    await call.message.edit_text("Qaysi tarif turini tanlaysiz?", reply_markup=kb.vip_tariff_kb(prices))


@router.callback_query(F.data.startswith("vip_"))
async def select_vip_handler(call: types.CallbackQuery, db: Database):
    days = int(call.data.split("_")[1])
    prices = await db.get_vip_prices()
    price = prices.get(days)
    user_id = call.from_user.id
    balance = await db.get_balance(user_id)

    if balance < price:
        await call.message.edit_text(
            "Balansingizda yetarli mablag' yo'q.\n\n"
            f"Kerak: {fmt_money(price)}\n"
            f"Balansingiz: {fmt_money(balance)}\n\n"
            "Hisobingizni to'ldirish uchun Kabinetdagi \"Hisobni to'ldirish\" "
            "bo'limidan foydalaning!",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet")]
            ])
        )
        return

    ok, new_balance = await db.change_balance(user_id, -price, "vip_purchase", f"VIP {days} kun")
    if not ok:
        await call.message.edit_text(
            "Balansingizda yetarli mablag' yo'q.\n\n"
            f"Kerak: {fmt_money(price)}\n"
            f"Balansingiz: {fmt_money(new_balance)}\n\n"
            "Hisobingizni to'ldirish uchun Kabinetdagi \"Hisobni to'ldirish\" "
            "bo'limidan foydalaning!",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet")]
            ])
        )
        return

    vip_until = await db.set_vip(user_id, days)
    tariff_label = kb.VIP_LABELS[days]
    await call.message.edit_text(
        "Tabriklaymiz, siz VIP obunachiga aylandingiz!\n\n"
        f"Tarif: {tariff_label}\n"
        f"Tugaydi: {vip_until_str(vip_until)}\n"
        f"Balansdan yechildi: {fmt_money(price)}\n"
        f"Qolgan balans: {fmt_money(new_balance)}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Orqaga", callback_data="back_cabinet")]
        ])
    )


# ==================== VIDEOLARIM ====================

@router.callback_query(F.data.startswith("my_videos_"))
async def my_videos_handler(call: types.CallbackQuery, db: Database):
    page = int(call.data.split("_")[2])
    videos = await db.get_purchased_videos(call.from_user.id)
    if not videos:
        await call.answer("Sizda sotib olingan videolar yo'q.", show_alert=True)
        return
    total_pages = math.ceil(len(videos) / 10)
    try:
        await call.message.edit_text(
            "Shu kungacha sotib olgan videolaringiz",
            reply_markup=kb.my_videos_kb(videos, page, total_pages)
        )
    except Exception:
        await call.message.answer(
            "Shu kungacha sotib olgan videolaringiz",
            reply_markup=kb.my_videos_kb(videos, page, total_pages)
        )


# ==================== VIDEO KOD ORQALI ====================

async def user_can_watch_paid(db: Database, user_id, video_id):
    if await db.is_vip(user_id):
        return True
    return await db.has_purchased(user_id, video_id)


@router.message(StateFilter(None), F.text, F.from_user.id != ADMIN_ID)
async def video_code_handler(message: types.Message, db: Database):
    if await is_admin(db, message.from_user.id):
        return
    video = await db.get_video_by_code(message.text.strip())
    if not video:
        await message.answer("Bunday video kodi topilmadi.")
        return

    video_id = video[0]
    video_type = video[2]
    user_id = message.from_user.id

    if video_type == "free":
        await deliver_free_video(message, db, video, user_id)
        return

    owned = await user_can_watch_paid(db, user_id, video_id)
    caption = f"{video[4]}\n\nKo'rishlar: {video[8]}"
    await message.answer_photo(
        video[3],
        caption=caption,
        reply_markup=kb.video_post_paid_kb(video_id, owned),
        protect_content=True
    )


async def deliver_free_video(message_or_call, db: Database, video, user_id):
    video_id = video[0]
    is_call = isinstance(message_or_call, types.CallbackQuery)
    target = message_or_call.message if is_call else message_or_call

    await db.count_view_once(user_id, video_id)
    likes, dislikes = await db.get_likes(video_id)

    await target.answer_video(
        video[7],
        reply_markup=kb.video_action_kb(video_id, likes, dislikes, show_quality_switch=False),
        protect_content=True
    )

    ad = await db.get_ad_channel("free")
    if ad and ad[1]:
        await target.answer(
            "Yana boshqa videolar uchun bizning reklama kanalimizga o'ting!",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Kanalga o'tish", url=ad[1])]
            ])
        )


@router.callback_query(F.data.startswith("buy_video_"))
async def buy_video_handler(call: types.CallbackQuery, db: Database):
    try:
        video_id = int(call.data.split("_")[2])
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri video.", show_alert=True)
        return

    video = await db.get_video(video_id)
    if not video or video[2] != "paid":
        await call.answer("Video topilmadi.", show_alert=True)
        return

    user_id = call.from_user.id
    if await user_can_watch_paid(db, user_id, video_id):
        await call.answer("Sizda bu videoga kirish huquqi allaqachon mavjud.", show_alert=True)
        return

    price = video[6]
    balance = await db.get_balance(user_id)
    if balance < price:
        await call.message.edit_caption(
            caption=(
                "Balansingizda yetarli mablag' yo'q.\n\n"
                f"Kerak: {fmt_money(price)}\n"
                f"Balansingiz: {fmt_money(balance)}\n\n"
                "Hisobingizni to'ldirish uchun Kabinetdagi \"Hisobni to'ldirish\" "
                "bo'limidan foydalaning!"
            )
        )
        return

    ok, new_balance = await db.change_balance(user_id, -price, "video_purchase", f"Video #{video_id}")
    if not ok:
        await call.answer("Balansingizda yetarli mablag' yo'q.", show_alert=True)
        return

    await db.add_purchase(user_id, video_id)
    is_first_view = await db.count_view_once(user_id, video_id)
    video = await db.get_video(video_id)

    qualities = await db.get_video_qualities(video_id)
    likes, dislikes = await db.get_likes(video_id)

    await call.message.delete()

    if qualities:
        q_name, file_id = qualities[0]
        cap = f"{video[5]}\nSifati: {q_name}\nKo'rishlar: {video[8]}"
        await call.message.answer_video(
            file_id, caption=cap,
            reply_markup=kb.video_action_kb(video_id, likes, dislikes, show_quality_switch=len(qualities) > 1),
            protect_content=True
        )
    else:
        await call.message.answer(
            f"{video[5]}\n\nKo'rishlar: {video[8]}",
            reply_markup=kb.video_action_kb(video_id, likes, dislikes, show_quality_switch=False)
        )

    await call.message.answer(
        f"Video muvaffaqiyatli sotib olindi.\n\n"
        f"Video narxi: {fmt_money(price)}\n"
        f"Balansdan yechildi: {fmt_money(price)}\n"
        f"Qolgan balans: {fmt_money(new_balance)}"
    )

    if is_first_view:
        ad = await db.get_ad_channel("paid")
        if ad and ad[1]:
            await call.message.answer(
                "Yana boshqa videolar uchun bizning reklama kanalimizga o'ting!",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Kanalga o'tish", url=ad[1])]
                ])
            )


@router.callback_query(F.data.startswith("watch_paid_"))
async def watch_paid_handler(call: types.CallbackQuery, db: Database):
    video_id = int(call.data.split("_")[2])
    user_id = call.from_user.id

    if not await user_can_watch_paid(db, user_id, video_id):
        await call.answer("Bu videoni ko'rish uchun avval uni sotib oling.", show_alert=True)
        return

    video = await db.get_video(video_id)
    if not video:
        await call.answer("Video topilmadi.", show_alert=True)
        return

    qualities = await db.get_video_qualities(video_id)
    is_first_view = await db.count_view_once(user_id, video_id)
    video = await db.get_video(video_id)
    likes, dislikes = await db.get_likes(video_id)

    try:
        await call.message.delete()
    except Exception:
        pass

    if qualities:
        q_name, file_id = qualities[0]
        cap = f"{video[5]}\nSifati: {q_name}\nKo'rishlar: {video[8]}"
        await call.message.answer_video(
            file_id, caption=cap,
            reply_markup=kb.video_action_kb(video_id, likes, dislikes, show_quality_switch=len(qualities) > 1),
            protect_content=True
        )
    else:
        await call.message.answer(
            f"{video[5]}\n\nKo'rishlar: {video[8]}",
            reply_markup=kb.video_action_kb(video_id, likes, dislikes, show_quality_switch=False)
        )

    if is_first_view:
        ad = await db.get_ad_channel("paid")
        if ad and ad[1]:
            await call.message.answer(
                "Yana boshqa videolar uchun bizning reklama kanalimizga o'ting!",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Kanalga o'tish", url=ad[1])]
                ])
            )


@router.callback_query(F.data.startswith("change_quality_"))
async def change_quality_handler(call: types.CallbackQuery, db: Database):
    video_id = int(call.data.split("_")[2])
    qualities = await db.get_video_qualities(video_id)
    q_list = [q[0] for q in qualities]
    current_q = None
    if call.message.caption and "Sifati: " in call.message.caption:
        current_q = call.message.caption.split("Sifati: ")[1].split("\n")[0]
    await call.message.delete()
    await call.message.answer(
        "Sifatini tanlang!",
        reply_markup=kb.quality_select_kb(video_id, q_list, exclude=current_q)
    )


@router.callback_query(F.data.startswith("quality_"))
async def quality_selected_handler(call: types.CallbackQuery, db: Database):
    data = call.data.split("_")
    video_id = int(data[1])
    selected_quality = "_".join(data[2:])
    user_id = call.from_user.id

    if not await user_can_watch_paid(db, user_id, video_id):
        await call.answer("Bu videoni ko'rish huquqingiz yo'q.", show_alert=True)
        return

    qualities = await db.get_video_qualities(video_id)
    selected_file_id = None
    for quality_name, file_id in qualities:
        if quality_name == selected_quality:
            selected_file_id = file_id
            break

    if not selected_file_id:
        await call.answer("Bu sifatdagi video topilmadi.", show_alert=True)
        return

    video = await db.get_video(video_id)
    likes, dislikes = await db.get_likes(video_id)
    await db.count_view_once(user_id, video_id)

    try:
        await call.message.delete()
    except Exception:
        pass

    cap = f"{video[5]}\nSifati: {selected_quality}\nKo'rishlar: {video[8]}"
    await call.message.answer_video(
        selected_file_id, caption=cap,
        reply_markup=kb.video_action_kb(video_id, likes, dislikes, show_quality_switch=len(qualities) > 1),
        protect_content=True
    )


@router.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def like_handler(call: types.CallbackQuery, db: Database):
    action, video_id = call.data.split("_")
    video_id = int(video_id)
    is_like = 1 if action == "like" else 0

    prev_like = await db.has_liked(call.from_user.id, video_id)
    if prev_like == is_like:
        await call.answer("Siz allaqachon bosib bo'lgansiz!", show_alert=True)
        return

    await db.set_like(call.from_user.id, video_id, is_like)
    likes, dislikes = await db.get_likes(video_id)

    video = await db.get_video(video_id)
    show_switch = False
    if video and video[2] == "paid":
        qualities = await db.get_video_qualities(video_id)
        show_switch = len(qualities) > 1

    await call.message.edit_reply_markup(
        reply_markup=kb.video_action_kb(video_id, likes, dislikes, show_quality_switch=show_switch)
    )
