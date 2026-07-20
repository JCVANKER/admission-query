import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # ⚠️ 生产环境请务必修改以下三项
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-2024")
    DATABASE = os.path.join(BASE_DIR, "admission.db")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123456")
