from aiogram.fsm.state import State, StatesGroup

class AdminAddVideo(StatesGroup):
    waiting_for_cover = State()
    waiting_for_post_desc = State()
    waiting_for_main_desc = State()
    waiting_for_price = State()
    waiting_for_quality_select = State()
    waiting_for_video_file = State()
    waiting_for_code = State()

class AdminDeleteVideo(StatesGroup):
    waiting_for_code = State()

class AdminSettings(StatesGroup):
    waiting_for_base_channel = State()
    waiting_for_mandatory_channel = State()
    waiting_for_card_number = State()
    waiting_for_admin_link = State()

class UserPayment(StatesGroup):
    waiting_for_receipt_vip = State()
    waiting_for_receipt_video = State()


class AdminBroadcast(StatesGroup):
    waiting_for_photo = State()
    waiting_for_text = State()
    waiting_for_button_name = State()
    waiting_for_button_url = State()
