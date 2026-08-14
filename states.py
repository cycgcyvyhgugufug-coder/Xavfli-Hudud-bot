
from aiogram.fsm.state import State, StatesGroup

class UserPayment(StatesGroup):
    waiting_vip_receipt = State()
    waiting_video_receipt = State()
    waiting_balance_amount = State()
    waiting_balance_receipt = State()

class AdminVideo(StatesGroup):
    waiting_cover = State()
    waiting_post_desc = State()
    waiting_main_desc = State()
    waiting_type = State()
    waiting_price = State()
    waiting_quality = State()
    waiting_file = State()
    waiting_code = State()
    waiting_delete_code = State()

class AdminSettings(StatesGroup):
    waiting_card = State()
    waiting_info = State()
    waiting_admin_link = State()
    waiting_channel_post = State()
    waiting_channel_name = State()
    waiting_remove_channel = State()
    waiting_tariff_price = State()
    waiting_admin_id = State()

class AdminBroadcast(StatesGroup):
    waiting_post = State()
    waiting_buttons = State()

class AdminGift(StatesGroup):
    waiting_id = State()
    waiting_id_confirm = State()
    waiting_random_count = State()
    waiting_random_confirm = State()
    waiting_revoke_id = State()
    waiting_revoke_confirm = State()
