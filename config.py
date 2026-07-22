import os
from datetime import timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-2024")

    # MySQL 数据库配置
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
    MYSQL_USER = os.environ.get("MYSQL_USER", "admission")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "Adm1ssion@2026!")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "admission")

    # 保留 SQLite 路径以兼容旧配置引用
    DATABASE = os.path.join(BASE_DIR, "admission.db")

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")

    _raw_password = os.environ.get("ADMIN_PASSWORD", "admin123456")
    ADMIN_PASSWORD_HASH = generate_password_hash(_raw_password)

    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 30
