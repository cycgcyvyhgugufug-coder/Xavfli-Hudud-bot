import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8921125294:AAGVGELVKXk9k5Xjsuor5mVlkfUUB7XuTSU")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6237680057"))