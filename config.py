import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "career_guidance_secret_key")
    PORT = int(os.getenv("PORT", "5000"))
    DB_PATH = os.path.join("instance", "career.db")
