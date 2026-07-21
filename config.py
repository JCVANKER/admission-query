import os
from datetime import timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-2024")
    DATABASE = os.path.join(BASE_DIR, "admission.db")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")

    # 密码使用哈希存储：环境变量传入明文，自动生成哈希
    # 默认密码 admin123456 的哈希值（生产环境请通过环境变量覆盖）
    _raw_password = os.environ.get("ADMIN_PASSWORD", "admin123456")
    ADMIN_PASSWORD_HASH = generate_password_hash(_raw_password)

    # Session 30 分钟无操作自动过期
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # 登录暴力破解防护：同 IP 连续失败上限
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 30
