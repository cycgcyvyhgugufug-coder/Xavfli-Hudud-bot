import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
import math

from config import BOT_TOKEN, ADMIN_ID
from db import Database
import keyboards as kb
from states import AdminAddVideo, AdminDeleteVideo, AdminSettings, UserPayment, AdminBroadcast, AdminGifts

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()
db = Database()

# Helper function
async def check_sub(user_id):
    channels = await db.get_mandatory_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch[0], user_id)
            if member.status in ['left', 'kicked', 'restricted']:
                return False
        except Exception as e:
            logging.exception("Majburiy obuna tekshiruvida xato: channel=%s user=%s", ch[0], user_id)
            # Tekshirishning o'zi ishlamasa, foydalanuvchini avtomatik ravishda
            # obuna bo'lgan deb qabul qilmaymiz.
            return False
    return True

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        await message.answer("Assalomu alaykum, xo'jayin hush kelibsiz Bugun nima qilamiz?", reply_markup=kb.admin_main_kb())
        return

    await db.add_user(user_id, message.from_user.first_name, message.from_user.username)
    
    if not await check_sub(user_id):
        channels = await db.get_mandatory_channels()
        await message.answer("Botdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'ling!", reply_markup=kb.mandatory_channels_kb(channels))
        return

    await message.answer(f"Salom {message.from_user.first_name} botga hush kelibsiz ko'rmoqchi bo'lgan video kodini jo'nating!", reply_markup=kb.user_main_kb())

@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer(f"Salom {call.from_user.first_name} botga hush kelibsiz ko'rmoqchi bo'lgan video kodini jo'nating!", reply_markup=kb.user_main_kb())
    else:
        await call.answer("Hali barcha kanallarga obuna bo'lmapsiz!", show_alert=True)

@dp.message(Command("data"))
async def get_data_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    db_file = FSInputFile("bot.db")
    await message.answer_document(db_file, caption="Botning ma'lumotlar bazasi")

# USER HANDLERS
@dp.message(F.text.in_({"Kabinet", "👤 Kabinet", "👤  Kabinet"}))
async def cabinet_handler(message: types.Message):
    await db.add_user(message.from_user.id, message.from_user.first_name, message.from_user.username)
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Foydalanuvchi ma'lumotlari topilmadi. Iltimos /start ni bosing.")
        return
    purchased = await db.get_user_purchased_count(message.from_user.id)
    is_vip = await db.is_vip(message.from_user.id)
    tariff = "Vip tarif" if is_vip else "Oddiy"
    
    text = (f"Ismi: {user[1]}\n"
            f"Useri: @{user[2]}\n"
            f"IDsi: {user[0]}\n"
            f"Tarifi: {tariff}\n"
            f"Sotib olingan videolari: {purchased} ta")
    await message.answer(text, reply_markup=kb.cabinet_kb())

@dp.message(F.text == "Yordam")
async def help_handler(message: types.Message):
    admin_link = (await db.get_setting("admin_link") or "").strip()

    if admin_link.startswith(("http://", "https://")):
        contact_url = admin_link
    else:
        admin_link = (
            admin_link
            .replace("https://t.me/", "")
            .replace("http://t.me/", "")
            .replace("t.me/", "")
            .lstrip("@")
            .strip("/")
        )
        contact_url = f"https://t.me/{admin_link}"

    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Bog'lanish", url=contact_url)],
        [types.InlineKeyboardButton(text="Orqaga", callback_data="main_menu")]
    ])
    await message.answer(
        "Agar sizda muammolar yoki qanaqadur savollar paydo bo'lgan bo'lsa admin bilan bo'g'lanishingiz mumkin",
        reply_markup=markup
    )

@dp.message(F.text == "Bot haqida")
async def about_handler(message: types.Message):
    text = ("Ushbu bot orqali siz turli sifatdagi (360p, 480p, 720p, 1080p) videolarni tomosha qilishingiz mumkin!\n\n"
            "Siz videolarni donalab sotib olishingiz yoki VIP tariflarni xarid qilib barcha videolarni cheklovsiz ko'rishingiz mumkin.\n"
            "Donalab olingan videolar doimiy sizning kabinetingizda qoladi.\n"
            "VIP tariflarida esa obuna tugagunga qadar barcha videolarni ko'rish huquqiga ega bo'lasiz.")
    await message.answer(text)

@dp.callback_query(F.data == "buy_vip")
async def buy_vip_handler(call: types.CallbackQuery):
    await call.message.edit_text("O'zingizga maqul kelgan tarifini tanlang!", reply_markup=kb.vip_kb())

@dp.callback_query(F.data.startswith("vip_"))
async def select_vip_handler(call: types.CallbackQuery, state: FSMContext):
    days = int(call.data.split("_")[1])
    prices = {1: 5000, 7: 15000, 30: 25000}
    price = prices.get(days)
    card = await db.get_setting("card")
    text = (f"Ajoyib endi quyidagi karta raqamga to'lovni amalga oshiring va pastdagi to'lov qildim tugmasini bosib chekni skrinshot qilib botga jo'nating!\n"
            f"Karta raqam: {card}\n"
            f"To'lov summasi: {price} so'm")
    await state.update_data(vip_days=days)
    await call.message.edit_text(text, reply_markup=kb.payment_done_kb("vip", days))

@dp.callback_query(F.data.startswith("paid_"))
async def paid_handler(call: types.CallbackQuery, state: FSMContext):
    data = call.data.split("_")
    item_type, item_id = data[1], data[2]
    await call.message.edit_text("Endi tasdiqlash uchun chekni rasmini jo'nating!")
    if item_type == "vip":
        await state.set_state(UserPayment.waiting_for_receipt_vip)
        await state.update_data(item_id=item_id)
    else:
        await state.set_state(UserPayment.waiting_for_receipt_video)
        await state.update_data(item_id=item_id)

@dp.message(UserPayment.waiting_for_receipt_vip, F.photo)
async def receipt_vip_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    days = data['item_id']
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, 
                         caption=f"Yangi VIP to'lov!\nFoydalanuvchi: {message.from_user.id} (@{message.from_user.username})\nTarif: {days} kun",
                         reply_markup=kb.admin_approve_kb(message.from_user.id, "vip", days))
    await message.answer("To'lovingiz qabul qilindi va adminga xabar yubordik tez orada admin to'lovingizni tasdiqlaydi.")
    await state.clear()

@dp.message(UserPayment.waiting_for_receipt_video, F.photo)
async def receipt_video_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_id = data['item_id']
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, 
                         caption=f"Yangi Video to'lov!\nFoydalanuvchi: {message.from_user.id} (@{message.from_user.username})\nVideo ID: {video_id}",
                         reply_markup=kb.admin_approve_kb(message.from_user.id, "video", video_id))
    await message.answer("To'lov qabul qilindi va adminga xabar yubordik tez orada to'lovingiz tasdiqlanadi.")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_handler(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    if call.message.caption and "✅ TASDIQLANGAN" in call.message.caption:
        await call.answer("Bu to'lov allaqachon tasdiqlangan.", show_alert=True)
        return

    data = call.data.split("_")
    try:
        user_id = int(data[1])
        item_type = data[2]
        item_id = int(data[3])
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri to'lov ma'lumoti.", show_alert=True)
        return

    if item_type not in {"vip", "video"}:
        await call.answer("Noto'g'ri to'lov turi.", show_alert=True)
        return

    if not await db.get_user(user_id):
        await call.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    if item_type == "vip":
        await db.set_vip(user_id, item_id)
        await bot.send_message(user_id, "Tabriklaymiz to'lovingiz tasdiqlanadi endi botdan bemalol foydalanishingiz mumkin, ko'rmoqchi bo'lgan videongizni kodini yozing!")
    elif item_type == "video":
        if not await db.get_video(item_id):
            await call.answer("Video topilmadi.", show_alert=True)
            return
        await db.add_purchase(user_id, item_id)
        await bot.send_message(
            user_id,
            "Tabriklaymiz to'lovingiz tasdiqlandi, endi videoni ko'rishingiz mumkin!"
        )

        qualities = await db.get_video_qualities(item_id)
        if qualities:
            q_name, file_id = qualities[0]
            video = await db.get_video(item_id)
            likes, dislikes = await db.get_likes(item_id)
            caption = f"{video[4]}\nSifati: {q_name}\nKo'rishlar: {video[6]}"
            await bot.send_video(
                user_id,
                file_id,
                caption=caption,
                reply_markup=kb.video_action_kb(item_id, likes, dislikes),
                protect_content=True
            )
    
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ TASDIQLANGAN")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_handler(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    if call.message.caption and ("✅ TASDIQLANGAN" in call.message.caption or "❌ RAD ETILGAN" in call.message.caption):
        await call.answer("Bu to'lov allaqachon qayta ishlangan.", show_alert=True)
        return
    data = call.data.split("_")
    user_id = int(data[1])
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Bosh menyu", callback_data="main_menu")]])
    await bot.send_message(user_id, "Afsus sizni to'lovingiz rad qilindi sababi siz yolg'on to'lov qilgansiz iltimos qayta urinib ko'ring!", reply_markup=markup)
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ RAD ETILGAN")

@dp.callback_query(F.data.startswith("my_videos_"))
async def my_videos_handler(call: types.CallbackQuery):
    page = int(call.data.split("_")[2])
    videos = await db.get_purchased_videos(call.from_user.id)
    if not videos:
        await call.answer("Sizda sotib olingan videolar yo'q.", show_alert=True)
        return
    
    total_pages = math.ceil(len(videos) / 10)
    await call.message.edit_text("Shu kungacha sotib olgan videolaringiz", reply_markup=kb.my_videos_kb(videos, page, total_pages))

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer(f"Bosh menyu", reply_markup=kb.user_main_kb())

async def user_can_watch_video(user_id, video_id):
    """VIP yoki aynan shu video sotib olingan bo'lsa, videoni ko'rishga ruxsat."""
    # VIP birinchi navbatda tekshiriladi: VIP foydalanuvchiga
    # alohida video sotib olish talabi chiqmasligi kerak.
    if await db.is_vip(user_id):
        return True

    return await db.has_purchased(user_id, video_id)

selected_qualities = {}

async def count_view_once(user_id, video_id):
    await db.count_view_once(user_id, video_id)


@dp.message(F.text, ~F.state, F.from_user.id != ADMIN_ID)
async def video_code_handler(message: types.Message):
    video = await db.get_video_by_code(message.text)
    if not video:
        await message.answer("Bunday video kodi topilmadi.")
        return
    
    text = f"{video[3]}\n\nKo'rishlar: {video[6]}"
    await message.answer_photo(
        video[2],
        caption=text,
        reply_markup=kb.video_post_kb(video[0]),
        protect_content=True
    )

@dp.callback_query(F.data.startswith("choose_quality_"))
async def choose_quality_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[2])

    qualities = await db.get_video_qualities(video_id)
    q_list = [q[0] for q in qualities]
    await call.message.edit_reply_markup(reply_markup=kb.quality_select_kb(video_id, q_list))

@dp.callback_query(F.data.startswith("quality_"))
async def quality_selected_handler(call: types.CallbackQuery):
    data = call.data.split("_")
    video_id = int(data[1])
    selected_quality = "_".join(data[2:])

    qualities = await db.get_video_qualities(video_id)

    # Tanlangan sifatga mos file_id ni topamiz
    selected_file_id = None
    for quality_name, file_id in qualities:
        if quality_name == selected_quality:
            selected_file_id = file_id
            break

    if not selected_file_id:
        await call.answer("Bu sifatdagi video topilmadi.", show_alert=True)
        return

    selected_qualities[(call.from_user.id, video_id)] = (selected_quality, selected_file_id)

    # VIP yoki video sotib olingan bo'lsa, sifat tanlangani zahoti video yuboriladi.
    if await user_can_watch_video(call.from_user.id, video_id):
        await call.answer(f"{selected_quality} tanlandi")
        await count_view_once(call.from_user.id, video_id)
        await send_video_with_likes(
            call,
            video_id,
            selected_quality,
            selected_file_id
        )
        return

    # Xarid qilmagan/VIP olmagan foydalanuvchi uchun esa video yuborilmaydi.
    await call.answer(f"{selected_quality} tanlandi")
    await call.message.edit_reply_markup(reply_markup=kb.video_post_kb(video_id))

@dp.callback_query(F.data.startswith("watch_video_"))
async def watch_video_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[2])
    
    if not await user_can_watch_video(call.from_user.id, video_id):
        await call.message.answer("Iltimos videoni ko'rish uchun oldin uni sotib oling yoki Vip tariflaridan birini xarid qiling!", reply_markup=kb.watch_video_buy_kb(video_id))
        return
        
    qualities = await db.get_video_qualities(video_id)
    if not qualities:
        await call.answer("Video topilmadi", show_alert=True)
        return
    
    selected = selected_qualities.get((call.from_user.id, video_id))
    q_name, file_id = selected if selected else qualities[0]

    await count_view_once(call.from_user.id, video_id)
    await send_video_with_likes(call, video_id, q_name, file_id)

@dp.callback_query(F.data.startswith("buy_video_"))
async def buy_video_handler(call: types.CallbackQuery):
    try:
        video_id = int(call.data.split("_")[2])
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri video.", show_alert=True)
        return
    video = await db.get_video(video_id)
    if not video:
        await call.answer("Video topilmadi.", show_alert=True)
        return
    if await db.is_vip(call.from_user.id) or await db.has_purchased(call.from_user.id, video_id):
        await call.answer("Sizda bu videoga kirish huquqi allaqachon mavjud.", show_alert=True)
        return
    card = await db.get_setting("card")
    text = (f"Ajoyib tanlov quyidagi karta raqamga belgilangan to'lovni amalga oshiring va pastdagi to'lov qildim tugmasini bosib chekni skrinshot qilib botga jo'nating!\n"
            f"Karta raqam {card}\n"
            f"Video narxi {video[5]} so'm\n"
            f"Eslatma: Siz faqat 1ta video uchun to'lov qilyabsiz va u videoni siz doimiy ko'raolasiz u sizning sotib olgan videolarim bo'limida saqlanadi.")
    await call.message.edit_text(text, reply_markup=kb.payment_done_kb("video", video_id))

async def send_video_with_likes(call, video_id, quality_name, file_id):
    # Yakuniy himoya: VIP yoki xarid bo'lmasa, video hech qaysi sifatda yuborilmaydi.
    if not await user_can_watch_video(call.from_user.id, video_id):
        await call.answer(
            "Bu videoni ko'rish uchun avval video sotib oling yoki VIP tarifini oling.",
            show_alert=True
        )
        return

    video = await db.get_video(video_id)
    likes, dislikes = await db.get_likes(video_id)
    text = f"{video[4]}\nSifati: {quality_name}\nKo'rishlar: {video[6]}"
    
    await call.message.delete()
    await call.message.answer_video(file_id, caption=text, reply_markup=kb.video_action_kb(video_id, likes, dislikes), protect_content=True)
    
    base_channel = await db.get_setting("base_channel")
    if base_channel:
        await call.message.answer("Yana boshqa videolar kodlarini olish uchun bizning kodlar kanalimizga o'ting!", reply_markup=kb.base_channel_kb(base_channel))

@dp.callback_query(F.data.startswith("change_quality_"))
async def change_quality_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[2])

    qualities = await db.get_video_qualities(video_id)
    q_list = [q[0] for q in qualities]
    current_q = call.message.caption.split("Sifati: ")[1].split("\n")[0] if "Sifati: " in call.message.caption else None
    await call.message.delete()
    await call.message.answer("Sifatini tanlang!", reply_markup=kb.quality_select_kb(video_id, q_list, exclude=current_q))

@dp.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def like_handler(call: types.CallbackQuery):
    action, video_id = call.data.split("_")
    video_id = int(video_id)
    is_like = 1 if action == "like" else 0
    
    prev_like = await db.has_liked(call.from_user.id, video_id)
    if prev_like == is_like:
        await call.answer("Siz allaqachon bosib bo'lgansiz!", show_alert=True)
        return
        
    await db.set_like(call.from_user.id, video_id, is_like)
    likes, dislikes = await db.get_likes(video_id)
    await call.message.edit_reply_markup(reply_markup=kb.video_action_kb(video_id, likes, dislikes))

# REKLAMA / BROADCAST
@dp.message(F.text == "📢 Reklama")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    await message.answer("Reklama posti uchun rasm jo'nating")
    await state.set_state(AdminBroadcast.waiting_for_photo)

@dp.message(AdminBroadcast.waiting_for_photo, F.photo)
async def broadcast_photo_handler(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("Endi reklama matnini yozing!")
    await state.set_state(AdminBroadcast.waiting_for_text)

@dp.message(AdminBroadcast.waiting_for_text, F.text)
async def broadcast_text_handler(message: types.Message, state: FSMContext):
    await state.update_data(ad_text=message.text)
    await message.answer("URL tugma uchun nom o'ylab toping!")
    await state.set_state(AdminBroadcast.waiting_for_button_name)

@dp.message(AdminBroadcast.waiting_for_button_name, F.text)
async def broadcast_button_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(button_name=message.text)
    await message.answer("URL tugma havolasini jo'nating!")
    await state.set_state(AdminBroadcast.waiting_for_button_url)

@dp.message(AdminBroadcast.waiting_for_button_url, F.text)
async def broadcast_button_url_handler(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith(("http://", "https://", "tg://")):
        await message.answer("Iltimos, to'g'ri URL havola yuboring.\nMasalan: https://t.me/username")
        return
    await state.update_data(button_url=url)
    await message.answer("Reklama kimlarga jo'natilsin?", reply_markup=kb.broadcast_target_kb())

async def _send_broadcast(target, data):
    users = await db.get_broadcast_users(target)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=data["button_name"], url=data["button_url"]) ]])
    sent = 0
    failed = 0
    for user_id in users:
        while True:
            try:
                await bot.send_photo(chat_id=user_id, photo=data["photo_id"], caption=data["ad_text"], reply_markup=keyboard, parse_mode=None)
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

@dp.callback_query(F.data.in_({"broadcast_regular", "broadcast_vip"}))
async def broadcast_target_handler(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    if not all(data.get(k) for k in ("photo_id", "ad_text", "button_name", "button_url")):
        await call.answer("Reklama ma'lumotlari to'liq emas.", show_alert=True)
        await state.clear()
        return
    target = "vip" if call.data == "broadcast_vip" else "regular"
    target_name = "VIP obunachilar" if target == "vip" else "oddiy obunachilar"
    await call.answer()
    await call.message.edit_text(f"📢 Reklama {target_name}ga yuborilmoqda...\nIltimos, kuting.")
    sent, failed, total = await _send_broadcast(target, data)
    await state.clear()
    await call.message.answer(f"✅ Reklama yuborish yakunlandi!\n\n👥 Auditoriya: {target_name}\n📋 Jami: {total} ta\n✅ Yetkazildi: {sent} ta\n❌ Yetkazilmadi: {failed} ta", reply_markup=kb.admin_main_kb())

# ADMIN HANDLERS
# =========================\n# 🎁 HADYALAR\n# =========================\nGIFT_TARIFFS = {1: "1 kunlik VIP", 7: "1 haftalik VIP", 30: "1 oylik VIP"}\n\n@dp.message(F.text == "🎁 Hadyalar")\nasync def gifts_menu_handler(message: types.Message, state: FSMContext):\n    if message.from_user.id != ADMIN_ID: return\n    await state.clear()\n    await message.answer("🎁 Hadyalar bo'limidasiz. Kimga sovg'a beramiz?", reply_markup=kb.gifts_main_kb())\n\n@dp.callback_query(F.data == "gift_back")\nasync def gift_back_handler(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    await state.clear()\n    await call.message.edit_text("🎁 Hadyalar bo'limidasiz. Kimga sovg'a beramiz?", reply_markup=kb.gifts_main_kb())\n\n# ---------- ID ORQALI ----------\n@dp.callback_query(F.data == "gift_by_id")\nasync def gift_by_id_start(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    await state.clear(); await call.message.edit_text("Foydalanuvchining ID raqamini jo'nating!"); await state.set_state(AdminGifts.waiting_for_user_id)\n\n@dp.message(AdminGifts.waiting_for_user_id, F.text)\nasync def gift_by_id_user(message: types.Message, state: FSMContext):\n    if message.from_user.id != ADMIN_ID: return\n    try:\n        uid=int(message.text.strip())\n        if uid <= 0: raise ValueError\n    except ValueError:\n        await message.answer("❌ Xato ID raqam! Iltimos, to'g'ri Telegram ID raqamini yuboring."); return\n    user=await db.get_user(uid)\n    if not user:\n        await message.answer("❌ Bunday ID raqamli obunachi topilmadi! Qaytadan yuboring."); return\n    await state.update_data(gift_user_id=uid)\n    await message.answer("VIP obuna tarifini tanlang!", reply_markup=kb.gift_tariffs_kb("gift_tariff"))\n    await state.set_state(AdminGifts.waiting_for_id_tariff)\n\n@dp.callback_query(AdminGifts.waiting_for_id_tariff, F.data.startswith("gift_tariff_"))\nasync def gift_id_tariff(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    days=int(call.data.rsplit("_",1)[1]); name=GIFT_TARIFFS[days]\n    await state.update_data(gift_days=days, gift_tariff=name)\n    await call.message.edit_text("🎁 Hadya qilganingizni tasdiqlang!", reply_markup=kb.gift_confirm_kb("gift_id_yes","gift_id_no"))\n    await state.set_state(AdminGifts.waiting_for_id_confirm)\n\n@dp.callback_query(F.data == "gift_id_no")\nasync def gift_id_no(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    await state.clear(); await call.message.edit_text("🎁 Hadyalar bo'limidasiz. Kimga sovg'a beramiz?", reply_markup=kb.gifts_main_kb())\n\n@dp.callback_query(F.data == "gift_id_yes")\nasync def gift_id_yes(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    data=await state.get_data(); uid=data.get("gift_user_id"); days=data.get("gift_days"); name=data.get("gift_tariff")\n    user=await db.get_user(uid) if uid else None\n    if not user:\n        await state.clear(); await call.message.edit_text("❌ Bunday ID raqamli obunachi topilmadi!", reply_markup=kb.gifts_main_kb()); return\n    await db.set_vip(uid,days)\n    try:\n        await bot.send_message(uid, f"🎁 Sizga bot adminlari tomonidan {name} hadya qilindi.\\nBemalol muddat tugagungacha botdan foydalanishingiz mumkin.")\n    except Exception as e:\n        logging.warning("ID gift notification failed: %s",e)\n    await state.clear(); await call.message.edit_text("Hadya egasiga topshirildi xo'jayin.", reply_markup=kb.gift_back_kb())\n\n# ---------- RANDOM ----------\n@dp.callback_query(F.data == "gift_random")\nasync def gift_random_start(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    await state.clear(); await call.message.edit_text("🎁 Hadya qilmoqchi bo'lgan VIP tarifini tanlang!", reply_markup=kb.gift_tariffs_kb("random_tariff")); await state.set_state(AdminGifts.waiting_for_random_tariff)\n\n@dp.callback_query(AdminGifts.waiting_for_random_tariff, F.data.startswith("random_tariff_"))\nasync def gift_random_tariff(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    days=int(call.data.rsplit("_",1)[1]); name=GIFT_TARIFFS[days]\n    await state.update_data(random_days=days, random_tariff=name); await call.message.edit_text("Nechta odam olishi mumkin sonini yozing!"); await state.set_state(AdminGifts.waiting_for_random_count)\n\n@dp.message(AdminGifts.waiting_for_random_count, F.text)\nasync def gift_random_count(message: types.Message, state: FSMContext):\n    if message.from_user.id != ADMIN_ID: return\n    try:\n        count=int(message.text.strip())\n        if count<=0: raise ValueError\n    except ValueError:\n        await message.answer("❌ Odamlar sonini 1 yoki undan katta butun son qilib yuboring."); return\n    await state.update_data(random_count=count); await message.answer("🎁 Hadyani jo'nataverymi xo'jayin?", reply_markup=kb.gift_confirm_kb("gift_random_yes","gift_random_no")); await state.set_state(AdminGifts.waiting_for_random_confirm)\n\n@dp.callback_query(F.data == "gift_random_no")\nasync def gift_random_no(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    await state.clear(); await call.message.edit_text("🎁 Hadyalar bo'limidasiz. Kimga sovg'a beramiz?", reply_markup=kb.gifts_main_kb())\n\n@dp.callback_query(F.data == "gift_random_yes")\nasync def gift_random_yes(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    data=await state.get_data(); days=data.get("random_days"); name=data.get("random_tariff"); limit=data.get("random_count")\n    if not days or not name or not limit:\n        await state.clear(); await call.message.edit_text("❌ Hadya ma'lumotlari topilmadi.", reply_markup=kb.gifts_main_kb()); return\n    gift_id=await db.create_gift_campaign(days,name,limit)\n    await call.message.edit_text("🎁 Hadyalar jo'natilmoqda...\\nIltimos, kuting.")\n    users=await db.get_non_vip_users(); sent=failed=0\n    text=f"🎁 Adminlar obunachilar uchun tekinga {name} sovg'a qilishmoqchi.\\nShoshiling! Sovg'a faqatgina {limit} odamga nasib qiladi, omadingizni qo'ldan chiqarmang!"\n    for uid in users:\n        try:\n            await bot.send_message(uid,text,reply_markup=kb.gift_claim_kb(gift_id)); sent+=1; await asyncio.sleep(0.05)\n        except TelegramRetryAfter as e:\n            await asyncio.sleep(e.retry_after);\n            try:\n                await bot.send_message(uid,text,reply_markup=kb.gift_claim_kb(gift_id)); sent+=1\n            except Exception: failed+=1\n        except Exception as e:\n            failed+=1; logging.warning("Random gift send failed user_id=%s: %s",uid,e)\n    await state.clear(); await call.message.answer(f"Hadyalar jo'natildi.\\n\\n📨 Yuborildi: {sent} ta\\n❌ Yetkazilmadi: {failed} ta",reply_markup=kb.gift_back_kb())\n\n@dp.callback_query(F.data.startswith("claim_gift_"))\nasync def claim_gift_handler(call: types.CallbackQuery):\n    gift_id=int(call.data.rsplit("_",1)[1]); status,campaign=await db.claim_gift(gift_id,call.from_user.id)\n    if status=="won":\n        await db.set_vip(call.from_user.id,campaign[1])\n        await call.answer("🎉 Tabriklaymiz siz sovg'ani qo'lga kiritdingiz",show_alert=True)\n        if campaign[4] >= campaign[3] and await db.mark_gift_completed_notified(gift_id):\n            winners=await db.get_gift_winners(gift_id)\n            lines=[f"🎁 Hadyalarni olgan obunachilar\\n\\n💎 Tarif: {campaign[2]}\\n👥 Jami: {len(winners)} ta\\n"]\n            for i,(uid,name,username) in enumerate(winners,1):\n                who=name or "User"; uname=f"@{username}" if username else "username yo'q"\n                lines.append(f"{i}. {who} — {uname} — ID: {uid}")\n            await bot.send_message(ADMIN_ID,"\\n".join(lines))\n    elif status=="vip":\n        await call.answer("❌ Sizda allaqachon faol VIP obuna bor.",show_alert=True)\n    elif status=="already":\n        await call.answer("❌ Siz bu sovg'ani allaqachon olgansiz.",show_alert=True)\n    elif status=="not_found":\n        await call.answer("❌ Siz botda ro'yxatdan o'tmagansiz.",show_alert=True)\n    else:\n        await call.answer("Afsuski siz ulgurmadingiz keyingi giftda faolroq bo'ling!",show_alert=True)\n\n# ---------- VIPNI QAYTARISH ----------\n@dp.callback_query(F.data == "gift_revoke")\nasync def gift_revoke_start(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    await state.clear(); await call.message.edit_text("Kimdan VIPni olib qo'ymoqchisiz ID raqamini yuboring!"); await state.set_state(AdminGifts.waiting_for_revoke_id)\n\n@dp.message(AdminGifts.waiting_for_revoke_id, F.text)\nasync def gift_revoke_id(message: types.Message, state: FSMContext):\n    if message.from_user.id != ADMIN_ID: return\n    try:\n        uid=int(message.text.strip())\n        if uid<=0: raise ValueError\n    except ValueError:\n        await message.answer("❌ Xato ID raqam! Iltimos, to'g'ri Telegram ID raqamini yuboring."); return\n    user=await db.get_user(uid)\n    if not user:\n        await message.answer("❌ Bunday ID raqamli obunachi topilmadi! Qaytadan yuboring."); return\n    if not await db.is_vip(uid):\n        await message.answer("❌ Bu foydalanuvchida faol VIP obuna mavjud emas."); return\n    await state.update_data(revoke_user_id=uid); await message.answer("Haqiqatdan ham olib qo'ymoqchimisiz?",reply_markup=kb.gift_confirm_kb("gift_revoke_yes","gift_revoke_no")); await state.set_state(AdminGifts.waiting_for_revoke_confirm)\n\n@dp.callback_query(F.data == "gift_revoke_no")\nasync def gift_revoke_no(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    await state.clear(); await call.message.edit_text("🎁 Hadyalar bo'limidasiz. Kimga sovg'a beramiz?",reply_markup=kb.gifts_main_kb())\n\n@dp.callback_query(F.data == "gift_revoke_yes")\nasync def gift_revoke_yes(call: types.CallbackQuery, state: FSMContext):\n    if call.from_user.id != ADMIN_ID: return\n    data=await state.get_data(); uid=data.get("revoke_user_id"); result=await db.revoke_vip(uid); await state.clear()\n    if result=="revoked": text="✅ VIP olib tashlandi xo'jayin."\n    elif result=="no_vip": text="❌ Bu foydalanuvchida faol VIP obuna mavjud emas."\n    else: text="❌ Bunday ID raqamli obunachi topilmadi!"\n    await call.message.edit_text(text,reply_markup=kb.gift_back_kb())\n\n
@dp.message(F.text == "Video qo‘shish")
async def add_video_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Video muqovasi uchun rasm jo'nating!")
    await state.set_state(AdminAddVideo.waiting_for_cover)

@dp.message(AdminAddVideo.waiting_for_cover, F.photo)
async def add_video_cover(message: types.Message, state: FSMContext):
    await state.update_data(cover=message.photo[-1].file_id)
    await message.answer("Video posti uchun izoh yozing!")
    await state.set_state(AdminAddVideo.waiting_for_post_desc)

@dp.message(AdminAddVideo.waiting_for_post_desc, F.text)
async def add_video_post_desc(message: types.Message, state: FSMContext):
    await state.update_data(post_desc=message.text)
    await message.answer("Asosiy video uchun izoh yozing!")
    await state.set_state(AdminAddVideo.waiting_for_main_desc)

@dp.message(AdminAddVideo.waiting_for_main_desc, F.text)
async def add_video_main_desc(message: types.Message, state: FSMContext):
    await state.update_data(main_desc=message.text)
    await message.answer("Video uchun narx belgilang!\nMasalan: 5000")
    await state.set_state(AdminAddVideo.waiting_for_price)

@dp.message(AdminAddVideo.waiting_for_price, F.text)
async def add_video_price(message: types.Message, state: FSMContext):
    raw_price = message.text.strip().replace(" ", "").replace("_", "")
    if not raw_price.isdigit() or int(raw_price) <= 0:
        await message.answer("Iltimos, narxni faqat musbat raqam bilan kiriting. Masalan: 5000")
        return
    await state.update_data(price=int(raw_price), qualities={})
    await message.answer("Video sifatini belgilang!", reply_markup=kb.admin_quality_select_kb([]))
    await state.set_state(AdminAddVideo.waiting_for_quality_select)

@dp.callback_query(AdminAddVideo.waiting_for_quality_select, F.data.startswith("addq_"))
async def add_video_quality_select(call: types.CallbackQuery, state: FSMContext):
    q = call.data.split("_")[1]
    if q == "done":
        await call.message.edit_text("Video uchun kalit kodni yozing!")
        await state.set_state(AdminAddVideo.waiting_for_code)
    else:
        await state.update_data(current_q=q)
        await call.message.edit_text(f"Endi shu sifatdagi ({q}) videoni jo'nating!")
        await state.set_state(AdminAddVideo.waiting_for_video_file)

@dp.message(AdminAddVideo.waiting_for_video_file, F.video)
async def add_video_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    qualities = data.get('qualities', {})
    current_q = data['current_q']
    qualities[current_q] = message.video.file_id
    await state.update_data(qualities=qualities)
    
    await message.answer("Video qabul qilindi yana boshqa sifat qo'shasizmi?", reply_markup=kb.admin_quality_select_kb(list(qualities.keys())))
    await state.set_state(AdminAddVideo.waiting_for_quality_select)

@dp.message(AdminAddVideo.waiting_for_code, F.text)
async def add_video_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_id = await db.add_video(message.text, data['cover'], data['post_desc'], data['main_desc'], data['price'])
    for q, file_id in data['qualities'].items():
        await db.add_video_quality(video_id, q, file_id)
    
    await message.answer("Video muvaffaqiyatli qo'shildi xo'jayin")
    await state.clear()

@dp.message(F.text == "Video o'chirish")
async def delete_video_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("O'chirmoqchi bo'lgan videongizni kodini yozing!")
    await state.set_state(AdminDeleteVideo.waiting_for_code)

@dp.message(AdminDeleteVideo.waiting_for_code, F.text)
async def delete_video_code(message: types.Message, state: FSMContext):
    code = message.text
    video = await db.get_video_by_code(code)
    if not video:
        await message.answer("Video topilmadi.")
        await state.clear()
        return
    await state.update_data(code=code)
    await message.answer("Chindan ham shu videoni o'chirmoqchimisiz?", reply_markup=kb.confirm_kb("delvid"))

@dp.callback_query(F.data == "yes_delvid")
async def confirm_delete_video(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.delete_video(data['code'])
    await call.message.edit_text("Video muvaffaqiyatli o'chirildi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="admin_back")]]))
    await state.clear()

@dp.callback_query(F.data == "no_action")
async def no_action_handler(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("Bosh menyu", reply_markup=kb.admin_main_kb())

@dp.message(F.text == "Statistika")
async def stats_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    total_users = await db.get_total_users()
    vip_users = await db.get_vip_users_count()
    total_purchased = await db.get_purchased_videos_count()
    
    text = (f"Botga qo'shilgan odamlar soni: {total_users}\n"
            f"Vip obunasi bor obunachilar soni: {vip_users}\n"
            f"Sotib olingan videolar soni: {total_purchased}")
    await message.answer(text)

@dp.message(F.text == "Sozlamalar")
async def settings_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Mana barcha sozlamalar xo'jayin", reply_markup=kb.admin_settings_kb())

@dp.callback_query(F.data == "admin_back")
async def admin_back_handler(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("Admin panel", reply_markup=kb.admin_main_kb())

@dp.callback_query(F.data == "set_channels")
async def set_channels_handler(call: types.CallbackQuery):
    await call.message.edit_text("Kanallar bo'limidasiz", reply_markup=kb.admin_channels_kb())

@dp.callback_query(F.data == "settings_back")
async def settings_back_handler(call: types.CallbackQuery):
    await call.message.edit_text("Mana barcha sozlamalar xo'jayin", reply_markup=kb.admin_settings_kb())

@dp.callback_query(F.data == "set_basechannel")
async def set_basechannel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Baza kanal havolasini jo'nating!")
    await state.set_state(AdminSettings.waiting_for_base_channel)

@dp.message(AdminSettings.waiting_for_base_channel, F.text)
async def set_basechannel_save(message: types.Message, state: FSMContext):
    await db.set_setting("base_channel", message.text)
    await message.answer("Kanal muvaffaqiyatli qo'shildi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    await state.clear()

@dp.callback_query(F.data == "set_mandatorychannel")
async def set_mandatorychannel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Botni kanalga admin qilib tayinlang va kanaldagi postlardan birini botga jo'nating!")
    await state.set_state(AdminSettings.waiting_for_mandatory_channel)

@dp.message(AdminSettings.waiting_for_mandatory_channel)
async def set_mandatorychannel_save(message: types.Message, state: FSMContext):
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        url = f"https://t.me/{message.forward_from_chat.username}" if message.forward_from_chat.username else "Private channel"
        await db.add_channel(chat_id, url, 1)
        await message.answer("Kanal muvaffaqiyatli qo'shildi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    else:
        await message.answer("Iltimos kanaldan post jo'nating.")
    await state.clear()

@dp.callback_query(F.data == "del_channels")
async def del_channels_list(call: types.CallbackQuery):
    channels = await db.get_all_channels()
    builder = kb.InlineKeyboardBuilder()
    for ch in channels:
        name = "Majburiy" if ch[3] else "Baza"
        builder.button(text=f"{name} kanal", callback_data=f"delch_{ch[0]}")
    builder.adjust(1)
    await call.message.edit_text("Barcha kanallar", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("delch_"))
async def del_channels_confirm(call: types.CallbackQuery, state: FSMContext):
    ch_id = call.data.split("_")[1]
    await state.update_data(del_ch_id=ch_id)
    await call.message.edit_text("Haqiqatdan ham shu kanalni o'chirishni hoxlaysizmi?", reply_markup=kb.confirm_kb("delch"))

@dp.callback_query(F.data == "yes_delch")
async def del_channels_yes(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.delete_channel(data['del_ch_id'])
    await call.message.edit_text("Kanal muvaffaqiyatli o'chirildi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    await state.clear()

@dp.callback_query(F.data == "set_card")
async def set_card_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Karta raqamingizni jo'nating!")
    await state.set_state(AdminSettings.waiting_for_card_number)

@dp.message(AdminSettings.waiting_for_card_number, F.text)
async def set_card_save(message: types.Message, state: FSMContext):
    await db.set_setting("card", message.text)
    await message.answer("Karta raqam muvaffaqiyatli saqlandi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    await state.clear()
    
@dp.callback_query(F.data == "set_adminlink")
async def set_adminlink_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Havolani jo'nating!")
    await state.set_state(AdminSettings.waiting_for_admin_link)

@dp.message(AdminSettings.waiting_for_admin_link, F.text)
async def set_adminlink_save(message: types.Message, state: FSMContext):
    await db.set_setting("admin_link", message.text)
    await message.answer("Havola saqlandi", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    await state.clear()

async def main():
    await db.connect()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
