import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile
import math

from config import BOT_TOKEN, ADMIN_ID
from db import Database
import keyboards as kb
from states import AdminSettings, AddVideo, UserBuy

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
db = Database()

# ADMIN HANDLERS
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Assalomu alaykum, Admin! Bot boshqaruv paneliga xush kelibsiz.", reply_markup=kb.admin_main_kb())
    else:
        await db.add_user(message.from_user.id)
        await message.answer("Assalomu alaykum! Kerakli bo'limni tanlang:", reply_markup=kb.user_main_kb())

@dp.message(Command("data"))
async def get_data_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    db_file = FSInputFile("bot.db")
    await message.answer_document(db_file, caption="Botning ma'lumotlar bazasi")

# USER HANDLERS
@dp.message(F.text == "Kabinet")
async def cabinet_handler(message: types.Message):
    count = await db.get_user_purchased_count(message.from_user.id)
    text = f"Sizning ID: {message.from_user.id}\nSotib olgan videolaringiz soni: {count} ta"
    await message.answer(text, reply_markup=kb.user_main_kb())

@dp.message(F.text == "Sotib olingan videolar")
async def purchased_videos_handler(message: types.Message):
    videos = await db.get_user_purchased_videos(message.from_user.id)
    if not videos:
        await message.answer("Siz hali hech qanday video sotib olmagansiz.")
        return
    
    text = "Sotib olingan videolar ro'yxati:\n\n"
    for v in videos:
        text += f"ID: {v[0]} - {v[1]}\n"
    
    text += "\nKodni yuborish orqali videoni ko'rishingiz mumkin."
    await message.answer(text)

@dp.message(F.text == "Barcha videolar")
async def all_videos_handler(message: types.Message):
    videos = await db.get_all_videos()
    if not videos:
        await message.answer("Hozircha videolar yo'q.")
        return
    
    text = "Barcha videolar ro'yxati:\n\n"
    for v in videos:
        text += f"ID: {v[0]} - {v[1]} - {v[2]} so'm\n"
    
    text += "\nKodni yuborish orqali videoni ko'rishingiz mumkin."
    await message.answer(text)

@dp.message(F.text == "Admin")
async def contact_admin_handler(message: types.Message):
    admin_link = await db.get_setting("admin_link")
    if admin_link:
        text = f"Admin bilan bog'lanish: {admin_link}"
    else:
        text = "Admin bilan bog'lanish uchun havola topilmadi."
    await message.answer(text)

@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(call: types.CallbackQuery):
    channels = await db.get_mandatory_channels()
    all_subscribed = True
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch[1], call.from_user.id)
            if member.status in ['left', 'kicked']:
                all_subscribed = False
                break
        except Exception:
            pass
            
    if all_subscribed:
        await call.message.delete()
        await call.message.answer("Siz barcha kanallarga obuna bo'ldingiz. Endi botdan to'liq foydalanishingiz mumkin!", reply_markup=kb.user_main_kb())
    else:
        await call.answer("Hali barcha kanallarga obuna bo'lmapsiz!", show_alert=True)

async def check_user_subscription(user_id: int):
    channels = await db.get_mandatory_channels()
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch[1], user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

@dp.message(F.text.isdigit())
async def process_video_code(message: types.Message):
    video_id = int(message.text)
    video = await db.get_video(video_id)
    
    if not video:
        await message.answer("Bunday kodli video topilmadi.")
        return
        
    is_subscribed = await check_user_subscription(message.from_user.id)
    if not is_subscribed:
        channels = await db.get_mandatory_channels()
        if channels:
            await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=kb.subscription_kb(channels))
            return
            
    has_purchased = await db.has_user_purchased(message.from_user.id, video_id)
    
    if has_purchased or message.from_user.id == ADMIN_ID:
        await db.increment_views(video_id)
        text = f"{video[3]}\n\nKo'rishlar: {video[6]+1}"
        await message.answer_photo(video[2], caption=text, reply_markup=kb.video_post_kb(video_id), protect_content=True)
    else:
        card = await db.get_setting("card")
        if not card:
            await message.answer("Sotib olish uchun karta raqami kiritilmagan. Adminga murojaat qiling.")
            return
            
        text = f"Video nomi: {video[1]}\nNarxi: {video[4]} so'm\n\nTo'lov uchun karta: {card}\n\nTo'lov qilinganligini tasdiqlash uchun chekni shu yerga yuboring."
        await message.answer_photo(video[2], caption=text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Bekor qilish", callback_data="cancel_buy")]]))
        
@dp.callback_query(F.data.startswith("choose_quality_"))
async def choose_quality_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[2])
    video = await db.get_video(video_id)
    if not video:
        await call.answer("Video topilmadi", show_alert=True)
        return
        
    base_channel = await db.get_setting("base_channel")
    if not base_channel:
        await call.answer("Baza kanali ulanmagan. Adminga murojaat qiling.", show_alert=True)
        return
        
    await call.message.edit_reply_markup(reply_markup=kb.quality_kb(video_id))

@dp.callback_query(F.data.startswith("get_quality_"))
async def get_quality_video(call: types.CallbackQuery):
    parts = call.data.split("_")
    quality = parts[2]
    video_id = int(parts[3])
    
    video = await db.get_video(video_id)
    if not video:
        await call.answer("Video topilmadi", show_alert=True)
        return
        
    quality_name = ""
    file_id = ""
    if quality == "480":
        quality_name = "480p"
        file_id = video[7]
    elif quality == "720":
        quality_name = "720p"
        file_id = video[8]
    elif quality == "1080":
        quality_name = "1080p"
        file_id = video[9]
        
    if not file_id:
        await call.answer(f"Bu videoda {quality_name} sifati yo'q", show_alert=True)
        return
        
    likes = await db.get_video_likes(video_id)
    dislikes = await db.get_video_dislikes(video_id)
    
    text = f"{video[4]}\nSifati: {quality_name}\nKo'rishlar: {video[6]}"
    
    await call.message.delete()
    await call.message.answer_video(file_id, caption=text, reply_markup=kb.video_action_kb(video_id, likes, dislikes), protect_content=True)
    
    base_channel = await db.get_setting("base_channel")
    if base_channel:
        try:
            msg = await bot.send_video(chat_id=base_channel, video=file_id, caption=f"Foydalanuvchi: {call.from_user.id}\nVideo ID: {video_id}")
            await db.set_setting(f"last_forward_{call.from_user.id}", str(msg.message_id))
        except Exception as e:
            logging.error(f"Failed to forward to base channel: {e}")

@dp.callback_query(F.data.startswith("like_"))
async def like_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[1])
    # Simple logic for visual update (database logic can be expanded)
    await db.add_reaction(video_id, call.from_user.id, "like")
    likes = await db.get_video_likes(video_id)
    dislikes = await db.get_video_dislikes(video_id)
    await call.message.edit_reply_markup(reply_markup=kb.video_action_kb(video_id, likes, dislikes))
    await call.answer("Sizga yoqdi!")

@dp.callback_query(F.data.startswith("dislike_"))
async def dislike_handler(call: types.CallbackQuery):
    video_id = int(call.data.split("_")[1])
    await db.add_reaction(video_id, call.from_user.id, "dislike")
    likes = await db.get_video_likes(video_id)
    dislikes = await db.get_video_dislikes(video_id)
    await call.message.edit_reply_markup(reply_markup=kb.video_action_kb(video_id, likes, dislikes))
    await call.answer("Sizga yoqmadi!")

@dp.message(F.photo)
async def payment_receipt_handler(message: types.Message):
    # This implies the user is sending a photo while they were asked to pay
    # In a real scenario, state management is better, but this works for simple flows
    if message.from_user.id == ADMIN_ID:
        return
        
    # Ask admin to verify
    caption = f"Yangi to'lov cheki!\nFoydalanuvchi ID: {message.from_user.id}\nUsername: @{message.from_user.username}"
    # Send to admin
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Tasdiqlash", callback_data=f"approve_{message.from_user.id}"),
            types.InlineKeyboardButton(text="Bekor qilish", callback_data=f"reject_{message.from_user.id}")
        ]
    ]))
    await message.answer("Chek adminga yuborildi. Tasdiqlanishini kuting.")

@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
        
    user_id = int(call.data.split("_")[1])
    # The exact video_id they were trying to buy should be stored in state, 
    # but for simplicity, we ask the admin to enter the video ID
    await state.set_state(AdminSettings.waiting_for_approve_video_id)
    await state.update_data(approve_user_id=user_id)
    await call.message.answer("Qaysi video ID uchun ruxsat beryapsiz? Kodni yozing:")

@dp.message(AdminSettings.waiting_for_approve_video_id, F.text.isdigit())
async def process_approve_video_id(message: types.Message, state: FSMContext):
    video_id = int(message.text)
    data = await state.get_data()
    user_id = data.get("approve_user_id")
    
    await db.add_purchase(user_id, video_id)
    await message.answer(f"{user_id} ga {video_id} - videoga ruxsat berildi.")
    
    try:
        await bot.send_message(user_id, f"Tabriklaymiz! Sizning to'lovingiz tasdiqlandi.\nEndi botga {video_id} kodini yuborib videoni ko'rishingiz mumkin.")
    except:
        pass
        
    await state.clear()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
        
    user_id = int(call.data.split("_")[1])
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("Bekor qilindi.")
    
    try:
        await bot.send_message(user_id, "Kechirasiz, sizning to'lovingiz tasdiqlanmadi. Qayta urinib ko'ring yoki adminga murojaat qiling.")
    except:
        pass

# ADMIN SETTINGS HANDLERS
@dp.message(F.text == "Sozlamalar", F.from_user.id == ADMIN_ID)
async def settings_handler(message: types.Message):
    await message.answer("Sozlamalar bo'limi", reply_markup=kb.admin_settings_kb())

@dp.callback_query(F.data == "settings_back")
async def settings_back(call: types.CallbackQuery):
    await call.message.edit_text("Sozlamalar bo'limi", reply_markup=kb.admin_settings_kb())

@dp.callback_query(F.data == "set_channels")
async def set_channels_start(call: types.CallbackQuery):
    channels = await db.get_mandatory_channels()
    text = "Majburiy obuna kanallari:\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. {ch[0]} - {ch[1]}\n"
        
    text += "\nYangi kanal qo'shish uchun pastdagi tugmani bosing."
    await call.message.edit_text(text, reply_markup=kb.admin_channel_settings_kb())

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Kanal nomini kiriting:")
    await state.set_state(AdminSettings.waiting_for_channel_name)

@dp.message(AdminSettings.waiting_for_channel_name, F.text)
async def add_channel_name(message: types.Message, state: FSMContext):
    await state.update_data(channel_name=message.text)
    await message.answer("Endi kanal linkini yoki ID sini kiriting (@ bilan):")
    await state.set_state(AdminSettings.waiting_for_channel_link)

@dp.message(AdminSettings.waiting_for_channel_link, F.text)
async def add_channel_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data['channel_name']
    link = message.text
    
    await db.add_mandatory_channel(name, link)
    await message.answer("Kanal muvaffaqiyatli qo'shildi!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="set_channels")]]))
    await state.clear()

@dp.callback_query(F.data == "del_channel")
async def del_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("O'chirish uchun kanal ID sini kiriting (bazadagi ID):")
    await state.set_state(AdminSettings.waiting_for_channel_del_id)

@dp.message(AdminSettings.waiting_for_channel_del_id, F.text.isdigit())
async def del_channel_process(message: types.Message, state: FSMContext):
    await db.delete_mandatory_channel(int(message.text))
    await message.answer("Kanal o'chirildi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="set_channels")]]))
    await state.clear()

@dp.callback_query(F.data == "set_base_channel")
async def set_base_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Baza kanali ID sini kiriting (Masalan: -100123456789):")
    await state.set_state(AdminSettings.waiting_for_base_channel)

@dp.message(AdminSettings.waiting_for_base_channel, F.text)
async def process_base_channel(message: types.Message, state: FSMContext):
    await db.set_setting("base_channel", message.text)
    await message.answer("Baza kanali saqlandi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    await state.clear()

@dp.callback_query(F.data == "add_video")
async def add_video_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Video qo'shish jarayoni.\n\nVideo nomini kiriting:")
    await state.set_state(AddVideo.waiting_for_name)

@dp.message(AddVideo.waiting_for_name, F.text)
async def add_video_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Video narxini kiriting (faqat raqamda, so'mda):")
    await state.set_state(AddVideo.waiting_for_price)

@dp.message(AddVideo.waiting_for_price, F.text.isdigit())
async def add_video_price(message: types.Message, state: FSMContext):
    await state.update_data(price=int(message.text))
    await message.answer("Video postidagi yozuvni (description) kiriting:")
    await state.set_state(AddVideo.waiting_for_desc)

@dp.message(AddVideo.waiting_for_desc, F.text)
async def add_video_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Video ichidagi yozuvni kiriting:")
    await state.set_state(AddVideo.waiting_for_video_desc)

@dp.message(AddVideo.waiting_for_video_desc, F.text)
async def add_video_video_desc(message: types.Message, state: FSMContext):
    await state.update_data(video_desc=message.text)
    await message.answer("Post uchun rasm yuboring:")
    await state.set_state(AddVideo.waiting_for_image)

@dp.message(AddVideo.waiting_for_image, F.photo)
async def add_video_image(message: types.Message, state: FSMContext):
    await state.update_data(image_id=message.photo[-1].file_id)
    await message.answer("Endi 480p sifatdagi videoni yuboring (agar yo'q bo'lsa 0 deb yozing):")
    await state.set_state(AddVideo.waiting_for_video_480)

@dp.message(AddVideo.waiting_for_video_480, F.video)
async def add_video_480(message: types.Message, state: FSMContext):
    await state.update_data(video_480=message.video.file_id)
    await message.answer("Endi 720p sifatdagi videoni yuboring (agar yo'q bo'lsa 0 deb yozing):")
    await state.set_state(AddVideo.waiting_for_video_720)

@dp.message(AddVideo.waiting_for_video_480, F.text == "0")
async def add_video_480_skip(message: types.Message, state: FSMContext):
    await state.update_data(video_480=None)
    await message.answer("Endi 720p sifatdagi videoni yuboring (agar yo'q bo'lsa 0 deb yozing):")
    await state.set_state(AddVideo.waiting_for_video_720)

@dp.message(AddVideo.waiting_for_video_720, F.video)
async def add_video_720(message: types.Message, state: FSMContext):
    await state.update_data(video_720=message.video.file_id)
    await message.answer("Endi 1080p sifatdagi videoni yuboring (agar yo'q bo'lsa 0 deb yozing):")
    await state.set_state(AddVideo.waiting_for_video_1080)

@dp.message(AddVideo.waiting_for_video_720, F.text == "0")
async def add_video_720_skip(message: types.Message, state: FSMContext):
    await state.update_data(video_720=None)
    await message.answer("Endi 1080p sifatdagi videoni yuboring (agar yo'q bo'lsa 0 deb yozing):")
    await state.set_state(AddVideo.waiting_for_video_1080)

@dp.message(AddVideo.waiting_for_video_1080, F.video)
async def add_video_1080(message: types.Message, state: FSMContext):
    await state.update_data(video_1080=message.video.file_id)
    await save_video_data(message, state)

@dp.message(AddVideo.waiting_for_video_1080, F.text == "0")
async def add_video_1080_skip(message: types.Message, state: FSMContext):
    await state.update_data(video_1080=None)
    await save_video_data(message, state)

async def save_video_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_id = await db.add_video(
        data['name'], 
        data['image_id'], 
        data['desc'], 
        data['price'], 
        data['video_desc'],
        data.get('video_480'),
        data.get('video_720'),
        data.get('video_1080')
    )
    await message.answer(f"Video muvaffaqiyatli saqlandi!\n\nVideo ID (kodi): {video_id}", reply_markup=kb.admin_main_kb())
    await state.clear()

@dp.callback_query(F.data == "set_card")
async def set_card_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Karta raqamingizni jo'nating!")
    await state.set_state(AdminSettings.waiting_for_card_number)

@dp.message(AdminSettings.waiting_for_card_number, F.text)
async def process_card_number(message: types.Message, state: FSMContext):
    await db.set_setting("card", message.text)
    await message.answer("Karta raqam muvaffaqiyatli saqlandi.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    await state.clear()
    
@dp.callback_query(F.data == "set_adminlink")
async def set_adminlink_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Havolani jo'nating!")
    await state.set_state(AdminSettings.waiting_for_admin_link)

@dp.message(AdminSettings.waiting_for_admin_link, F.text)
async def process_adminlink(message: types.Message, state: FSMContext):
    await db.set_setting("admin_link", message.text)
    await message.answer("Havola saqlandi", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Orqaga", callback_data="settings_back")]]))
    await state.clear()

async def main():
    await db.create_tables()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
