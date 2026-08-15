# Xavfli Hudud — Video sotish boti

## Railway'ga joylashtirish

1. Loyihani GitHub repositoriyaga yuklang (yoki Railway CLI orqali to'g'ridan-to'g'ri deploy qiling).
2. Railway'da yangi loyiha yarating va shu repo'ni ulang.
3. **Project -> Variables** bo'limiga quyidagilarni qo'shing:
   - `BOT_TOKEN` — BotFather bergan token
   - `ADMIN_ID` — sizning shaxsiy Telegram ID raqamingiz (masalan @userinfobot orqali bilib olishingiz mumkin)
4. Railway avtomatik ravishda `requirements.txt`dagi kutubxonalarni o'rnatadi va `Procfile`dagi
   `worker: python main.py` buyrug'i orqali botni ishga tushiradi.

**MUHIM:** Avval sizda bo'lgan `config.py` faylida token va admin ID kod ichida ochiq
yozilgan edi va bu suhbat davomida oshkor bo'ldi. Shu tokenni BotFather'da
**/revoke** qilib, yangisini oling va uni faqat Railway Variables orqali kiriting.

## Lokal (kompyuteringizda) ishga tushirish

1. `.env` fayl yarating (loyiha ildizida) va ichiga yozing:
   ```
   BOT_TOKEN=sizning_tokeningiz
   ADMIN_ID=sizning_id_raqamingiz
   ```
2. Kutubxonalarni o'rnating:
   ```
   pip install -r requirements.txt
   ```
3. Botni ishga tushiring:
   ```
   python main.py
   ```

## Loyiha tuzilishi

```
config.py            - token/admin ID (Railway Variables orqali)
states.py             - barcha FSM holatlari
keyboards.py          - barcha klaviaturalar
db.py                 - SQLite ma'lumotlar bazasi (bot.db fayli avtomatik yaratiladi)
utils.py               - yordamchi funksiyalar
middlewares.py         - bloklangan foydalanuvchilarni cheklovchi middleware
handlers/user.py       - foydalanuvchi tomoni (kabinet, xarid, referal, VIP)
handlers/admin.py      - admin tomoni (ish stoli, sozlamalar, statistika)
main.py                - botni ishga tushiruvchi fayl
```

## Asosiy imkoniyatlar

**Foydalanuvchi:**
- Majburiy obuna tekshiruvi
- Kabinet (balans, VIP holati, do'stlar soni)
- Hisobni to'ldirish (chek orqali, admin tasdiqlaydi)
- Referal tizimi (har bir yangi do'st uchun 500 so'm)
- VIP obuna (1/7/30 kunlik, balansdan avtomatik yechiladi)
- Video xaridi (pullik — balansdan, bepul — kod bilan bevosita)
- Videolarim bo'limi
- Yoqdi/Yoqmadi (like/dislike)

**Admin:**
- Ish stoli: video qo'shish (pullik/bepul), video o'chirish, reklama jo'natish
  (rasm/video/matn + ixtiyoriy URL-tugmalar), gift o'tkazish (random VIP tarqatish)
- Sozlamalar: kanallar (majburiy + reklama), foydalanuvchilarni boshqarish
  (balans, VIP, bloklash, xabar yuborish), ko'p darajali adminlar (huquqlar bilan),
  karta/VIP narx/info/admin link tahrirlash
- Statistika: umumiy va so'nggi 7 kunlik ko'rsatkichlar

## Eslatma

`/data` buyrug'i orqali (faqat asosiy admin) `bot.db` faylini yuklab olishingiz mumkin —
bu Railway'da qayta ishga tushishlardan oldin zaxira nusxa olish uchun foydali.
