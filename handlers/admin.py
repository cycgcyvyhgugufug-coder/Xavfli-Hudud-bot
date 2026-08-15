import asyncio
import datetime
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import BaseFilter
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError

import keyboards as kb
from states import (
    AdminAddVideoPaid, AdminAddVideoFree, AdminDeleteVideo, AdminBroadcast, AdminGift,
    AdminUsers, AdminManage, AdminSettings, AdminChannels
)
from config import ADMIN_ID
from utils import (
    fmt_money, display_username, is_admin, get_permissions, vip_until_str,
    NO_PERMISSION_EDIT, NO_PERMISSION_USERS, NO_PERMISSION_ADMIN_MANAGE
)
from db import Database

router = Router()

GIFT_TARIFFS = {1: "1 kunlik VIP", 7: "1 haftalik VIP", 30: "1 oylik VIP"}


class IsAdminFilter(BaseFilter):
    """Ushbu router ichidagi BARCHA handlerlar faqat adminlar uchun ishlaydi.
    Bu callback_data'ni qo'lda yasab yuborishga urinishlardan ham himoya qiladi."""

    async def __call__(self, event, db: Database) -> bool:
        return await is_admin(db, event.from_user.id)


# gift_claim_gift_ callbackini oddiy foydalanuvchilar ham bosishi kerak,
# shuning uchun u pastda ALOHIDA (filtersiz) routerga o'tkaziladi.
public_router = Router()


@public_router.callback_query(F.data.startswith("claim_gift_"))
async def claim_gift_handler(call: types.CallbackQuery, db: Database):
    gift_id = int(call.data.rsplit("_", 1)[1])
    status, campaign = await db.claim_gift(gift_id, call.from_user.id)
    if status == "won":
        await db.set_vip(call.from_user.id, campaign[1])
        await call.answer("Tabriklaymiz, siz sovg'ani qo'lga kiritdingiz", show_alert=True)
        if campaign[4] >= campaign[3] and await db.mark_gift_completed_notified(gift_id):
            winners = await db.get_gift_winners(gift_id)
            lines = [
                "Hadyalarni olgan obunachilar", "",
                f"Tarif: {campaign[2]}",
                f"Jami: {len(winners)} ta", "",
                "G'oliblar:", ""
            ]
            for i, (uid, name, username) in enumerate(winners, 1):
                who = name or "User"
                uname = f"@{username}" if username else "mavjud emas"
                lines.extend([f"{i}. {who}", f"   Username: {uname}", f"   ID: {uid}", ""])
            await call.bot.send_message(ADMIN_ID, "\n".join(lines))
    elif status == "vip":
        await call.answer("Sizda allaqachon faol VIP obuna bor.", show_alert=True)
    elif status == "already":
        await call.answer("Siz allaqachon o'z sovg'angizni oldingiz.", show_alert=True)
    elif status == "not_found":
        await call.answer("Siz botda ro'yxatdan o'tmagansiz.", show_alert=True)
    else:
        await call.answer("Afsuski siz ulgurmadingiz, keyingi giftda faolroq bo'ling!", show_alert=True)


router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())


# ==================== UMUMIY ORQAGA HANDLERLARI ====================

@router.callback_query(F.data == "cancel_to_desk")
async def cancel_to_desk(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer("Ish stolingiz xo'jayin marhamat", reply_markup=kb.admin_desk_kb())


@router.callback_query(F.data == "cancel_to_settings")
async def cancel_to_settings(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


@router.callback_query(F.data == "back_channels_menu")
async def back_channels_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Kanallar bo'limidasiz xo'jayin marhamat", reply_markup=kb.channels_menu_kb())


@router.callback_query(F.data == "back_delete_channels_type")
async def back_delete_channels_type(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Qaysi kanallarni o'chiramiz?", reply_markup=kb.delete_channels_type_kb())


@router.callback_query(F.data.startswith("back_profile_"))
async def back_to_profile(call: types.CallbackQuery, state: FSMContext, db: Database):
    user_id = int(call.data.split("_")[2])
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_user_profile(call.message, db, user_id)


@router.callback_query(F.data == "perm_cancel")
async def perm_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


# ==================== ASOSIY MENYU ====================

@router.message(F.text == "Bosh menyu")
async def admin_go_home(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await state.clear()
    await message.answer("Admin panel", reply_markup=kb.admin_main_kb())


@router.message(F.text == "Ish stoli")
async def desk_menu(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await state.clear()
    await message.answer("Ish stolingiz xo'jayin marhamat", reply_markup=kb.admin_desk_kb())


@router.message(F.text == "Sozlamalar")
async def settings_menu(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await state.clear()
    await message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


@router.message(F.text == "Statistika")
async def stats_handler(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await state.clear()
    total_users = await db.get_total_users()
    vip_users = await db.get_vip_users_count()
    total_purchased = await db.get_purchased_videos_count()
    total_topped_up = await db.get_total_topped_up()
    total_referrals = await db.get_total_referrals()

    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - datetime.timedelta(days=7)

    new_today = await db.get_new_users_since(today_start)
    new_week = await db.get_new_users_since(week_start)
    sold_today = await db.get_purchases_since(today_start)
    sold_week = await db.get_purchases_since(week_start)

    text = (
        "Statistika\n\n"
        f"Jami foydalanuvchilar: {total_users}\n"
        f"VIP obunachilar: {vip_users}\n"
        f"Sotilgan videolar: {total_purchased}\n"
        f"Balansga tushgan jami mablag': {fmt_money(total_topped_up)}\n"
        f"Referal orqali kelganlar: {total_referrals}\n\n"
        f"Bugungi yangi foydalanuvchilar: {new_today}\n"
        f"Oxirgi 7 kundagi yangi foydalanuvchilar: {new_week}\n"
        f"Bugungi sotuvlar: {sold_today}\n"
        f"Oxirgi 7 kundagi sotuvlar: {sold_week}"
    )
    await message.answer(text)


# ==================== VIDEO QO'SHISH ====================

@router.message(F.text == "Video qo'shish")
async def add_video_start(message: types.Message, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await message.answer("Qanaqa video qo'shamiz?", reply_markup=kb.video_type_kb())


@router.callback_query(F.data == "addvideo_paid")
async def add_video_paid_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Video muqovasi uchun rasm jo'nating!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminAddVideoPaid.waiting_for_cover)


@router.message(AdminAddVideoPaid.waiting_for_cover, F.photo)
async def add_video_cover(message: types.Message, state: FSMContext):
    await state.update_data(cover=message.photo[-1].file_id)
    await message.answer("Video posti uchun izoh yozing!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminAddVideoPaid.waiting_for_post_desc)


@router.message(AdminAddVideoPaid.waiting_for_post_desc, F.text)
async def add_video_post_desc(message: types.Message, state: FSMContext):
    await state.update_data(post_desc=message.text)
    await message.answer("Asosiy video uchun izoh yozing!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminAddVideoPaid.waiting_for_main_desc)


@router.message(AdminAddVideoPaid.waiting_for_main_desc, F.text)
async def add_video_main_desc(message: types.Message, state: FSMContext):
    await state.update_data(main_desc=message.text)
    await message.answer("Video uchun narx belgilang!\nMasalan: 5000", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminAddVideoPaid.waiting_for_price)


@router.message(AdminAddVideoPaid.waiting_for_price, F.text)
async def add_video_price(message: types.Message, state: FSMContext):
    raw_price = message.text.strip().replace(" ", "").replace("_", "")
    if not raw_price.isdigit() or int(raw_price) <= 0:
        await message.answer("Iltimos, narxni faqat musbat raqam bilan kiriting. Masalan: 5000", reply_markup=kb.orqaga_kb("cancel_to_desk"))
        return
    await state.update_data(price=int(raw_price), qualities={})
    await message.answer("Video sifatini belgilang!", reply_markup=kb.admin_quality_select_kb([]))
    await state.set_state(AdminAddVideoPaid.waiting_for_quality_select)


@router.callback_query(AdminAddVideoPaid.waiting_for_quality_select, F.data.startswith("addq_"))
async def add_video_quality_select(call: types.CallbackQuery, state: FSMContext):
    q = call.data.split("_")[1]
    if q == "done":
        await call.message.edit_text("Video uchun kalit kodni yozing!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
        await state.set_state(AdminAddVideoPaid.waiting_for_code)
    else:
        await state.update_data(current_q=q)
        await call.message.edit_text(f"Endi shu sifatdagi ({q}) videoni jo'nating!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
        await state.set_state(AdminAddVideoPaid.waiting_for_video_file)


@router.message(AdminAddVideoPaid.waiting_for_video_file, F.video)
async def add_video_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    qualities = data.get('qualities', {})
    current_q = data['current_q']
    qualities[current_q] = message.video.file_id
    await state.update_data(qualities=qualities)
    await message.answer(
        "Video qabul qilindi, yana boshqa sifat qo'shasizmi?",
        reply_markup=kb.admin_quality_select_kb(list(qualities.keys()))
    )
    await state.set_state(AdminAddVideoPaid.waiting_for_quality_select)


@router.message(AdminAddVideoPaid.waiting_for_code, F.text)
async def add_video_code(message: types.Message, state: FSMContext, db: Database):
    code = message.text.strip()
    if await db.get_video_by_code(code):
        await message.answer("Bu kod band, boshqa kod kiriting!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
        return
    data = await state.get_data()
    video_id = await db.add_paid_video(code, data['cover'], data['post_desc'], data['main_desc'], data['price'])
    for q, file_id in data['qualities'].items():
        await db.add_video_quality(video_id, q, file_id)
    await message.answer("Video muvaffaqiyatli qo'shildi xo'jayin", reply_markup=kb.admin_desk_kb())
    await state.clear()


# ---------- BEPUL VIDEO ----------

@router.callback_query(F.data == "addvideo_free")
async def add_video_free_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Video faylini jo'nating!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminAddVideoFree.waiting_for_video_file)


@router.message(AdminAddVideoFree.waiting_for_video_file, F.video)
async def add_video_free_file(message: types.Message, state: FSMContext):
    await state.update_data(file_id=message.video.file_id)
    await message.answer("Video uchun kalit kodni yozing!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminAddVideoFree.waiting_for_code)


@router.message(AdminAddVideoFree.waiting_for_code, F.text)
async def add_video_free_code(message: types.Message, state: FSMContext, db: Database):
    code = message.text.strip()
    if await db.get_video_by_code(code):
        await message.answer("Bu kod band, boshqa kod kiriting!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
        return
    data = await state.get_data()
    await db.add_free_video(code, data['file_id'])
    await message.answer("Bepul video muvaffaqiyatli qo'shildi xo'jayin", reply_markup=kb.admin_desk_kb())
    await state.clear()


# ==================== VIDEO O'CHIRISH ====================

@router.message(F.text == "Video o'chirish")
async def delete_video_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await message.answer("O'chirmoqchi bo'lgan videongizni kodini yozing!", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminDeleteVideo.waiting_for_code)


@router.message(AdminDeleteVideo.waiting_for_code, F.text)
async def delete_video_code(message: types.Message, state: FSMContext, db: Database):
    code = message.text.strip()
    video = await db.get_video_by_code(code)
    if not video:
        await message.answer("Video topilmadi.", reply_markup=kb.admin_desk_kb())
        await state.clear()
        return
    await state.update_data(del_code=code)
    await message.answer(
        "Rostdan ham shu videoni o'chirmoqchimisiz?",
        reply_markup=kb.confirm_kb("delvid_yes", "delvid_no")
    )


@router.callback_query(F.data == "delvid_yes")
async def confirm_delete_video(call: types.CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    await db.delete_video(data['del_code'])
    await call.message.edit_text("Video muvaffaqiyatli o'chirildi.")
    await call.message.answer("Ish stolingiz xo'jayin marhamat", reply_markup=kb.admin_desk_kb())
    await state.clear()


@router.callback_query(F.data == "delvid_no")
async def cancel_delete_video(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Ish stolingiz xo'jayin marhamat", reply_markup=kb.admin_desk_kb())


# ==================== REKLAMA JO'NATISH ====================

def parse_url_buttons(text: str):
    rows = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        row = []
        for part in line.split("|"):
            part = part.strip()
            if " - " not in part:
                return None
            label, url = part.split(" - ", 1)
            label, url = label.strip(), url.strip()
            if not label or not url.startswith(("http://", "https://", "tg://")):
                return None
            row.append(types.InlineKeyboardButton(text=label, url=url))
        if not row or len(row) > 3:
            return None
        rows.append(row)
    if not rows:
        return None
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


async def send_broadcast_preview(message: types.Message, data: dict, reply_markup):
    content_type = data.get("type")
    caption = data.get("caption") or ""
    url_markup = data.get("url_markup")
    if content_type == "photo":
        await message.answer_photo(data["file_id"], caption=caption, reply_markup=url_markup or reply_markup)
    elif content_type == "video":
        await message.answer_video(data["file_id"], caption=caption, reply_markup=url_markup or reply_markup)
    else:
        await message.answer(caption or "-", reply_markup=url_markup or reply_markup)
    if url_markup:
        await message.answer("Reklamangiz shu ko'rinishda ketadi.", reply_markup=reply_markup)


@router.message(F.text == "Reklama jo'natish")
async def broadcast_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "Jo'natmoqchi bo'lgan reklamangizni yuboring!\n\nReklama qanaqa bo'ladi?\nRasm + matn yoki Video + matn yoki faqat matn.",
        reply_markup=kb.orqaga_kb("cancel_to_desk")
    )
    await state.set_state(AdminBroadcast.waiting_for_content)


@router.message(AdminBroadcast.waiting_for_content, F.photo)
async def broadcast_photo(message: types.Message, state: FSMContext):
    data = {"type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption or ""}
    await state.update_data(bc=data)
    await send_broadcast_preview(message, data, kb.broadcast_content_kb())


@router.message(AdminBroadcast.waiting_for_content, F.video)
async def broadcast_video(message: types.Message, state: FSMContext):
    data = {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
    await state.update_data(bc=data)
    await send_broadcast_preview(message, data, kb.broadcast_content_kb())


@router.message(AdminBroadcast.waiting_for_content, F.text)
async def broadcast_text(message: types.Message, state: FSMContext):
    data = {"type": "text", "caption": message.text}
    await state.update_data(bc=data)
    await send_broadcast_preview(message, data, kb.broadcast_content_kb())


@router.callback_query(F.data == "bc_add_buttons")
async def broadcast_add_buttons_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Menga bitta xabarda URL-tugmalar ro'yxatini yuboring. Iltimos, "
        "quyidagi formatga amal qiling:\n\n"
        "Tugma 1 - http://example1.com\n"
        "Tugma 2 - http://example2.com\n\n"
        "Bitta qatorga uchtagacha tugma qo'shish uchun | belgisidan "
        "foydalaning. Masalan:\n\n"
        "Tugma 1 - http://example1.com | Tugma 2 - http://example2.com\n"
        "Tugma 3 - http://example3.com | Tugma 4 - http://example4.com\n\n"
        "Xabarlar qo'shishga qaytish uchun \"Orqaga\" tugmasini bosing.",
        reply_markup=kb.broadcast_url_buttons_kb()
    )
    await state.set_state(AdminBroadcast.waiting_for_buttons)


@router.callback_query(F.data == "bc_back_to_content")
async def broadcast_back_to_content(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bc = data.get("bc", {})
    await call.message.delete()
    await state.set_state(AdminBroadcast.waiting_for_content)
    markup = kb.broadcast_content_with_buttons_kb() if bc.get("url_markup") else kb.broadcast_content_kb()
    await send_broadcast_preview(call.message, bc, markup)


@router.message(AdminBroadcast.waiting_for_buttons, F.text)
async def broadcast_buttons_received(message: types.Message, state: FSMContext):
    markup = parse_url_buttons(message.text)
    if not markup:
        await message.answer(
            "Format noto'g'ri. Qaytadan urinib ko'ring yoki \"Orqaga\" tugmasini bosing.",
            reply_markup=kb.broadcast_url_buttons_kb()
        )
        return
    data = await state.get_data()
    bc = data.get("bc", {})
    bc["url_markup"] = markup
    await state.update_data(bc=bc)
    await state.set_state(AdminBroadcast.waiting_for_content)
    await send_broadcast_preview(message, bc, kb.broadcast_content_with_buttons_kb())


@router.callback_query(F.data == "bc_clear_buttons")
async def broadcast_clear_buttons(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bc = data.get("bc", {})
    bc.pop("url_markup", None)
    await state.update_data(bc=bc)
    await call.message.delete()
    await send_broadcast_preview(call.message, bc, kb.broadcast_content_kb())


@router.callback_query(F.data == "bc_cancel")
async def broadcast_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Ish stolingiz xo'jayin marhamat", reply_markup=kb.admin_desk_kb())


@router.callback_query(F.data == "bc_ready")
async def broadcast_ready(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Auditoriyani tanlang!", reply_markup=kb.broadcast_target_kb())


async def _send_broadcast(bot: Bot, db: Database, target: str, bc: dict):
    users = await db.get_broadcast_users(target)
    url_markup = bc.get("url_markup")
    content_type = bc.get("type")
    caption = bc.get("caption") or ""
    sent = failed = 0
    for user_id in users:
        while True:
            try:
                if content_type == "photo":
                    await bot.send_photo(user_id, bc["file_id"], caption=caption, reply_markup=url_markup)
                elif content_type == "video":
                    await bot.send_video(user_id, bc["file_id"], caption=caption, reply_markup=url_markup)
                else:
                    await bot.send_message(user_id, caption or "-", reply_markup=url_markup)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except (TelegramForbiddenError, Exception) as e:
                failed += 1
                logging.warning("Reklama yuborilmadi user_id=%s: %s", user_id, e)
                break
        await asyncio.sleep(0.05)
    return sent, failed, len(users)


@router.callback_query(F.data.in_({"broadcast_vip", "broadcast_regular", "broadcast_all"}))
async def broadcast_target_handler(call: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    bc = data.get("bc")
    if not bc:
        await call.answer("Reklama ma'lumotlari topilmadi.", show_alert=True)
        await state.clear()
        return
    target_map = {"broadcast_vip": "vip", "broadcast_regular": "regular", "broadcast_all": "all"}
    target = target_map[call.data]
    label_map = {"vip": "VIP obunachilar", "regular": "Oddiy obunachilar", "all": "Barcha obunachilar"}

    await call.answer()
    await call.message.edit_text(f"Reklama {label_map[target]}ga yuborilmoqda...\nIltimos, kuting.")
    sent, failed, total = await _send_broadcast(bot, db, target, bc)
    await state.clear()
    await call.message.answer(
        f"Reklama yuborish yakunlandi!\n\n"
        f"Auditoriya: {label_map[target]}\n"
        f"Jami: {total} ta\n"
        f"Yetkazildi: {sent} ta\n"
        f"Yetkazilmadi: {failed} ta",
        reply_markup=kb.admin_desk_kb()
    )


# ==================== GIFT O'TKAZISH ====================

@router.message(F.text == "Gift o'tkazish")
async def gift_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await state.clear()
    await message.answer("Tariflar turini tanlang!", reply_markup=kb.gift_tariff_kb())
    await state.set_state(AdminGift.waiting_for_tariff)


@router.callback_query(AdminGift.waiting_for_tariff, F.data.startswith("gift_days_"))
async def gift_tariff_selected(call: types.CallbackQuery, state: FSMContext):
    days = int(call.data.split("_")[2])
    await state.update_data(gift_days=days, gift_tariff=GIFT_TARIFFS[days])
    await call.message.edit_text("Nechta odam g'olib bo'la oladi?", reply_markup=kb.orqaga_kb("cancel_to_desk"))
    await state.set_state(AdminGift.waiting_for_count)


@router.message(AdminGift.waiting_for_count, F.text)
async def gift_count_received(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("Iltimos, 1 yoki undan katta butun son kiriting.", reply_markup=kb.orqaga_kb("cancel_to_desk"))
        return
    await state.update_data(gift_count=int(raw))
    await message.answer("Gift boshlansinmi?", reply_markup=kb.confirm_kb("gift_start_yes", "gift_start_no"))
    await state.set_state(AdminGift.waiting_for_confirm)


@router.callback_query(F.data == "gift_start_no")
async def gift_start_no(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Ish stolingiz xo'jayin marhamat", reply_markup=kb.admin_desk_kb())


@router.callback_query(F.data == "gift_start_yes")
async def gift_start_yes(call: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    days, name, limit = data.get("gift_days"), data.get("gift_tariff"), data.get("gift_count")
    if not (days and name and limit):
        await state.clear()
        await call.message.edit_text("Gift ma'lumotlari topilmadi.")
        return

    gift_id = await db.create_gift_campaign(days, name, limit)
    await call.message.edit_text("Gift jo'natilmoqda...\nIltimos, kuting.")

    users = await db.get_non_vip_users()
    sent = failed = 0
    text = (
        f"Adminlar obunachilar uchun tekinga {name} sovg'a qilishmoqchi.\n"
        f"Shoshiling! Sovg'a faqatgina {limit} odamga nasib qiladi, "
        "omadingizni qo'ldan chiqarmang!"
    )
    gift_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Sovg'ani olish", callback_data=f"claim_gift_{gift_id}")]
    ])
    for uid in users:
        try:
            await bot.send_message(uid, text, reply_markup=gift_kb)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(uid, text, reply_markup=gift_kb)
                sent += 1
            except Exception:
                failed += 1
        except Exception as e:
            failed += 1
            logging.warning("Gift yuborilmadi user_id=%s: %s", uid, e)

    await state.clear()
    await call.message.answer(
        f"Gift jo'natildi!\n\nYuborildi: {sent} ta\nYetkazilmadi: {failed} ta",
        reply_markup=kb.admin_desk_kb()
    )


# ==================== SOZLAMALAR: KANALLAR ====================

@router.message(F.text == "Kanallar qo'shish")
async def channels_menu(message: types.Message, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    await message.answer("Kanallar bo'limidasiz xo'jayin marhamat", reply_markup=kb.channels_menu_kb())


@router.callback_query(F.data == "ch_add_mandatory")
async def add_mandatory_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Botni kanalga admin qilib tayinlang va kanaldagi postlardan birini botga jo'nating!",
        reply_markup=kb.orqaga_kb("back_channels_menu")
    )
    await state.set_state(AdminChannels.waiting_for_mandatory_channel)


@router.message(AdminChannels.waiting_for_mandatory_channel)
async def add_mandatory_channel_save(message: types.Message, state: FSMContext, db: Database):
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        url = f"https://t.me/{message.forward_from_chat.username}" if message.forward_from_chat.username else "Yopiq kanal"
        await db.add_channel(chat_id, url)
        await message.answer("Kanal muvaffaqiyatli qo'shildi.", reply_markup=kb.admin_settings_menu_kb())
        await state.clear()
    else:
        await message.answer("Iltimos, kanaldan post jo'nating.", reply_markup=kb.orqaga_kb("back_channels_menu"))


@router.callback_query(F.data == "ch_add_ad")
async def add_ad_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Kanal havolasini jo'nating!", reply_markup=kb.orqaga_kb("back_channels_menu"))
    await state.set_state(AdminChannels.waiting_for_ad_channel_link)


@router.message(AdminChannels.waiting_for_ad_channel_link, F.text)
async def add_ad_channel_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    await state.update_data(ad_url=url)
    await message.answer(
        f"Quyidagi havolani reklama kanal sifatida qo'shmoqchimisiz?\n{url}",
        reply_markup=kb.confirm_kb("adch_confirm_yes", "adch_confirm_no")
    )
    await state.set_state(AdminChannels.waiting_for_ad_channel_confirm)


@router.callback_query(F.data == "adch_confirm_no")
async def add_ad_channel_no(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Kanallar bo'limidasiz xo'jayin marhamat", reply_markup=kb.channels_menu_kb())


@router.callback_query(F.data == "adch_confirm_yes")
async def add_ad_channel_yes(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Bu kanal qaysi video turida ko'rsatilsin?", reply_markup=kb.ad_channel_video_type_kb())
    await state.set_state(AdminChannels.waiting_for_ad_channel_type)


@router.callback_query(F.data.in_({"adch_type_paid", "adch_type_free"}))
async def add_ad_channel_type(call: types.CallbackQuery, state: FSMContext, db: Database):
    video_type = "paid" if call.data == "adch_type_paid" else "free"
    data = await state.get_data()
    url = data.get("ad_url")
    await db.set_ad_channel(video_type, None, url)
    await state.clear()
    await call.message.edit_text("Reklama kanal muvaffaqiyatli qo'shildi.")
    await call.message.answer("Kanallar bo'limidasiz xo'jayin marhamat", reply_markup=kb.channels_menu_kb())


@router.callback_query(F.data == "ch_delete_menu")
async def delete_channels_menu(call: types.CallbackQuery):
    await call.message.edit_text("Qaysi kanallarni o'chiramiz?", reply_markup=kb.delete_channels_type_kb())


@router.callback_query(F.data == "delch_mandatory")
async def delete_mandatory_list(call: types.CallbackQuery, db: Database):
    channels = await db.get_mandatory_channels()
    if not channels:
        await call.answer("Majburiy kanallar mavjud emas.", show_alert=True)
        return
    await call.message.edit_text("Barcha majburiy kanallar", reply_markup=kb.mandatory_channels_delete_kb(channels))


@router.callback_query(F.data.startswith("delmch_"))
async def delete_mandatory_confirm(call: types.CallbackQuery, state: FSMContext):
    ch_id = call.data.split("_")[1]
    await state.update_data(del_ch_id=ch_id)
    await call.message.edit_text(
        "Rostdan ham shu kanalni o'chirishni hohlaysizmi?",
        reply_markup=kb.confirm_kb("delmch_yes", "delmch_no")
    )


@router.callback_query(F.data == "delmch_no")
async def delete_mandatory_no(call: types.CallbackQuery, db: Database):
    channels = await db.get_mandatory_channels()
    await call.message.edit_text("Barcha majburiy kanallar", reply_markup=kb.mandatory_channels_delete_kb(channels))


@router.callback_query(F.data == "delmch_yes")
async def delete_mandatory_yes(call: types.CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    await db.delete_channel(int(data['del_ch_id']))
    channels = await db.get_mandatory_channels()
    if channels:
        await call.message.edit_text("Barcha majburiy kanallar", reply_markup=kb.mandatory_channels_delete_kb(channels))
    else:
        await call.message.edit_text("Barcha majburiy kanallar o'chirildi.")
    await state.clear()


@router.callback_query(F.data == "delch_ad")
async def delete_ad_type_menu(call: types.CallbackQuery):
    await call.message.edit_text("Qaysi reklama kanalni o'chiramiz?", reply_markup=kb.ad_channels_delete_type_kb())


@router.callback_query(F.data.in_({"deladch_paid", "deladch_free"}))
async def delete_ad_channel_confirm(call: types.CallbackQuery, state: FSMContext):
    video_type = "paid" if call.data == "deladch_paid" else "free"
    await state.update_data(del_ad_type=video_type)
    await call.message.edit_text(
        "Rostdan ham o'chirmoqchimisiz?",
        reply_markup=kb.confirm_kb("deladch_yes", "deladch_no")
    )


@router.callback_query(F.data == "deladch_no")
async def delete_ad_channel_no(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Qaysi kanallarni o'chiramiz?", reply_markup=kb.delete_channels_type_kb())


@router.callback_query(F.data == "deladch_yes")
async def delete_ad_channel_yes(call: types.CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    video_type = data.get("del_ad_type")
    await db.delete_ad_channel(video_type)
    await state.clear()
    await call.message.edit_text("Kanal muvaffaqiyatli o'chirildi.")


# ==================== SOZLAMALAR: FOYDALANUVCHILAR ====================

@router.message(F.text == "Foydalanuvchilar")
async def users_menu_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_view_users"]:
        await message.answer(NO_PERMISSION_USERS)
        return
    await message.answer("Foydalanuvchi ID raqamini yuboring!", reply_markup=kb.orqaga_kb("cancel_to_settings"))
    await state.set_state(AdminUsers.waiting_for_user_id)


async def show_user_profile(message: types.Message, db: Database, user_id: int, edit=False):
    user = await db.get_user(user_id)
    if not user:
        await message.answer("Bunday ID raqamli foydalanuvchi topilmadi.")
        return
    is_vip = await db.is_vip(user_id)
    is_blocked = bool(user[7])
    friends = await db.get_referral_count(user_id)
    purchases = len(await db.get_purchased_videos(user_id))

    text = (
        f"Ismi: {user[1]}\n"
        f"Useri: {display_username(user[2])}\n"
        f"IDsi: {user[0]}\n"
        f"Balansi: {fmt_money(user[3])}\n"
        f"Holati: {'VIP obunachi' if is_vip else 'Oddiy obunachi'}\n"
    )
    if is_vip:
        text += f"Muddati: {vip_until_str(user[4])} da tugaydi\n"
    blocked_label = "Ha" if is_blocked else "Yo'q"
    text += (
        f"Do'stlari: {friends} ta\n"
        f"Sotib olgan videolari: {purchases} ta\n"
        f"Bloklangan: {blocked_label}"
    )
    markup = kb.user_profile_kb(user_id, is_vip, is_blocked)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(AdminUsers.waiting_for_user_id, F.text)
async def users_id_received(message: types.Message, state: FSMContext, db: Database):
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("Iltimos, to'g'ri Telegram ID raqamini yuboring.", reply_markup=kb.orqaga_kb("cancel_to_settings"))
        return
    user_id = int(raw)
    await state.clear()
    await show_user_profile(message, db, user_id)


# ---------- PUL QO'SHISH / AYIRISH ----------

@router.callback_query(F.data.startswith("uadd_"))
async def user_add_balance_start(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(target_user_id=user_id)
    await call.message.answer("Qancha pul qo'shmoqchisiz? Summani yozing!", reply_markup=kb.orqaga_kb(f"back_profile_{user_id}"))
    await state.set_state(AdminUsers.waiting_for_add_amount)


@router.message(AdminUsers.waiting_for_add_amount, F.text)
async def user_add_balance_amount(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace(" ", "")
    data = await state.get_data()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("Iltimos, musbat raqam kiriting.", reply_markup=kb.orqaga_kb(f"back_profile_{data['target_user_id']}"))
        return
    await state.update_data(amount=int(raw))
    await message.answer(
        f"{fmt_money(int(raw))} miqdorini qo'shishni tasdiqlaysizmi?",
        reply_markup=kb.confirm_kb("uaddconfirm_yes", "uaddconfirm_no")
    )
    await state.set_state(AdminUsers.waiting_for_add_confirm)


@router.callback_query(F.data == "uaddconfirm_no")
async def user_add_balance_no(call: types.CallbackQuery, state: FSMContext, db: Database):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


@router.callback_query(F.data == "uaddconfirm_yes")
async def user_add_balance_yes(call: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    user_id, amount = data['target_user_id'], data['amount']
    ok, new_balance = await db.change_balance(user_id, amount, "admin_add", "Admin tomonidan qo'shildi")
    await state.clear()
    await call.message.edit_text(f"Foydalanuvchi hisobiga {fmt_money(amount)} qo'shildi.\nYangi balans: {fmt_money(new_balance)}")
    try:
        await bot.send_message(user_id, f"Admin hisobingizga {fmt_money(amount)} qo'shdi.\nBalans: {fmt_money(new_balance)}")
    except Exception:
        logging.warning("Foydalanuvchiga balans xabari yuborilmadi: %s", user_id)


@router.callback_query(F.data.startswith("usub_"))
async def user_sub_balance_start(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(target_user_id=user_id)
    await call.message.answer("Qancha pul ayirmoqchisiz? Summani yozing!", reply_markup=kb.orqaga_kb(f"back_profile_{user_id}"))
    await state.set_state(AdminUsers.waiting_for_subtract_amount)


@router.message(AdminUsers.waiting_for_subtract_amount, F.text)
async def user_sub_balance_amount(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace(" ", "")
    data = await state.get_data()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("Iltimos, musbat raqam kiriting.", reply_markup=kb.orqaga_kb(f"back_profile_{data['target_user_id']}"))
        return
    await state.update_data(amount=int(raw))
    await message.answer(
        f"{fmt_money(int(raw))} miqdorini ayirishni tasdiqlaysizmi?",
        reply_markup=kb.confirm_kb("usubconfirm_yes", "usubconfirm_no")
    )
    await state.set_state(AdminUsers.waiting_for_subtract_confirm)


@router.callback_query(F.data == "usubconfirm_no")
async def user_sub_balance_no(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


@router.callback_query(F.data == "usubconfirm_yes")
async def user_sub_balance_yes(call: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    user_id, amount = data['target_user_id'], data['amount']
    ok, new_balance = await db.change_balance(user_id, -amount, "admin_subtract", "Admin tomonidan ayirildi")
    await state.clear()
    if not ok:
        await call.message.edit_text(f"Foydalanuvchida yetarli mablag' yo'q. Balans: {fmt_money(new_balance)}")
        return
    await call.message.edit_text(f"Foydalanuvchi hisobidan {fmt_money(amount)} ayirildi.\nYangi balans: {fmt_money(new_balance)}")
    try:
        await bot.send_message(user_id, f"Admin hisobingizdan {fmt_money(amount)} ayirdi.\nBalans: {fmt_money(new_balance)}")
    except Exception:
        logging.warning("Foydalanuvchiga balans xabari yuborilmadi: %s", user_id)


# ---------- VIP BERISH / OLISH ----------

@router.callback_query(F.data.startswith("uvipgive_"))
async def user_vip_give_start(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await call.message.answer("VIP tarifni tanlang!", reply_markup=kb.user_vip_give_tariff_kb(user_id))


@router.callback_query(F.data.startswith("uvipset_"))
async def user_vip_give_confirm(call: types.CallbackQuery, db: Database, bot: Bot):
    _, user_id, days = call.data.split("_")
    user_id, days = int(user_id), int(days)
    vip_until = await db.set_vip(user_id, days)
    tariff_label = kb.VIP_LABELS[days]
    await call.message.edit_text(f"{tariff_label} VIP berildi. Tugaydi: {vip_until_str(vip_until)}")
    try:
        await bot.send_message(user_id, f"Admin sizga {tariff_label} VIP obuna berdi.\nTugaydi: {vip_until_str(vip_until)}")
    except Exception:
        logging.warning("Foydalanuvchiga VIP xabari yuborilmadi: %s", user_id)


@router.callback_query(F.data.startswith("uviprevoke_"))
async def user_vip_revoke(call: types.CallbackQuery, db: Database, bot: Bot):
    user_id = int(call.data.split("_")[1])
    result = await db.revoke_vip(user_id)
    if result == "revoked":
        await call.message.edit_text("Foydalanuvchining VIP obunasi bekor qilindi.")
        try:
            await bot.send_message(user_id, "Admin sizning VIP obunangizni bekor qildi.")
        except Exception:
            logging.warning("Foydalanuvchiga VIP bekor xabari yuborilmadi: %s", user_id)
    else:
        await call.answer("Bu foydalanuvchida faol VIP obuna mavjud emas.", show_alert=True)


# ---------- BLOCKLASH / BLOCKDAN CHIQARISH ----------

@router.callback_query(F.data.startswith("ublock_"))
async def user_block_start(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(target_user_id=user_id)
    await call.message.answer(
        "Rostdan ham shu foydalanuvchini blocklamoqchimisiz?",
        reply_markup=kb.confirm_kb("ublockconfirm_yes", "ublockconfirm_no")
    )
    await state.set_state(AdminUsers.waiting_for_block_confirm)


@router.callback_query(F.data == "ublockconfirm_no")
async def user_block_no(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


@router.callback_query(F.data == "ublockconfirm_yes")
async def user_block_yes(call: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    user_id = data['target_user_id']
    await db.set_blocked(user_id, True)
    await state.clear()
    await call.message.edit_text("Foydalanuvchi bloklandi.")
    try:
        await bot.send_message(
            user_id,
            "Siz botdan butunlay blocklandingiz. Sababini bilmoqchi bo'lsangiz "
            "Yordam bo'limidan adminga murojaat qiling."
        )
    except Exception:
        logging.warning("Foydalanuvchiga block xabari yuborilmadi: %s", user_id)


@router.callback_query(F.data.startswith("uunblock_"))
async def user_unblock(call: types.CallbackQuery, db: Database, bot: Bot):
    user_id = int(call.data.split("_")[1])
    await db.set_blocked(user_id, False)
    await call.message.edit_text("Foydalanuvchi blockdan chiqarildi.")
    try:
        await bot.send_message(user_id, "Siz blockdan ozod etildingiz, endi erkin foydalanishingiz mumkin.")
    except Exception:
        logging.warning("Foydalanuvchiga unblock xabari yuborilmadi: %s", user_id)


# ---------- XABAR YUBORISH ----------

@router.callback_query(F.data.startswith("umsg_"))
async def user_message_start(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(target_user_id=user_id)
    await call.message.answer("Yubormoqchi bo'lgan xabaringizni yozing!", reply_markup=kb.orqaga_kb(f"back_profile_{user_id}"))
    await state.set_state(AdminUsers.waiting_for_message_text)


@router.message(AdminUsers.waiting_for_message_text, F.text)
async def user_message_send(message: types.Message, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    user_id = data['target_user_id']
    try:
        await bot.send_message(user_id, message.text)
        await message.answer("Xabar yuborildi.", reply_markup=kb.admin_settings_menu_kb())
    except Exception:
        await message.answer("Xabar yuborilmadi, foydalanuvchi botni bloklagan bo'lishi mumkin.", reply_markup=kb.admin_settings_menu_kb())
    await state.clear()


# ==================== ADMIN QILISH / ADMINDAN OLISH ====================

@router.message(F.text == "Admin qilish")
async def make_admin_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_manage_admins"]:
        await message.answer(NO_PERMISSION_ADMIN_MANAGE)
        return
    await message.answer("Foydalanuvchining ID raqamini jo'nating!", reply_markup=kb.orqaga_kb("cancel_to_settings"))
    await state.set_state(AdminManage.waiting_for_new_admin_id)


@router.message(AdminManage.waiting_for_new_admin_id, F.text)
async def make_admin_id(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("Iltimos, to'g'ri Telegram ID raqamini yuboring.", reply_markup=kb.orqaga_kb("cancel_to_settings"))
        return
    await state.update_data(new_admin_id=int(raw))
    await message.answer(
        "Rostdan ham shu foydalanuvchini admin qilmoqchimisiz?",
        reply_markup=kb.confirm_kb("mkadmin_yes", "mkadmin_no")
    )
    await state.set_state(AdminManage.waiting_for_new_admin_confirm)


@router.callback_query(F.data == "mkadmin_no")
async def make_admin_no(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


@router.callback_query(F.data == "mkadmin_yes")
async def make_admin_yes(call: types.CallbackQuery, state: FSMContext):
    perms = {"can_edit": False, "can_confirm_payments": False, "can_manage_admins": False, "can_view_users": False}
    await state.update_data(new_perms=perms)
    await call.message.edit_text("Adminda qanaqa huquqlar bo'lsin?", reply_markup=kb.admin_permissions_kb(perms))
    await state.set_state(AdminManage.waiting_for_permissions)


@router.callback_query(AdminManage.waiting_for_permissions, F.data.startswith("perm_"))
async def toggle_permission(call: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    key = call.data[len("perm_"):]
    data = await state.get_data()
    perms = data.get("new_perms", {})

    if key == "done":
        user_id = data['new_admin_id']
        await db.add_admin(user_id, added_by=call.from_user.id, permissions=perms)
        await state.clear()
        await call.message.edit_text("Foydalanuvchi admin etib tayinlandi.")
        await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())
        try:
            await bot.send_message(user_id, "Siz botga admin etib tayinlandingiz.")
        except Exception:
            logging.warning("Yangi adminga xabar yuborilmadi: %s", user_id)
        return

    perms[key] = not perms.get(key, False)
    await state.update_data(new_perms=perms)
    await call.message.edit_reply_markup(reply_markup=kb.admin_permissions_kb(perms))


@router.message(F.text == "Admindan olish")
async def remove_admin_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_manage_admins"]:
        await message.answer(NO_PERMISSION_ADMIN_MANAGE)
        return
    await message.answer("Adminlikdan olmoqchi bo'lgan foydalanuvchi ID raqamini yuboring!", reply_markup=kb.orqaga_kb("cancel_to_settings"))
    await state.set_state(AdminManage.waiting_for_remove_admin_id)


@router.message(AdminManage.waiting_for_remove_admin_id, F.text)
async def remove_admin_id(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("Iltimos, to'g'ri Telegram ID raqamini yuboring.", reply_markup=kb.orqaga_kb("cancel_to_settings"))
        return
    await state.update_data(remove_admin_id=int(raw))
    await message.answer(
        "Rostdan ham shu foydalanuvchidan adminlikni olib qo'ymoqchimisiz?",
        reply_markup=kb.confirm_kb("rmadmin_yes", "rmadmin_no")
    )
    await state.set_state(AdminManage.waiting_for_remove_confirm)


@router.callback_query(F.data == "rmadmin_no")
async def remove_admin_no(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Sozlamalar bo'limidasiz xo'jayin marhamat", reply_markup=kb.admin_settings_menu_kb())


@router.callback_query(F.data == "rmadmin_yes")
async def remove_admin_yes(call: types.CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    data = await state.get_data()
    user_id = data['remove_admin_id']
    await db.remove_admin(user_id)
    await state.clear()
    await call.message.edit_text("Adminlik bekor qilindi.")
    try:
        await bot.send_message(user_id, "Sizning adminligingiz bekor qilindi.")
    except Exception:
        logging.warning("Xabar yuborilmadi: %s", user_id)


# ==================== KARTA / VIP NARX / INFO / ADMIN LINK EDIT ====================

@router.message(F.text == "Karta edit")
async def card_edit_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_edit"]:
        await message.answer(NO_PERMISSION_EDIT)
        return
    await message.answer("Karta raqamingizni jo'nating!", reply_markup=kb.orqaga_kb("cancel_to_settings"))
    await state.set_state(AdminSettings.waiting_for_card)


@router.message(AdminSettings.waiting_for_card, F.text)
async def card_edit_save(message: types.Message, state: FSMContext, db: Database):
    await db.set_setting("card", message.text.strip())
    await message.answer("Karta raqam muvaffaqiyatli saqlandi.", reply_markup=kb.admin_settings_menu_kb())
    await state.clear()


@router.message(F.text == "Vip narx edit")
async def vip_price_edit_start(message: types.Message, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_edit"]:
        await message.answer(NO_PERMISSION_EDIT)
        return
    await message.answer("Qaysi tarif narxini o'zgartiramiz?", reply_markup=kb.vip_price_tariff_kb())


@router.callback_query(F.data.startswith("vipprice_"))
async def vip_price_tariff_selected(call: types.CallbackQuery, state: FSMContext):
    days = int(call.data.split("_")[1])
    await state.update_data(vip_price_days=days)
    await call.message.edit_text(f"{kb.VIP_LABELS[days]} tarif uchun yangi narxni kiriting!\nMasalan: 5000", reply_markup=kb.orqaga_kb("cancel_to_settings"))
    await state.set_state(AdminSettings.waiting_for_vip_price)


@router.message(AdminSettings.waiting_for_vip_price, F.text)
async def vip_price_save(message: types.Message, state: FSMContext, db: Database):
    raw = message.text.strip().replace(" ", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("Iltimos, musbat raqam kiriting.", reply_markup=kb.orqaga_kb("cancel_to_settings"))
        return
    data = await state.get_data()
    days = data['vip_price_days']
    await db.set_setting(f"vip_price_{days}", raw)
    await message.answer(f"{kb.VIP_LABELS[days]} tarif narxi {fmt_money(int(raw))} qilib saqlandi.", reply_markup=kb.admin_settings_menu_kb())
    await state.clear()


@router.message(F.text == "Info edit")
async def info_edit_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_edit"]:
        await message.answer(NO_PERMISSION_EDIT)
        return
    await message.answer("Yangi matnni jo'nating!", reply_markup=kb.orqaga_kb("cancel_to_settings"))
    await state.set_state(AdminSettings.waiting_for_info)


@router.message(AdminSettings.waiting_for_info, F.text)
async def info_edit_save(message: types.Message, state: FSMContext, db: Database):
    await db.set_setting("bot_info", message.text)
    await message.answer("Matn saqlandi, ma'lumot almashtirildi.", reply_markup=kb.admin_settings_menu_kb())
    await state.clear()


@router.message(F.text == "Admin link edit")
async def admin_link_edit_start(message: types.Message, state: FSMContext, db: Database):
    if not await is_admin(db, message.from_user.id):
        return
    perms = await get_permissions(db, message.from_user.id)
    if not perms["can_edit"]:
        await message.answer(NO_PERMISSION_EDIT)
        return
    await message.answer("Havolani jo'nating!", reply_markup=kb.orqaga_kb("cancel_to_settings"))
    await state.set_state(AdminSettings.waiting_for_admin_link)


@router.message(AdminSettings.waiting_for_admin_link, F.text)
async def admin_link_edit_save(message: types.Message, state: FSMContext, db: Database):
    await db.set_setting("admin_link", message.text.strip())
    await message.answer("Havola saqlandi.", reply_markup=kb.admin_settings_menu_kb())
    await state.clear()
