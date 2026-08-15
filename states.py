from aiogram.fsm.state import State, StatesGroup


# ---------- FOYDALANUVCHI ----------
class TopUp(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()


# ---------- ADMIN: VIDEO QO'SHISH ----------
class AdminAddVideoPaid(StatesGroup):
    waiting_for_cover = State()
    waiting_for_post_desc = State()
    waiting_for_main_desc = State()
    waiting_for_price = State()
    waiting_for_quality_select = State()
    waiting_for_video_file = State()
    waiting_for_code = State()


class AdminAddVideoFree(StatesGroup):
    waiting_for_video_file = State()
    waiting_for_code = State()


class AdminDeleteVideo(StatesGroup):
    waiting_for_code = State()
    waiting_for_confirm = State()


# ---------- ADMIN: REKLAMA ----------
class AdminBroadcast(StatesGroup):
    waiting_for_content = State()   # rasm+matn / video+matn / faqat matn
    waiting_for_buttons = State()   # tugmalar formatidagi matn


# ---------- ADMIN: GIFT ----------
class AdminGift(StatesGroup):
    waiting_for_tariff = State()
    waiting_for_count = State()
    waiting_for_confirm = State()


# ---------- ADMIN: FOYDALANUVCHILAR ----------
class AdminUsers(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_add_amount = State()
    waiting_for_add_confirm = State()
    waiting_for_subtract_amount = State()
    waiting_for_subtract_confirm = State()
    waiting_for_vip_tariff = State()
    waiting_for_block_confirm = State()
    waiting_for_message_text = State()


# ---------- ADMIN: ADMINLARNI BOSHQARISH ----------
class AdminManage(StatesGroup):
    waiting_for_new_admin_id = State()
    waiting_for_new_admin_confirm = State()
    waiting_for_permissions = State()
    waiting_for_remove_admin_id = State()
    waiting_for_remove_confirm = State()


# ---------- ADMIN: SOZLAMALAR ----------
class AdminSettings(StatesGroup):
    waiting_for_card = State()
    waiting_for_vip_price = State()
    waiting_for_info = State()
    waiting_for_admin_link = State()


class AdminChannels(StatesGroup):
    waiting_for_mandatory_channel = State()
    waiting_for_ad_channel_link = State()
    waiting_for_ad_channel_confirm = State()
    waiting_for_ad_channel_type = State()


# ---------- TO'LOVNI RAD ETISH SABABI ----------
class RejectReason(StatesGroup):
    waiting_for_reason = State()
