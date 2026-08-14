
import asyncio, logging, os, re, shutil, tempfile, zipfile
from datetime import datetime
from aiogram import Bot,Dispatcher,F,types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError,TelegramRetryAfter
from aiogram.types import FSInputFile
from config import BOT_TOKEN,ADMIN_ID
from db import Database
import keyboards as kb
from states import UserPayment,AdminVideo,AdminSettings,AdminBroadcast,AdminGift

logging.basicConfig(level=logging.INFO)
bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode="HTML"))
dp=Dispatcher()
db=Database()
STATE_FILE="bot.db"

def is_root(uid): return uid==ADMIN_ID

async def is_admin(uid):
    return is_root(uid) or bool(await db.admin(uid))

async def can_manage_admins(uid):
    if is_root(uid): return True
    a=await db.admin(uid)
    return bool(a and a["role"]=="admin")

async def ensure_user(m):
    await db.add_user(m.from_user.id,m.from_user.first_name,m.from_user.username)

async def blocked(uid):
    return await db.is_blocked(uid)

async def sub_ok(uid):
    channels=await db.channels()
    for c in channels:
        try:
            member=await bot.get_chat_member(c["channel_id"],uid)
            if member.status in ("left","kicked","restricted"): return False
        except Exception:
            return False
    return True

async def welcome(m):
    await m.answer(
        f"Salom {m.from_user.first_name}, Xavfli Hududga xush kelibsiz.\n\n"
        "Ko'rmoqchi bo'lgan videongiz kodini jo'nating yoki o'zingizga kerak bo'lgan bo'limlardan birini tanlang!",
        reply_markup=kb.main_kb()
    )

async def process_referral(m):
    text=m.text or ""
    parts=text.split(maxsplit=1)
    if len(parts)!=2 or not parts[1].startswith("ref_"): return
    raw=parts[1][4:]
    if not raw.isdigit(): return
    ref=int(raw)
    if ref==m.from_user.id or not await db.get_user(ref): return
    reward=int(await db.get_setting("referral_reward") or 500)
    if await db.add_referral(m.from_user.id,ref,reward):
        u=await db.get_user(m.from_user.id)
        await bot.send_message(ref,
            f"Siz {u['name']} ni qo'shdingiz, sizga {reward:,} so'm berildi.\n"
            f"Do'stingiz IDsi: {m.from_user.id}".replace(","," ")
        )
        await bot.send_message(ADMIN_ID,
            f"Yangi obunachi\n\nIsmi: {u['name']}\n"
            f"Useri: @{u['username'] or 'yoq'}\nIDsi: {m.from_user.id}\n\n"
            f"Referral orqali qo'shildi\nTaklif qilgan odam: {ref}"
        )

@dp.message(Command("start"))
async def start(m:types.Message):
    if await blocked(m.from_user.id): return
    if is_root(m.from_user.id):
        await m.answer("Salom xo'jayin, nima ish qilamiz?",reply_markup=kb.admin_kb()); return
    existed=await db.get_user(m.from_user.id)
    await ensure_user(m)
    if not existed: await process_referral(m)
    if not await sub_ok(m.from_user.id):
        await m.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!",reply_markup=kb.mandatory(await db.channels()))
        return
    await welcome(m)

@dp.callback_query(F.data=="check")
async def check(call:types.CallbackQuery):
    if await sub_ok(call.from_user.id):
        await call.message.delete()
        await welcome(call.message)
    else: await call.answer("Hali barcha kanallarga obuna bo'lmagansiz.",show_alert=True)

@dp.message(Command("data"))
async def data_cmd(m:types.Message):
    if not is_root(m.from_user.id): return
    await db.conn.commit()
    os.makedirs("backups",exist_ok=True)
    path=os.path.join("backups","bot.db")
    shutil.copy2(db.db_path,path)
    try:
        await m.answer_document(FSInputFile(path),caption="To'liq ma'lumotlar bazasi. Shu bot.db faylini keyingi versiyada joyiga qo'ysangiz ma'lumotlar saqlanadi.")
    finally:
        try: os.remove(path)
        except: pass

@dp.message(F.text=="Kabinet")
async def cabinet(m:types.Message):
    if await blocked(m.from_user.id): return
    await ensure_user(m)
    u=await db.get_user(m.from_user.id)
    bal=await db.get_balance(m.from_user.id)
    friends=await db.referral_count(m.from_user.id)
    vip=await db.is_vip(m.from_user.id)
    bal_text=f"{bal:,}".replace(","," ")
    username=f"@{u['username']}" if u["username"] else "yoq"
    text=f"Ism: {u['name']}\nUser: {username}\nID: {u['user_id']}\n\nHisobim: {bal_text} so'm\n"
    if vip:
        try: until=datetime.fromisoformat(str(u["vip_until"])).strftime("%d.%m.%Y")
        except: until=str(u["vip_until"])
        text+=f"Holatim: VIP obunachi\nMuddati: {until} da tugaydi\n"
    else: text+="Holatim: Oddiy obunachi\n"
    text+=f"Do'stlarim: {friends} ta"
    await m.answer(text,reply_markup=kb.cabinet_kb(vip))

@dp.callback_query(F.data=="cabinet")
async def cabinet_cb(c:types.CallbackQuery):
    await c.message.delete()
    u=await db.get_user(c.from_user.id)
    if not u: return
    bal=await db.get_balance(c.from_user.id); friends=await db.referral_count(c.from_user.id); vip=await db.is_vip(c.from_user.id)
    username=f"@{u['username']}" if u["username"] else "yoq"
    text=f"Ism: {u['name']}\nUser: {username}\nID: {u['user_id']}\n\nHisobim: {bal:,} so'm\n".replace(","," ")
    if vip:
        try: until=datetime.fromisoformat(str(u["vip_until"])).strftime("%d.%m.%Y")
        except: until=str(u["vip_until"])
        text+=f"Holatim: VIP obunachi\nMuddati: {until} da tugaydi\n"
    else: text+="Holatim: Oddiy obunachi\n"
    text+=f"Do'stlarim: {friends} ta"
    await c.message.answer(text,reply_markup=kb.cabinet_kb(vip))

@dp.message(F.text=="Yordam")
async def help_(m:types.Message):
    link=await db.get_setting("admin_link") or "@admin"
    if link.startswith("http"): url=link
    else: url="https://t.me/"+link.replace("https://t.me/","").replace("t.me/","").lstrip("@/")
    await m.answer("Savollaringiz yoki muammo bo'lsa admin bilan bog'lanishingiz mumkin.",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="Bog'lanish",url=url)],
                        [types.InlineKeyboardButton(text="Orqaga",callback_data="cabinet")]
                    ]))

@dp.message(F.text=="Bot haqida")
async def about(m:types.Message):
    await m.answer(await db.get_setting("bot_info") or "Bot haqida ma'lumot mavjud emas.")

@dp.callback_query(F.data=="vip_menu")
async def vip_menu(c:types.CallbackQuery):
    if await db.is_vip(c.from_user.id):
        u=await db.get_user(c.from_user.id)
        try: until=datetime.fromisoformat(str(u["vip_until"])).strftime("%d.%m.%Y")
        except: until=str(u["vip_until"])
        await c.answer(f"Sizda allaqachon VIP obunasi mavjud. Muddati: {until} da tugaydi.",show_alert=True); return
    await c.message.edit_text("Qaysi tarif narxini tanlaysiz?",reply_markup=kb.vip_kb(await db.tariffs()))

@dp.callback_query(F.data.startswith("vip:"))
async def vip_select(c:types.CallbackQuery,state:FSMContext):
    if await db.is_vip(c.from_user.id):
        await c.answer("Sizda allaqachon VIP obunasi mavjud.",show_alert=True); return
    days=int(c.data.split(":")[1]); t=await db.tariff(days); card=await db.get_setting("card")
    await state.set_state(UserPayment.waiting_vip_receipt); await state.update_data(days=days)
    await c.message.edit_text(
        f"{t['name']}\nNarxi: {t['price']:,} so'm\n\nKarta raqami: {card}\n"
        "To'lovni amalga oshirgach, chek rasmini shu yerga yuboring.".replace(","," "),
        reply_markup=kb.back("cabinet")
    )

@dp.message(UserPayment.waiting_vip_receipt,F.photo)
async def vip_receipt(m:types.Message,state:FSMContext):
    d=await state.get_data(); days=int(d["days"]); t=await db.tariff(days)
    await bot.send_photo(ADMIN_ID,m.photo[-1].file_id,
        caption=f"Yangi VIP to'lov\nFoydalanuvchi IDsi: {m.from_user.id}\nTarif: {t['name']}\nNarxi: {t['price']} so'm",
        reply_markup=kb.admin_payment(m.from_user.id,"vip",days))
    await m.answer("Chek qabul qilindi. Admin tasdiqlashini kuting.")
    await state.clear()

@dp.callback_query(F.data=="balance")
async def balance_start(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("Qancha mablag' hisobingizga tushirmoqchisiz?\nMasalan: 20000",reply_markup=kb.back("cabinet"))
    await state.set_state(UserPayment.waiting_balance_amount)

@dp.message(UserPayment.waiting_balance_amount,F.text)
async def balance_amount(m:types.Message,state:FSMContext):
    raw=m.text.replace(" ","")
    if not raw.isdigit() or int(raw)<=0:
        await m.answer("Summani faqat raqam bilan kiriting."); return
    await state.update_data(amount=int(raw))
    await state.set_state(UserPayment.waiting_balance_receipt)
    card=await db.get_setting("card")
    await m.answer(f"Karta raqami: {card}\nTo'lovni amalga oshirib, chek rasmini yuboring.")

@dp.message(UserPayment.waiting_balance_receipt,F.photo)
async def balance_receipt(m:types.Message,state:FSMContext):
    d=await state.get_data(); amount=int(d["amount"])
    await bot.send_photo(ADMIN_ID,m.photo[-1].file_id,
        caption=f"Hisob to'ldirish\nFoydalanuvchi IDsi: {m.from_user.id}\nSumma: {amount} so'm",
        reply_markup=kb.admin_payment(m.from_user.id,"balance",amount))
    await m.answer("Chek qabul qilindi. Admin tasdiqlashini kuting.")
    await state.clear()

@dp.callback_query(F.data=="referral")
async def referral(c:types.CallbackQuery):
    me=await bot.get_me(); count=await db.referral_count(c.from_user.id); bal=await db.get_balance(c.from_user.id)
    link=f"https://t.me/{me.username}?start=ref_{c.from_user.id}"
    text=(f"Sizning maxsus havolangiz:\n{link}\n\n"
          "Har bir taklif qilgan yangi foydalanuvchi uchun: 500 so'm\n\n"
          f"Taklif qilgan do'stlaringiz: {count} ta\n"
          f"Ishlagan pulingiz: {bal:,} so'm\n\n"
          "Eslatma: Oldin qoidalar bilan tanishib chiqing!").replace(","," ")
    await c.message.edit_text(text,reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Referral qoidalari",callback_data="ref_rules")],
        [types.InlineKeyboardButton(text="Orqaga",callback_data="cabinet")]
    ]))

@dp.callback_query(F.data=="ref_rules")
async def ref_rules(c:types.CallbackQuery):
    await c.message.edit_text(
        "Referraldan qanday foydalanish mumkin?\n\n"
        "Faqat ishonchli, yaqin do'stingizga havolani shaxsiy xabarda yuboring. "
        "Referral havolasini ommaviy kanallar yoki guruhlarda tarqatmang.\n\n"
        "Qanday holatlarda qoida buzilgan hisoblanadi?\n"
        "1. Bir qurilmada bir nechta Telegram hisobidan foydalanib sun'iy referral yig'ish.\n"
        "2. Havolani ommaviy kanal yoki guruhlarda tarqatish.\n"
        "3. Yolg'on yoki chalg'ituvchi xabar bilan odam jalb qilish.\n"
        "4. Referral tizimini aldashga urinish.\n\n"
        "Qoidalar buzilsa bot sizni butunlay block qiladi va undan foydalana olmaysiz.\n\n"
        "Tushundim tugmasini bosish orqali barcha qoidalarga rioya qilishga rozilik bildirasiz.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Tushundim",callback_data="ref_ok")]
        ])
    )

@dp.callback_query(F.data=="ref_ok")
async def ref_ok(c:types.CallbackQuery):
    await c.message.edit_text("Referral qoidalari qabul qilindi.",reply_markup=kb.back("cabinet"))

async def can_watch(uid,vid):
    v=await db.video(vid)
    return bool(v and (v["is_free"] or await db.is_vip(uid) or await db.purchased(uid,vid)))

@dp.message(F.text,F.from_user.id!=ADMIN_ID)
async def video_code(m:types.Message):
    if await blocked(m.from_user.id): return
    if not await sub_ok(m.from_user.id):
        await m.answer("Botdan foydalanish uchun avval barcha majburiy kanallarga obuna bo'ling.",reply_markup=kb.mandatory(await db.channels())); return
    v=await db.video_by_code(m.text)
    if not v:
        await m.answer("Bunday video kodi topilmadi."); return
    await m.answer_photo(v["cover_id"],caption=f"{v['post_desc']}\n\nKo'rishlar: {v['views']}",
                         reply_markup=kb.video_post(v["id"]),protect_content=True)

@dp.callback_query(F.data.startswith("qmenu:"))
async def qmenu(c:types.CallbackQuery):
    vid=int(c.data.split(":")[1]); qs=await db.qualities(vid)
    await c.message.edit_reply_markup(reply_markup=kb.qualities(vid,[q["quality"] for q in qs]))

@dp.callback_query(F.data.startswith("watch:"))
async def watch(c:types.CallbackQuery):
    vid=int(c.data.split(":")[1]); v=await db.video(vid)
    if not v: return
    if not await can_watch(c.from_user.id,vid):
        await c.message.answer("Bu videoni ko'rish uchun avval sotib oling yoki VIP obuna oling.",
                               reply_markup=kb.buy_video(vid,True)); return
    qs=await db.qualities(vid)
    if not qs: await c.answer("Video fayli topilmadi.",show_alert=True); return
    q=qs[0]
    await db.view_once(c.from_user.id,vid)
    likes,dislikes=await db.like_counts(vid)
    await c.message.delete()
    await c.message.answer_video(q["file_id"],caption=f"{v['main_desc']}\n\nSifati: {q['quality']}\nKo'rishlar: {v['views']}",
                                 reply_markup=kb.watch_actions(vid,likes,dislikes),protect_content=True)

@dp.callback_query(F.data.startswith("quality:"))
async def quality(c:types.CallbackQuery):
    _,vid,qname=c.data.split(":",2); vid=int(vid)
    if not await can_watch(c.from_user.id,vid):
        await c.answer("Avval videoni sotib oling yoki VIP obuna oling.",show_alert=True); return
    qs=await db.qualities(vid); match=next((q for q in qs if q["quality"]==qname),None)
    if not match: return
    v=await db.video(vid); await db.view_once(c.from_user.id,vid); likes,dislikes=await db.like_counts(vid)
    await c.message.delete()
    await c.message.answer_video(match["file_id"],caption=f"{v['main_desc']}\n\nSifati: {qname}\nKo'rishlar: {v['views']}",
                                 reply_markup=kb.watch_actions(vid,likes,dislikes),protect_content=True)

@dp.callback_query(F.data.startswith("changeq:"))
async def changeq(c:types.CallbackQuery):
    vid=int(c.data.split(":")[1]); qs=await db.qualities(vid)
    await c.message.delete()
    await c.message.answer("Sifatni tanlang.",reply_markup=kb.qualities(vid,[q["quality"] for q in qs]))

@dp.callback_query(F.data.startswith("like:" )|F.data.startswith("dislike:"))
async def like(c:types.CallbackQuery):
    action,vid=c.data.split(":"); vid=int(vid); val=1 if action=="like" else 0
    await db.set_like(c.from_user.id,vid,val); l,d=await db.like_counts(vid)
    await c.message.edit_reply_markup(reply_markup=kb.watch_actions(vid,l,d))

@dp.callback_query(F.data.startswith("buy:"))
async def buy(c:types.CallbackQuery,state:FSMContext):
    vid=int(c.data.split(":")[1]); v=await db.video(vid)
    if not v: return
    if await db.is_vip(c.from_user.id) or await db.purchased(c.from_user.id,vid):
        await c.answer("Sizda bu videoga kirish huquqi mavjud.",show_alert=True); return
    await state.set_state(UserPayment.waiting_video_receipt); await state.update_data(video=vid)
    card=await db.get_setting("card")
    await c.message.edit_text(
        f"Video narxi: {v['price']} so'm\nKarta raqami: {card}\n\n"
        "To'lovni amalga oshirgach chek rasmini yuboring."
    )

@dp.message(UserPayment.waiting_video_receipt,F.photo)
async def video_receipt(m:types.Message,state:FSMContext):
    d=await state.get_data(); vid=int(d["video"]); v=await db.video(vid)
    await bot.send_photo(ADMIN_ID,m.photo[-1].file_id,
        caption=f"Yangi video to'lovi\nFoydalanuvchi IDsi: {m.from_user.id}\nVideo kodi: {v['code']}\nNarxi: {v['price']} so'm",
        reply_markup=kb.admin_payment(m.from_user.id,"video",vid))
    await m.answer("Chek qabul qilindi. Admin tasdiqlashini kuting."); await state.clear()

@dp.callback_query(F.data.startswith("my:"))
async def my(c:types.CallbackQuery):
    page=int(c.data.split(":")[1]); vs=await db.my_videos(c.from_user.id)
    if not vs: await c.answer("Sizda sotib olingan videolar yo'q.",show_alert=True); return
    await c.message.edit_text("Shu kungacha sotib olgan videolaringiz:",reply_markup=kb.my_videos(vs,page))

@dp.callback_query(F.data.startswith("myvideo:"))
async def myvideo(c:types.CallbackQuery):
    vid=int(c.data.split(":")[1])
    if not await db.purchased(c.from_user.id,vid) and not await db.is_vip(c.from_user.id):
        await c.answer("Bu video sizga tegishli emas.",show_alert=True); return
    v=await db.video(vid)
    await c.message.delete()
    await c.message.answer_photo(v["cover_id"],caption=v["post_desc"],reply_markup=kb.video_post(vid),protect_content=True)

@dp.callback_query(F.data=="cabinet")
async def cabinet_back(c:types.CallbackQuery):
    await c.message.delete()

# PAYMENT APPROVAL
@dp.callback_query(F.data.startswith("payok:"))
async def payok(c:types.CallbackQuery):
    if not is_root(c.from_user.id): return
    _,uid,kind,item=c.data.split(":"); uid=int(uid); item=int(item)
    if kind=="vip":
        until=await db.set_vip(uid,item)
        await bot.send_message(uid,f"VIP obunangiz tasdiqlandi.\nMuddati: {until.strftime('%d.%m.%Y')} da tugaydi.")
    elif kind=="video":
        await db.purchase(uid,item); await bot.send_message(uid,"To'lov tasdiqlandi. Video endi sizning Videolarim bo'limingizda.")
    elif kind=="balance":
        await db.add_balance(uid,item); await bot.send_message(uid,f"Hisobingiz {item:,} so'mga to'ldirildi.".replace(","," "))
    await c.message.edit_caption((c.message.caption or "")+"\n\nTasdiqlandi")

@dp.callback_query(F.data.startswith("payno:"))
async def payno(c:types.CallbackQuery):
    if not is_root(c.from_user.id): return
    _,uid,kind,item=c.data.split(":"); uid=int(uid)
    await bot.send_message(uid,"To'lovingiz rad qilindi. Iltimos, to'g'ri to'lov bilan qayta urinib ko'ring.")
    await c.message.edit_caption((c.message.caption or "")+"\n\nRad qilindi")

# ADMIN MAIN
@dp.message(F.text=="Video qo'shish")
async def add_video(m:types.Message,state:FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.answer("Video muqovasi uchun rasm yuboring."); await state.set_state(AdminVideo.waiting_cover)

@dp.message(AdminVideo.waiting_cover,F.photo)
async def add_cover(m:types.Message,state:FSMContext):
    await state.update_data(cover=m.photo[-1].file_id); await m.answer("Video posti uchun izoh yuboring."); await state.set_state(AdminVideo.waiting_post_desc)

@dp.message(AdminVideo.waiting_post_desc,F.text)
async def add_post_desc(m:types.Message,state:FSMContext):
    await state.update_data(post_desc=m.text); await m.answer("Asosiy video uchun izoh yuboring."); await state.set_state(AdminVideo.waiting_main_desc)

@dp.message(AdminVideo.waiting_main_desc,F.text)
async def add_main_desc(m:types.Message,state:FSMContext):
    await state.update_data(main_desc=m.text); await m.answer("Video turi: Pullik yoki Bepul?",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Pullik",callback_data="vtype:paid"),types.InlineKeyboardButton(text="Bepul",callback_data="vtype:free")]
    ])); await state.set_state(AdminVideo.waiting_type)

@dp.callback_query(AdminVideo.waiting_type,F.data.startswith("vtype:"))
async def vtype(c:types.CallbackQuery,state:FSMContext):
    free=c.data.endswith("free"); await state.update_data(is_free=free)
    if free:
        await state.update_data(price=0); await c.message.edit_text("Video sifatini tanlang.",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="360p",callback_data="vq:360p"),types.InlineKeyboardButton(text="480p",callback_data="vq:480p")],
            [types.InlineKeyboardButton(text="720p",callback_data="vq:720p"),types.InlineKeyboardButton(text="1080p",callback_data="vq:1080p")]
        ]))
        await state.set_state(AdminVideo.waiting_quality)
    else:
        await c.message.edit_text("Video narxini kiriting."); await state.set_state(AdminVideo.waiting_price)

@dp.message(AdminVideo.waiting_price,F.text)
async def add_price(m:types.Message,state:FSMContext):
    raw=m.text.replace(" ","")
    if not raw.isdigit() or int(raw)<=0: await m.answer("Narxni faqat musbat raqam bilan kiriting."); return
    await state.update_data(price=int(raw)); await m.answer("Video sifatini tanlang.",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="360p",callback_data="vq:360p"),types.InlineKeyboardButton(text="480p",callback_data="vq:480p")],
        [types.InlineKeyboardButton(text="720p",callback_data="vq:720p"),types.InlineKeyboardButton(text="1080p",callback_data="vq:1080p")]
    ])); await state.set_state(AdminVideo.waiting_quality)

@dp.callback_query(AdminVideo.waiting_quality,F.data.startswith("vq:"))
async def choose_add_quality(c:types.CallbackQuery,state:FSMContext):
    q=c.data.split(":")[1]; await state.update_data(current_q=q); await c.message.edit_text(f"{q} sifatdagi videoni yuboring."); await state.set_state(AdminVideo.waiting_file)

@dp.message(AdminVideo.waiting_file,F.video)
async def add_file(m:types.Message,state:FSMContext):
    d=await state.get_data(); qs=d.get("qualities",{}); qs[d["current_q"]]=m.video.file_id; await state.update_data(qualities=qs)
    remaining=[q for q in ["360p","480p","720p","1080p"] if q not in qs]
    if remaining:
        await m.answer("Yana sifat qo'shasizmi?",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            *[[types.InlineKeyboardButton(text=q,callback_data=f"vq:{q}")] for q in remaining],
            [types.InlineKeyboardButton(text="Bo'ldi",callback_data="vq_done")]
        ])); await state.set_state(AdminVideo.waiting_quality)
    else:
        await m.answer("Barcha sifatlar qo'shildi. Video kodini yuboring."); await state.set_state(AdminVideo.waiting_code)

@dp.callback_query(AdminVideo.waiting_quality,F.data=="vq_done")
async def vq_done(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("Video kodini yuboring."); await state.set_state(AdminVideo.waiting_code)

@dp.message(AdminVideo.waiting_code,F.text)
async def save_video(m:types.Message,state:FSMContext):
    d=await state.get_data()
    try: vid=await db.add_video(m.text,d["cover"],d["post_desc"],d["main_desc"],d["price"],d["is_free"])
    except Exception:
        await m.answer("Bu video kodi allaqachon mavjud yoki saqlashda xato yuz berdi."); return
    for q,f in d.get("qualities",{}).items(): await db.add_quality(vid,q,f)
    await m.answer("Video muvaffaqiyatli qo'shildi, xo'jayin."); await state.clear()

@dp.message(F.text=="Video o'chirish")
async def delete_video(m:types.Message,state:FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.answer("O'chirmoqchi bo'lgan video kodini yuboring."); await state.set_state(AdminVideo.waiting_delete_code)

# BROADCAST
def parse_buttons(raw):
    rows=[]
    for line in raw.strip().splitlines():
        cols=[x.strip() for x in line.split("|")]
        row=[]
        for col in cols:
            parts=[x.strip() for x in col.split("-")]
            if len(parts)<2: continue
            # color is accepted for compatibility; Telegram Bot API does not expose per-button colors.
            name=parts[0]; url=parts[1]
            if url.startswith("t.me/"): url="https://"+url
            row.append({"text":name,"url":url,"color":parts[2].lower() if len(parts)>2 else "blue"})
        if row: rows.append(row)
    return rows

def button_markup(rows):
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=b["text"],url=b["url"]) for b in row] for row in rows
    ])

async def send_post(chat_id,data,markup=None):
    typ=data["type"]
    if typ=="text": return await bot.send_message(chat_id,data["text"],reply_markup=markup)
    if typ=="photo": return await bot.send_photo(chat_id,data["file_id"],caption=data.get("caption",""),reply_markup=markup,protect_content=True)
    if typ=="video": return await bot.send_video(chat_id,data["file_id"],caption=data.get("caption",""),reply_markup=markup,protect_content=True)
    if typ=="document": return await bot.send_document(chat_id,data["file_id"],caption=data.get("caption",""),reply_markup=markup,protect_content=True)
    if typ=="animation": return await bot.send_animation(chat_id,data["file_id"],caption=data.get("caption",""),reply_markup=markup,protect_content=True)
    if typ=="voice": return await bot.send_voice(chat_id,data["file_id"],caption=data.get("caption",""),reply_markup=markup,protect_content=True)

def extract_post(m):
    if m.text is not None: return {"type":"text","text":m.text}
    if m.photo: return {"type":"photo","file_id":m.photo[-1].file_id,"caption":m.caption or ""}
    if m.video: return {"type":"video","file_id":m.video.file_id,"caption":m.caption or ""}
    if m.document: return {"type":"document","file_id":m.document.file_id,"caption":m.caption or ""}
    if m.animation: return {"type":"animation","file_id":m.animation.file_id,"caption":m.caption or ""}
    if m.voice: return {"type":"voice","file_id":m.voice.file_id,"caption":m.caption or ""}
    return None

@dp.message(F.text=="Reklama")
async def broadcast_start(m:types.Message,state:FSMContext):
    if not await is_admin(m.from_user.id): return
    await m.answer("Nima reklama qilamiz?\nMatn, rasm + matn, video yoki boshqa postni yuboring.")
    await state.set_state(AdminBroadcast.waiting_post)

@dp.message(AdminBroadcast.waiting_post)
async def broadcast_post(m:types.Message,state:FSMContext):
    d=extract_post(m)
    if not d: await m.answer("Bu turdagi xabarni qabul qila olmayman."); return
    await state.update_data(post=d,buttons=[])
    await send_post(m.from_user.id,d,kb.broadcast_editor(False))

@dp.callback_query(F.data=="broadcast_buttons")
async def broadcast_buttons(c:types.CallbackQuery,state:FSMContext):
    await c.message.answer(
        "Tugmalar nomi va havolasini birga ko'rsating.\n\n"
        "1 ta tugma:\nBotga o'tish - t.me/Xavfli_Hudud_Robot - blue\n\n"
        "2 ta yonma-yon:\nBotga o'tish - t.me/Xavfli_Hudud_Robot - blue | Obuna olish - t.me/Xavfli_Hudud_tg - red\n\n"
        "Tagma-tag:\nBotga o'tish - t.me/Xavfli_Hudud_Robot - blue\nObuna olish - t.me/Xavfli_Hudud_tg - red\n\n"
        "blue, red, green ranglari qabul qilinadi. Telegram Bot API standart inline tugma rangini alohida o'zgartirishni bermaydi."
    )
    await state.set_state(AdminBroadcast.waiting_buttons)

@dp.message(AdminBroadcast.waiting_buttons,F.text)
async def broadcast_buttons_save(m:types.Message,state:FSMContext):
    rows=parse_buttons(m.text)
    if not rows: await m.answer("Tugmalar formati noto'g'ri."); return
    await state.update_data(buttons=rows)
    d=await state.get_data(); await m.answer("Tugmalar qo'shilgan post:")
    await send_post(m.from_user.id,d["post"],button_markup(rows))
    await m.answer("Keyingi amalni tanlang.",reply_markup=kb.broadcast_editor(True))
    await state.set_state(AdminBroadcast.waiting_post)

@dp.callback_query(F.data=="broadcast_clear")
async def broadcast_clear(c:types.CallbackQuery,state:FSMContext):
    d=await state.get_data(); d["buttons"]=[]; await state.update_data(buttons=[])
    await c.message.answer("Tugmalar o'chirildi. Post boshidagi holatga qaytdi.")
    await send_post(c.from_user.id,d["post"],kb.broadcast_editor(False))

@dp.callback_query(F.data=="broadcast_done")
async def broadcast_done(c:types.CallbackQuery,state:FSMContext):
    await c.message.answer("Kimlarga yuborishni tanlang:",reply_markup=kb.broadcast_targets())

@dp.callback_query(F.data=="broadcast_cancel")
async def broadcast_cancel(c:types.CallbackQuery,state:FSMContext):
    await state.clear(); await c.message.answer("Reklama bekor qilindi.",reply_markup=kb.admin_kb())

@dp.callback_query(F.data.startswith("target:"))
async def broadcast_target(c:types.CallbackQuery,state:FSMContext):
    target=c.data.split(":")[1]; d=await state.get_data(); rows=d.get("buttons",[]); markup=button_markup(rows) if rows else None
    if target=="all": users=[r["user_id"] for r in await db.conn.execute_fetchall("SELECT user_id FROM users")]
    elif target=="vip": users=[r["user_id"] for r in await db.conn.execute_fetchall("SELECT user_id FROM users WHERE vip_until IS NOT NULL AND vip_until>?",(datetime.now().isoformat(),))]
    else: users=[r["user_id"] for r in await db.conn.execute_fetchall("SELECT user_id FROM users WHERE vip_until IS NULL OR vip_until<=?",(datetime.now().isoformat(),))]
    sent=0
    for uid in users:
        try: await send_post(uid,d["post"],markup); sent+=1
        except (TelegramForbiddenError,TelegramRetryAfter): pass
        except Exception: pass
    await c.message.answer(f"Reklama yuborildi.\nYuborilganlar: {sent} ta",reply_markup=kb.admin_kb()); await state.clear()

# GIFTS
@dp.message(F.text=="Hadyalar")
async def gift_menu(m:types.Message):
    if await is_admin(m.from_user.id): await m.answer("Hadyalar bo'limi",reply_markup=kb.gifts())

@dp.callback_query(F.data=="gift_id")
async def gift_id(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("VIP beriladigan foydalanuvchi IDsi:")
    await state.set_state(AdminGift.waiting_id)

@dp.message(AdminGift.waiting_id,F.text)
async def gift_id_user(m:types.Message,state:FSMContext):
    if not m.text.isdigit(): await m.answer("IDni faqat raqam bilan kiriting."); return
    uid=int(m.text); u=await db.get_user(uid)
    if not u: await m.answer("Bunday foydalanuvchi topilmadi."); return
    await state.update_data(uid=uid); await m.answer("Tarifni tanlang.",reply_markup=kb.gift_tariffs(await db.tariffs(),"giftid"))

@dp.callback_query(F.data.startswith("giftid:"))
async def gift_id_tariff(c:types.CallbackQuery,state:FSMContext):
    days=int(c.data.split(":")[1]); d=await state.get_data(); t=await db.tariff(days)
    await state.update_data(days=days)
    await c.message.edit_text(f"{d['uid']} ID foydalanuvchiga {t['name']} VIP berilsinmi?",reply_markup=kb.yesno("giftid_yes","giftid_no"))

@dp.callback_query(F.data=="giftid_yes")
async def giftid_yes(c:types.CallbackQuery,state:FSMContext):
    d=await state.get_data(); until=await db.set_vip(int(d["uid"]),int(d["days"]))
    await bot.send_message(int(d["uid"]),f"Sizga VIP sovg'a berildi.\nMuddati: {until.strftime('%d.%m.%Y')} da tugaydi.")
    await c.message.edit_text("VIP sovg'a berildi."); await state.clear()

@dp.callback_query(F.data=="giftid_no")
async def giftid_no(c:types.CallbackQuery,state:FSMContext):
    await state.clear(); await c.message.edit_text("Bekor qilindi.")

@dp.callback_query(F.data=="gift_random")
async def gift_random(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("Nechta odam sovg'ani ola oladi?")
    await state.set_state(AdminGift.waiting_random_count)

@dp.message(AdminGift.waiting_random_count,F.text)
async def gift_random_count(m:types.Message,state:FSMContext):
    if not m.text.isdigit() or int(m.text)<=0: await m.answer("Musbat son kiriting."); return
    await state.update_data(count=int(m.text))
    await m.answer("Tarifni tanlang.",reply_markup=kb.gift_tariffs(await db.tariffs(),"giftrand"))

@dp.callback_query(F.data.startswith("giftrand:"))
async def gift_random_tariff(c:types.CallbackQuery,state:FSMContext):
    days=int(c.data.split(":")[1]); d=await state.get_data(); t=await db.tariff(days)
    await state.update_data(days=days,name=t["name"])
    await c.message.edit_text(f"{t['name']} VIP, {d['count']} ta g'olib uchun gift yaratiladi. Tasdiqlaysizmi?",
                             reply_markup=kb.yesno("giftrand_yes","giftrand_no"))

@dp.callback_query(F.data=="giftrand_yes")
async def giftrand_yes(c:types.CallbackQuery,state:FSMContext):
    d=await state.get_data(); gid=await db.create_gift(d["days"],d["name"],d["count"])
    await c.message.edit_text("Gift tayyor.")
    await bot.send_message(c.from_user.id,f"Sovg'a uchun maxsus xabar:\n\nBirinchi bo'lib tugmani bosgan {d['count']} ta foydalanuvchi {d['name']} VIP oladi.",
                           reply_markup=kb.claim(gid))
    await state.clear()

@dp.callback_query(F.data=="giftrand_no")
async def giftrand_no(c:types.CallbackQuery,state:FSMContext):
    await state.clear(); await c.message.edit_text("Bekor qilindi.")

@dp.callback_query(F.data.startswith("claim:"))
async def claim(c:types.CallbackQuery):
    gid=int(c.data.split(":")[1])
    status,data=await db.claim_gift(gid,c.from_user.id)
    if status=="won":
        g,n=data; until=await db.set_vip(c.from_user.id,g["days"])
        await c.answer("Sovg'a sizga berildi.",show_alert=True)
        await c.message.edit_text(f"Tabriklaymiz. Siz {g['tariff_name']} VIP sovg'asini oldingiz.\nMuddati: {until.strftime('%d.%m.%Y')} da tugaydi.")
        await bot.send_message(ADMIN_ID,f"Gift olgan foydalanuvchi\nIsmi: {c.from_user.first_name}\nUseri: @{c.from_user.username or 'yoq'}\nIDsi: {c.from_user.id}")
    elif status=="already": await c.answer("Siz bu sovg'ani allaqachon olgansiz.",show_alert=True)
    elif status=="vip": await c.answer("Sizda allaqachon VIP obunasi mavjud.",show_alert=True)
    else: await c.answer("Afsus, sovg'a tugagan.",show_alert=True)

@dp.callback_query(F.data=="revoke")
async def revoke(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("VIPsi bekor qilinadigan foydalanuvchi IDsi:")
    await state.set_state(AdminGift.waiting_revoke_id)

@dp.message(AdminGift.waiting_revoke_id,F.text)
async def revoke_id(m:types.Message,state:FSMContext):
    if not m.text.isdigit(): await m.answer("IDni faqat raqam bilan kiriting."); return
    await state.update_data(uid=int(m.text)); await m.answer("VIPni bekor qilasizmi?",reply_markup=kb.yesno("revoke_yes","revoke_no"))

@dp.callback_query(F.data=="revoke_yes")
async def revoke_yes(c:types.CallbackQuery,state:FSMContext):
    d=await state.get_data(); await db.revoke_vip(d["uid"]); await bot.send_message(d["uid"],"VIP obunangiz bekor qilindi.")
    await c.message.edit_text("VIP bekor qilindi."); await state.clear()

@dp.callback_query(F.data=="revoke_no")
async def revoke_no(c:types.CallbackQuery,state:FSMContext):
    await state.clear(); await c.message.edit_text("Bekor qilindi.")

# SETTINGS
@dp.message(F.text=="Sozlamalar")
async def settings(m:types.Message):
    if await is_admin(m.from_user.id): await m.answer("Sozlamalar",reply_markup=kb.admin_settings())

@dp.callback_query(F.data=="settings")
async def settings_cb(c:types.CallbackQuery):
    await c.message.edit_text("Sozlamalar",reply_markup=kb.admin_settings())

@dp.callback_query(F.data=="card")
async def card(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("Yangi karta raqamini yuboring.\nEski karta o'rniga yangi karta saqlanadi.")
    await state.set_state(AdminSettings.waiting_card)

@dp.message(AdminSettings.waiting_card,F.text)
async def card_save(m:types.Message,state:FSMContext):
    await db.set_setting("card",m.text.strip()); await m.answer("O'zgartirilgan karta raqami saqlandi."); await state.clear()

@dp.callback_query(F.data=="info")
async def info(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("Yangi bot haqida matnini yuboring."); await state.set_state(AdminSettings.waiting_info)

@dp.message(AdminSettings.waiting_info,F.text)
async def info_save(m:types.Message,state:FSMContext):
    await db.set_setting("bot_info",m.text); await m.answer("Ma'lumot almashtirildi."); await state.clear()

@dp.callback_query(F.data=="adminlink")
async def adminlink(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("Admin havolasini yuboring."); await state.set_state(AdminSettings.waiting_admin_link)

@dp.message(AdminSettings.waiting_admin_link,F.text)
async def adminlink_save(m:types.Message,state:FSMContext):
    await db.set_setting("admin_link",m.text); await m.answer("Havola saqlandi."); await state.clear()

@dp.callback_query(F.data=="tariffs")
async def tariff_menu(c:types.CallbackQuery):
    await c.message.edit_text("Qaysi tarif narxini o'zgartiramiz xo'jayin?",reply_markup=kb.tariffs(await db.tariffs()))

@dp.callback_query(F.data.startswith("edit_tariff:"))
async def edit_tariff(c:types.CallbackQuery,state:FSMContext):
    days=int(c.data.split(":")[1]); await state.update_data(days=days)
    await c.message.edit_text("Qancha narx belgilaysiz?"); await state.set_state(AdminSettings.waiting_tariff_price)

@dp.message(AdminSettings.waiting_tariff_price,F.text)
async def save_tariff(m:types.Message,state:FSMContext):
    raw=m.text.replace(" ","")
    if not raw.isdigit() or int(raw)<0: await m.answer("Narxni raqam bilan kiriting."); return
    d=await state.get_data(); await db.set_tariff_price(d["days"],int(raw)); await m.answer("O'zgartirilgan narx saqlandi."); await state.clear()

@dp.callback_query(F.data=="channels")
async def channel_menu(c:types.CallbackQuery): await c.message.edit_text("Kanallar",reply_markup=kb.channels())

@dp.callback_query(F.data=="channel_add")
async def channel_add(c:types.CallbackQuery,state:FSMContext):
    await c.message.edit_text("Botni kanalga admin qiling va shu kanaldan bitta postni botga yuboring.")
    await state.set_state(AdminSettings.waiting_channel_post)

@dp.message(AdminSettings.waiting_channel_post)
async def channel_post(m:types.Message,state:FSMContext):
    chat=None
    try:
        if m.forward_origin and getattr(m.forward_origin,"chat",None):
            chat=m.forward_origin.chat
    except Exception:
        pass
    if chat is None:
        chat=getattr(m,"forward_from_chat",None)
    if not chat:
        await m.answer("Iltimos, aynan kanaldan yuborilgan postni yuboring."); return
    title=chat.title or "Kanal"
    url=f"https://t.me/{chat.username}" if getattr(chat,"username",None) else ""
    await db.add_channel(chat.id,title,url)
    await m.answer(f"{title} kanali saqlandi."); await state.clear()

@dp.callback_query(F.data=="channel_del")
async def channel_del(c:types.CallbackQuery):
    ch=await db.channels()
    if not ch: await c.message.edit_text("Saqlangan kanal yo'q.",reply_markup=kb.back("channels")); return
    b=types.InlineKeyboardBuilder()
    for x in ch: b.button(text=x["title"],callback_data=f"delchannel:{x['channel_id']}")
    b.adjust(1); await c.message.edit_text("O'chiriladigan kanalni tanlang.",reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("delchannel:"))
async def delchannel(c:types.CallbackQuery):
    await db.delete_channel(int(c.data.split(":")[1])); await c.message.edit_text("Kanal o'chirildi.",reply_markup=kb.back("channels"))

@dp.callback_query(F.data=="admins")
async def admins(c:types.CallbackQuery):
    if not can_manage_admins(c.from_user.id): return
    await c.message.edit_text("Adminlar",reply_markup=kb.admins())

@dp.callback_query(F.data=="admin_add")
async def admin_add(c:types.CallbackQuery,state:FSMContext):
    if not can_manage_admins(c.from_user.id): return
    await c.message.edit_text("Yangi admin Telegram IDsi:")
    await state.set_state(AdminSettings.waiting_admin_id)

@dp.message(AdminSettings.waiting_admin_id,F.text)
async def admin_id_save(m:types.Message,state:FSMContext):
    if not can_manage_admins(m.from_user.id): return
    if not m.text.isdigit(): await m.answer("IDni faqat raqam bilan kiriting."); return
    uid=int(m.text); await db.add_admin(uid,m.from_user.id,"admin"); await m.answer("Admin qo'shildi."); await state.clear()

@dp.callback_query(F.data=="admin_del")
async def admin_del(c:types.CallbackQuery):
    if not can_manage_admins(c.from_user.id): return
    admins=await db.all_admins()
    b=types.InlineKeyboardBuilder()
    for a in admins:
        # Oddiy admin faqat o'zi qo'shgan adminni bekor qila oladi.
        if is_root(c.from_user.id) or a["added_by"]==c.from_user.id:
            b.button(text=str(a["user_id"]),callback_data=f"deladmin:{a['user_id']}")
    b.adjust(1); await c.message.edit_text("Bekor qilinadigan adminni tanlang.",reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("deladmin:"))
async def deladmin(c:types.CallbackQuery):
    uid=int(c.data.split(":")[1])
    if uid==ADMIN_ID: await c.answer("Bosh xo'jayinning adminligini bekor qilib bo'lmaydi.",show_alert=True); return
    a=await db.admin(uid)
    if not is_root(c.from_user.id) and (not a or a["added_by"]!=c.from_user.id):
        await c.answer("Bu adminni bekor qila olmaysiz.",show_alert=True); return
    await db.remove_admin(uid); await c.message.edit_text("Admin bekor qilindi.",reply_markup=kb.back("admins"))

@dp.message(F.text=="Statistika")
async def statistics(m:types.Message):
    if not await is_admin(m.from_user.id): return
    vids,purchases,views=await db.stats()
    await m.answer(f"Botga qo'shilgan odamlar soni: {await db.total_users()}\nVIP obunachilar: {await db.vip_count()}\nVideolar: {vids}\nSotib olingan videolar: {purchases}\nKo'rishlar: {views}")

# ADMIN FALLBACK
@dp.message(AdminVideo.waiting_delete_code,F.text)
async def delete_code(m:types.Message,state:FSMContext):
    v=await db.video_by_code(m.text)
    if not v:
        await m.answer("Bunday video kodi topilmadi."); return
    await state.update_data(delete_code=m.text)
    await m.answer(
        f"Video: {m.text}\n\nChindan ham shu videoni o'chirmoqchimisiz?",
        reply_markup=kb.yesno("delete_yes","delete_no")
    )

@dp.callback_query(F.data=="delete_yes")
async def delete_yes(c:types.CallbackQuery,state:FSMContext):
    d=await state.get_data()
    ok=await db.delete_video(d["delete_code"])
    await c.message.edit_text("Video muvaffaqiyatli o'chirildi." if ok else "Video topilmadi.")
    await state.clear()

@dp.callback_query(F.data=="delete_no")
async def delete_no(c:types.CallbackQuery,state:FSMContext):
    await state.clear()
    await c.message.edit_text("Bekor qilindi.")

async def main():
    await db.connect()
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
