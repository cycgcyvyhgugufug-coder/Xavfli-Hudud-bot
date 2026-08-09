import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile
import math

from config import BOT_TOKEN, ADMIN_ID
from db import Database
import keyboards as kb
from states import AdminAddVideo, AdminDeleteVideo, AdminSettings, UserPayment

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
        except:
            pass # Bot might not be admin, ignore for now
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
@dp.message(F.text == "Kabinet")
async def cabinet_handler(message: types.Message):
    user = await db.get_user(message.from_user.id)
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
    admin_link = await db.get_setting("admin_link")
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Bog'lanish", url=f"https://t.me/{admin_link.replace('@', '')}")],
        [types.InlineKeyboardButton(text="Orqaga", callback_data="main_menu")]
    ])
    await message.answer("Agar sizda muammolar yoki qanaqadur savollar paydo bo'lgan bo'lsa admin bilan bo'g'lanishingiz mumkin", reply_markup=markup)

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
    data = call.data.split("_")
    user_id = int(data[1])
    item_type = data[2]
    item_id = int(data[3])

    if item_type == "vip":
        await db.set_vip(user_id, item_id)
        await bot.send_message(user_id, "Tabriklaymiz to'lovingiz tasdiqlanadi endi botdan bemalol foydalanishingiz mumkin, ko'rmoqchi bo'lgan videongizni kodini yozing!")
    elif item_type == "video":
        await db.add_purchase(user_id, item_id)
        await bot.send_message(user_id, "Tabriklaymiz to'lovingiz tasdiqlandi, endi videoni ko'rishingiz mumkin. Kodingizni yozing!")
    
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ TASDIQLANGAN")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_handler(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
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

@dp.message(F.text, ~F.state, F.from_user.id != ADMIN_ID)
async def video_code_handler(message: types.Message):
    video = await db.get_video_by_code(message.text)
    if not video:
        await message.answer("Bunday video kodi topilmadi.")
        return
    
    await db.increment_views(video[0])
    text = f"{video[3]}\n\nKo'rishlar: {video[6]+1}"
    await message.answer_photo(video[2], caption=text, reply_markup=kb.video_post_kb(video[0]), protect_content=True)

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

    await call.answer()
    await send_video_with_likes(
        call,
        video_id,
        selected_quality,
        selected_file_id
    )

@dp.callback_query(F.data.startswith("watch_video_"))
async def watch_video_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[2])
    
    is_vip = await db.is_vip(call.from_user.id)
    has_purchased = await db.has_purchased(call.from_user.id, video_id)
    
    if not is_vip and not has_purchased:
        await call.message.answer("Iltimos videoni ko'rish uchun oldin uni sotib oling yoki Vip tariflaridan birini xarid qiling!", reply_markup=kb.watch_video_buy_kb(video_id))
        return
        
    qualities = await db.get_video_qualities(video_id)
    if not qualities:
        await call.answer("Video topilmadi", show_alert=True)
        return
    
    # Agar foydalanuvchi alohida sifat tanlamagan bo'lsa,
    # birinchi qo'shilgan sifat standart sifatida yuboriladi.
    q_name, file_id = qualities[0]
    await send_video_with_likes(call, video_id, q_name, file_id)

@dp.callback_query(F.data.startswith("buy_video_"))
async def buy_video_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[2])
    video = await db.get_video(video_id)
    card = await db.get_setting("card")
    text = (f"Ajoyib tanlov quyidagi karta raqamga belgilangan to'lovni amalga oshiring va pastdagi to'lov qildim tugmasini bosib chekni skrinshot qilib botga jo'nating!\n"
            f"Karta raqam {card}\n"
            f"Video narxi {video[5]} so'm\n"
            f"Eslatma: Siz faqat 1ta video uchun to'lov qilyabsiz va u videoni siz doimiy ko'raolasiz u sizning sotib olgan videolarim bo'limida saqlanadi.")
    await call.message.edit_text(text, reply_markup=kb.payment_done_kb("video", video_id))

async def send_video_with_likes(call, video_id, quality_name, file_id):
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

# ADMIN HANDLERS
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
    await state.update_data(price=int(message.text), qualities={})
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
    await call.message.edit_text("Video muvaffaqiyatli o'chirildi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="main_menu")]]))
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
