import os
import sys
from datetime import timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production-2024")

    # 数据库类型: "mysql" 或 "sqlite"，默认自动检测
    # 设置 DB_TYPE=sqlite 强制使用 SQLite（Render 免费层等无 MySQL 的环境）
    # 设置 DB_TYPE=mysql 或提供 MYSQL_HOST 环境变量则使用 MySQL
    DB_TYPE = os.environ.get("DB_TYPE", "").lower()

    # MySQL 数据库配置
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
    MYSQL_USER = os.environ.get("MYSQL_USER", "admission")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "Adm1ssion@2026!")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "admission")

    # SQLite 路径（优先使用 Render 持久磁盘 /data 目录）
    _data_dir = os.environ.get("RENDER_DATA_DIR", os.environ.get("DATA_DIR", ""))
    if _data_dir and os.path.isdir(_data_dir):
        DATABASE = os.path.join(_data_dir, "admission.db")
    else:
        # 回退：检查 /data（Render 磁盘默认挂载点）
        _fallback = "/data"
        if os.path.isdir(_fallback):
            DATABASE = os.path.join(_fallback, "admission.db")
        else:
            DATABASE = os.path.join(BASE_DIR, "admission.db")

    print(f"[Config] DATABASE path: {DATABASE}", file=sys.stderr)

    # 自动检测数据库类型：如果没设 DB_TYPE 且没设 MYSQL_HOST，默认 SQLite
    if not DB_TYPE:
        if MYSQL_HOST:
            DB_TYPE = "mysql"
        else:
            DB_TYPE = "sqlite"

    print(f"[Config] DB_TYPE={DB_TYPE}", file=sys.stderr)

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")

    _raw_password = os.environ.get("ADMIN_PASSWORD", "admin123456")
    ADMIN_PASSWORD_HASH = generate_password_hash(_raw_password)

    # 录取名单删除操作二次确认密码（与登录密码独立）
    DELETE_CONFIRM_PASSWORD = os.environ.get("DELETE_CONFIRM_PASSWORD", "changsha123456")

    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 30
