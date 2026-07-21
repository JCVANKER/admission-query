import random
import sqlite3
import os
import csv
import io
import time
import json
from datetime import datetime

from flask import Flask, g, render_template, request, jsonify, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from config import Config


app = Flask(__name__)
app.config.from_object(Config)

# Session 过期配置
app.config["PERMANENT_SESSION_LIFETIME"] = Config.PERMANENT_SESSION_LIFETIME

# 静态文件版本号：基于 app.py 修改时间，部署更新后自动变化，强制浏览器刷新缓存
APP_VERSION = str(int(os.path.getmtime(__file__)))

@app.context_processor
def inject_version():
    return dict(app_version=APP_VERSION)


# ──────────────────── 数据库 ────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """初始化数据库表结构并执行自动迁移"""
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA journal_mode=WAL")

    # 创建基础表（使用 datetime('now', 'localtime') 确保北京时间）
    db.executescript("""
        CREATE TABLE IF NOT EXISTS admissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            class_type TEXT DEFAULT 'kete',
            grade TEXT DEFAULT '',
            score TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_admissions_name ON admissions(name);

        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            admitted INTEGER DEFAULT 0,
            class_type TEXT DEFAULT '',
            schedule_date TEXT DEFAULT '',
            schedule_time TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_query_logs_name ON query_logs(name);

        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            admin_user TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS captcha_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            answer INTEGER NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            success INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address, created_at);

        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );
    """)

    # 获取当前 schema 版本
    cur = db.execute("SELECT MAX(version) FROM schema_version")
    row = cur.fetchone()
    current_version = row[0] if row[0] is not None else 0

    # 迁移脚本列表（按版本号递增）
    migrations = {
        1: [
            "ALTER TABLE admissions ADD COLUMN class_type TEXT DEFAULT 'kete'",
            "ALTER TABLE query_logs ADD COLUMN class_type TEXT DEFAULT ''",
        ],
        2: [
            "CREATE TABLE IF NOT EXISTS admin_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, target TEXT DEFAULT '', detail TEXT DEFAULT '', admin_user TEXT DEFAULT 'admin', created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS captcha_store (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, answer INTEGER NOT NULL, used INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')))",
        ],
        3: [
            # 为现有表添加触发器，在插入时将 UTC 时间转换为北京时间
            "DROP TRIGGER IF EXISTS trg_admissions_localtime",
            "CREATE TRIGGER trg_admissions_localtime AFTER INSERT ON admissions BEGIN UPDATE admissions SET created_at = datetime(NEW.created_at, '+8 hours') WHERE id = NEW.id; END",
            "DROP TRIGGER IF EXISTS trg_query_logs_localtime",
            "CREATE TRIGGER trg_query_logs_localtime AFTER INSERT ON query_logs BEGIN UPDATE query_logs SET created_at = datetime(NEW.created_at, '+8 hours') WHERE id = NEW.id; END",
            "DROP TRIGGER IF EXISTS trg_audit_log_localtime",
            "CREATE TRIGGER trg_audit_log_localtime AFTER INSERT ON admin_audit_log BEGIN UPDATE admin_audit_log SET created_at = datetime(NEW.created_at, '+8 hours') WHERE id = NEW.id; END",
            "DROP TRIGGER IF EXISTS trg_captcha_store_localtime",
            "CREATE TRIGGER trg_captcha_store_localtime AFTER INSERT ON captcha_store BEGIN UPDATE captcha_store SET created_at = datetime(NEW.created_at, '+8 hours') WHERE id = NEW.id; END",
        ],
        4: [
            "ALTER TABLE query_logs ADD COLUMN needs TEXT DEFAULT ''",
        ],
        5: [
            "CREATE TABLE IF NOT EXISTS login_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, ip_address TEXT NOT NULL, success INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')))",
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address, created_at)",
        ],
    }

    # 按序执行未应用的迁移
    for ver in sorted(migrations.keys()):
        if ver <= current_version:
            continue
        sqls = migrations[ver]
        if not sqls:
            continue  # 空迁移跳过
        for sql in sqls:
            try:
                db.execute(sql)
            except sqlite3.OperationalError as e:
                # 列已存在则跳过（幂等）
                if "duplicate column" in str(e).lower():
                    pass
                else:
                    raise
        db.execute("INSERT INTO schema_version (version) VALUES (?)", (ver,))
        print(f"[DB Migration] v{ver} applied")

    db.commit()
    db.close()


# 应用启动时自动执行数据库初始化
init_db()


# ──────────────────── 班型配置 ────────────────────

CLASS_TYPES = {
    "kete": {"name": "科特班", "title": "科特班·英才计划录取结果查询", "category": "科特班·英才计划"},
    "yucai": {"name": "育才班", "title": "育才班·英才计划录取结果查询", "category": "育才班·英才计划"},
}


# ──────────────────── 辅助函数 ────────────────────

def generate_grade():
    """生成综合成绩排名：前1% 到 前9% 随机取值"""
    pct = random.randint(1, 9)
    return f"前{pct}%"


def generate_score():
    """废弃：原综合得分，新需求改为百分比排名。保留函数以兼容旧数据读取。"""
    return round(random.uniform(91.3, 97.6), 1)


def generate_captcha():
    """生成数学验证码，返回 (表达式, 答案)"""
    ops = [
        ("+", lambda a, b: a + b),
        ("-", lambda a, b: a - b),
        ("×", lambda a, b: a * b),
    ]
    op_symbol, op_func = random.choice(ops)
    if op_symbol == "×":
        a, b = random.randint(1, 9), random.randint(1, 9)
    elif op_symbol == "-":
        a, b = random.randint(5, 20), random.randint(1, 10)
        if a < b:
            a, b = b, a
    else:
        a, b = random.randint(1, 20), random.randint(1, 10)
    answer = op_func(a, b)
    expression = f"{a} {op_symbol} {b} = ?"
    return expression, answer


def log_audit(action, target="", detail=""):
    """记录管理后台操作日志"""
    try:
        db = sqlite3.connect(app.config["DATABASE"])
        db.execute(
            "INSERT INTO admin_audit_log (action, target, detail) VALUES (?, ?, ?)",
            (action, target, detail)
        )
        db.commit()
        db.close()
    except Exception:
        pass  # 日志记录失败不阻塞主流程


# ──────────────────── 认证 ────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    """API 专用认证：未登录返回 JSON 401 而非重定向"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"success": False, "message": "未登录，请先登录", "code": 401}), 401
        return f(*args, **kwargs)
    return decorated


# ──────────────────── 前端路由 ────────────────────

@app.route("/")
def root():
    """根路径跳转到默认班型（科特班）"""
    return redirect("/kete")


# ⚠️ /admin 必须在 /<class_type> 之前注册，否则会被捕获为 class_type="admin"
@app.route("/admin")
def admin_login_page():
    return render_template("admin_login.html")


@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    client_ip = request.remote_addr or "unknown"

    db = get_db()

    # 检查是否被锁定：最近 LOGIN_LOCKOUT_MINUTES 分钟内连续失败 MAX_LOGIN_ATTEMPTS 次
    lockout_cutoff = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    failed_count = db.execute(
        """SELECT COUNT(*) as cnt FROM login_attempts
           WHERE ip_address = ? AND success = 0
           AND datetime(created_at, ?) > datetime('now', 'localtime')""",
        (client_ip, f"+{app.config['LOGIN_LOCKOUT_MINUTES']} minutes")
    ).fetchone()["cnt"]

    if failed_count >= app.config["MAX_LOGIN_ATTEMPTS"]:
        remaining = app.config["LOGIN_LOCKOUT_MINUTES"]
        return jsonify({
            "success": False,
            "message": f"登录尝试次数过多，请 {remaining} 分钟后再试"
        })

    # 验证用户名 + 密码哈希
    if username == app.config["ADMIN_USERNAME"] and check_password_hash(app.config["ADMIN_PASSWORD_HASH"], password):
        session["admin_logged_in"] = True
        session.permanent = True  # 启用 PERMANENT_SESSION_LIFETIME
        db.execute(
            "INSERT INTO login_attempts (ip_address, success) VALUES (?, 1)",
            (client_ip,)
        )
        db.commit()
        return jsonify({"success": True})

    # 登录失败：记录并延迟响应
    db.execute(
        "INSERT INTO login_attempts (ip_address, success) VALUES (?, 0)",
        (client_ip,)
    )
    db.commit()

    # 失败后延迟 1 秒，增加暴力破解成本
    time.sleep(1)
    return jsonify({"success": False, "message": "账号或密码错误"})


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login_page"))


@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    return render_template("admin_dashboard.html")


@app.route("/<class_type>")
def index(class_type):
    """用户查询首页，class_type 区分班型"""
    if class_type not in CLASS_TYPES:
        return redirect("/kete")
    ct = CLASS_TYPES[class_type]
    return render_template("index.html", class_type=class_type, class_name=ct["name"], page_title=ct["title"])


@app.route("/<class_type>/result")
def result_page(class_type):
    """录取结果页（独立页面）"""
    if class_type not in CLASS_TYPES:
        return redirect("/kete/result")
    ct = CLASS_TYPES[class_type]
    name = request.args.get("name", "")
    category = request.args.get("category", ct["category"])
    grade = request.args.get("grade", "")
    score = request.args.get("score", "")
    return render_template("result.html",
        class_type=class_type,
        class_name=ct["name"],
        category=category,
        name=name,
        grade=grade,
        score=score)


@app.route("/<class_type>/invite")
def invite_page(class_type):
    """入学邀请函独立页面"""
    if class_type not in CLASS_TYPES:
        return redirect("/kete/invite")
    ct = CLASS_TYPES[class_type]
    student_name = request.args.get("name", "")
    badge_text = f"英才计划录取资格"
    today = datetime.now().strftime("%Y年%m月%d日")
    return render_template("invite.html",
        class_type=class_type,
        class_name=ct["name"],
        student_name=student_name,
        badge_text=badge_text,
        today_date=today)


@app.route("/api/captcha")
def get_captcha():
    """生成数学验证码，返回 token 和表达式（先生成时自动清理过期验证码）"""
    import uuid

    # 自动清理超过10分钟的未使用验证码
    # 注意：created_at 存储的是 UTC 时间（触发器已转换），所以用 datetime('now') 比较
    db = get_db()
    db.execute(
        "DELETE FROM captcha_store WHERE used = 0 AND datetime(created_at, '+10 minutes') < datetime('now')"
    )
    db.commit()

    expression, answer = generate_captcha()
    token = uuid.uuid4().hex[:16]

    db.execute(
        "INSERT INTO captcha_store (token, answer) VALUES (?, ?)",
        (token, answer)
    )
    db.commit()
    return jsonify({"token": token, "expression": expression})


@app.route("/api/query")
def query():
    """查询是否被录取"""
    name = request.args.get("name", "").strip()
    class_type = request.args.get("class_type", "kete").strip()
    captcha_token = request.args.get("captcha_token", "").strip()
    captcha_answer = request.args.get("captcha_answer", "").strip()

    if not name:
        return jsonify({"success": False, "message": "请输入姓名"})

    # 验证验证码
    db = get_db()
    if captcha_token and captcha_answer:
        captcha_row = db.execute(
            "SELECT answer, used FROM captcha_store WHERE token = ?",
            (captcha_token,)
        ).fetchone()
        if not captcha_row:
            return jsonify({"success": False, "message": "验证码已过期，请刷新后重试"})
        if captcha_row["used"]:
            return jsonify({"success": False, "message": "验证码已使用，请刷新后重试"})
        try:
            if int(captcha_answer) != captcha_row["answer"]:
                return jsonify({"success": False, "message": "验证码错误，请重新输入"})
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "验证码格式错误"})
        # 标记验证码已使用
        db.execute("UPDATE captcha_store SET used = 1 WHERE token = ?", (captcha_token,))
        db.commit()
    else:
        return jsonify({"success": False, "message": "请输入验证码"})

    db = get_db()
    row = db.execute(
        "SELECT name, category, class_type, grade, score FROM admissions WHERE name = ? AND class_type = ?",
        (name, class_type)
    ).fetchone()

    if row:
        # 已有记录，返回固定值
        grade = row["grade"] or generate_grade()
        # 如果之前没有生成过，更新到数据库
        if not row["grade"]:
            db.execute(
                "UPDATE admissions SET grade = ? WHERE name = ? AND class_type = ?",
                (grade, name, class_type)
            )
            db.commit()
        # 记录查询日志
        ct = CLASS_TYPES.get(class_type, CLASS_TYPES["kete"])
        category = row["category"] or ct["category"]
        db.execute(
            "INSERT INTO query_logs (name, admitted, class_type) VALUES (?, 1, ?)",
            (name, class_type)
        )
        db.commit()
        return jsonify({
            "success": True,
            "admitted": True,
            "name": row["name"],
            "category": category,
            "class_type": class_type,
            "grade": grade,
            "score": ""
        })
    else:
        # 记录未录取查询
        db.execute(
            "INSERT INTO query_logs (name, admitted, class_type) VALUES (?, 0, ?)",
            (name, class_type)
        )
        db.commit()
        return jsonify({"success": True, "admitted": False, "message": "未查询到录取信息"})


# ──────────────────── 管理后台 API ────────────────────


@app.route("/api/admin/stats")
@api_login_required
def admin_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) as cnt FROM admissions").fetchone()["cnt"]
    kete = db.execute("SELECT COUNT(*) as cnt FROM admissions WHERE class_type = 'kete'").fetchone()["cnt"]
    yucai = db.execute("SELECT COUNT(*) as cnt FROM admissions WHERE class_type = 'yucai'").fetchone()["cnt"]

    # 今日查询数（使用 datetime('now', 'localtime') 确保北京时间）
    today = datetime.now().strftime("%Y-%m-%d")
    today_queries = db.execute(
        "SELECT COUNT(*) as cnt FROM query_logs WHERE date(created_at, 'localtime') = ?",
        (today,)
    ).fetchone()["cnt"]

    # 总查询数
    total_queries = db.execute("SELECT COUNT(*) as cnt FROM query_logs").fetchone()["cnt"]

    # 已提交需求数
    confirmed = db.execute(
        "SELECT COUNT(*) as cnt FROM query_logs WHERE needs != ''"
    ).fetchone()["cnt"]

    # 录取率（被录取的查询 / 总查询）
    admitted_count = db.execute(
        "SELECT COUNT(*) as cnt FROM query_logs WHERE admitted = 1"
    ).fetchone()["cnt"]

    admission_rate = round(admitted_count / total_queries * 100, 1) if total_queries > 0 else 0

    # 今日新增录取名单
    today_new = db.execute(
        "SELECT COUNT(*) as cnt FROM admissions WHERE date(created_at, 'localtime') = ?",
        (today,)
    ).fetchone()["cnt"]

    return jsonify({
        "total": total,
        "kete": kete,
        "yucai": yucai,
        "today_queries": today_queries,
        "total_queries": total_queries,
        "confirmed": confirmed,
        "admission_rate": admission_rate,
        "today_new": today_new
    })


@app.route("/api/admin/upload", methods=["POST"])
@api_login_required
def admin_upload():
    """上传录取名单 - 支持 JSON、纯文本、CSV"""
    data = request.get_json()
    if not data or "names" not in data:
        return jsonify({"success": False, "message": "未收到数据"})

    names = data["names"]
    class_type = data.get("class_type", "kete")

    if not names:
        return jsonify({"success": False, "message": "名单为空"})

    db = get_db()
    inserted = 0
    skipped = 0
    errors = []

    for item in names:
        name = item.get("name", "").strip() if isinstance(item, dict) else str(item).strip()
        category = item.get("category", "").strip() if isinstance(item, dict) else ""

        if not name:
            continue

        # 检查重复（同班型按姓名去重）
        existing = db.execute(
            "SELECT id FROM admissions WHERE name = ? AND class_type = ?",
            (name, class_type)
        ).fetchone()

        if existing:
            skipped += 1
            continue

        try:
            db.execute(
                "INSERT INTO admissions (name, category, class_type) VALUES (?, ?, ?)",
                (name, category, class_type)
            )
            inserted += 1
        except Exception as e:
            errors.append(str(e))

    db.commit()

    log_audit("上传录取名单", f"{CLASS_TYPES.get(class_type, {}).get('name', class_type)}", f"成功 {inserted} 条，跳过 {skipped} 条")

    return jsonify({
        "success": True,
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors
    })


@app.route("/api/admin/list")
@api_login_required
def admin_list():
    """分页获取录取名单"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "").strip()
    filter_class = request.args.get("class_type", "").strip()

    db = get_db()

    if search or filter_class:
        conditions = []
        params = []
        if search:
            conditions.append("name LIKE ?")
            params.append(f"%{search}%")
        if filter_class:
            conditions.append("class_type = ?")
            params.append(filter_class)
        where = " AND ".join(conditions)
        count = db.execute(
            f"SELECT COUNT(*) as cnt FROM admissions WHERE {where}",
            params
        ).fetchone()["cnt"]
        rows = db.execute(
            f"SELECT id, name, class_type, created_at FROM admissions WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page]
        ).fetchall()
    else:
        count = db.execute("SELECT COUNT(*) as cnt FROM admissions").fetchone()["cnt"]
        rows = db.execute(
            "SELECT id, name, class_type, created_at FROM admissions ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page)
        ).fetchall()

    return jsonify({
        "total": count,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows]
    })


@app.route("/api/admin/update/<int:record_id>", methods=["PUT"])
@api_login_required
def admin_update(record_id):
    """编辑录取名单的姓名或班型"""
    data = request.get_json()
    new_name = data.get("name", "").strip()
    new_class_type = data.get("class_type", "").strip()

    if not new_name:
        return jsonify({"success": False, "message": "姓名不能为空"})
    if new_class_type not in CLASS_TYPES:
        return jsonify({"success": False, "message": "班型无效"})

    db = get_db()
    # 检查目标姓名+班型是否已存在（排除自身）
    existing = db.execute(
        "SELECT id FROM admissions WHERE name = ? AND class_type = ? AND id != ?",
        (new_name, new_class_type, record_id)
    ).fetchone()
    if existing:
        return jsonify({"success": False, "message": "该姓名在此班型下已存在"})

    # 获取旧记录用于日志
    old = db.execute(
        "SELECT name, class_type FROM admissions WHERE id = ?", (record_id,)
    ).fetchone()
    if not old:
        return jsonify({"success": False, "message": "记录不存在"})

    db.execute(
        "UPDATE admissions SET name = ?, class_type = ? WHERE id = ?",
        (new_name, new_class_type, record_id)
    )
    db.commit()

    log_audit("编辑录取名单",
              old["name"],
              f"姓名: {old['name']}→{new_name}, 班型: {CLASS_TYPES.get(old['class_type'], {}).get('name', old['class_type'])}→{CLASS_TYPES.get(new_class_type, {}).get('name', new_class_type)}")

    return jsonify({"success": True})


@app.route("/api/admin/list/export")
@api_login_required
def admin_list_export():
    """导出录取名单为 CSV"""
    db = get_db()
    rows = db.execute(
        "SELECT name, class_type, created_at FROM admissions ORDER BY id DESC"
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["姓名", "班型", "添加时间"])
    for r in rows:
        writer.writerow([
            r["name"],
            CLASS_TYPES.get(r["class_type"], {}).get("name", r["class_type"] or "-"),
            r["created_at"]
        ])

    output.seek(0)
    resp = make_response(output.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
    resp.headers["Content-Disposition"] = "attachment; filename=admissions_list.csv"
    return resp


@app.route("/api/admin/delete/<int:record_id>", methods=["DELETE"])
@api_login_required
def admin_delete(record_id):
    db = get_db()
    # 先查记录信息用于日志
    row = db.execute("SELECT name, class_type FROM admissions WHERE id = ?", (record_id,)).fetchone()
    db.execute("DELETE FROM admissions WHERE id = ?", (record_id,))
    db.commit()
    if row:
        log_audit("删除录取名单", row["name"], f"班型: {CLASS_TYPES.get(row['class_type'], {}).get('name', row['class_type'])}")
    return jsonify({"success": True})


@app.route("/api/admin/batch-delete", methods=["POST"])
@api_login_required
def admin_batch_delete():
    """批量删除录取名单"""
    data = request.get_json()
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"success": False, "message": "未选择记录"})
    db = get_db()
    placeholders = ",".join("?" * len(ids))
    db.execute(f"DELETE FROM admissions WHERE id IN ({placeholders})", ids)
    db.commit()
    log_audit("批量删除录取名单", "", f"删除 {len(ids)} 条记录")
    return jsonify({"success": True, "deleted": len(ids)})


@app.route("/api/admin/clear", methods=["DELETE"])
@api_login_required
def admin_clear():
    db = get_db()
    db.execute("DELETE FROM admissions")
    db.commit()
    log_audit("清空录取名单", "", "已清空全部录取名单")
    return jsonify({"success": True})


# ──────────────────── 查询日志 ────────────────────

@app.route("/api/schedule/confirm", methods=["POST"])
def schedule_confirm():
    """用户提交培养需求"""
    data = request.get_json()
    name = data.get("name", "").strip()
    needs = data.get("needs", [])

    if not name:
        return jsonify({"success": False, "message": "缺少姓名"})

    needs_str = ",".join(needs) if isinstance(needs, list) else ""

    db = get_db()
    db.execute(
        "UPDATE query_logs SET needs = ? WHERE name = ? AND admitted = 1 AND id = (SELECT MAX(id) FROM query_logs WHERE name = ? AND admitted = 1)",
        (needs_str, name, name)
    )
    db.commit()
    return jsonify({"success": True})


@app.route("/api/admin/logs")
@api_login_required
def admin_logs():
    """分页获取查询日志"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "").strip()
    filter_class = request.args.get("class_type", "").strip()

    db = get_db()

    conditions = []
    params = []
    if search:
        conditions.append("name LIKE ?")
        params.append(f"%{search}%")
    if filter_class:
        conditions.append("class_type = ?")
        params.append(filter_class)

    if conditions:
        where = " AND ".join(conditions)
        count = db.execute(
            f"SELECT COUNT(*) as cnt FROM query_logs WHERE {where}", params
        ).fetchone()["cnt"]
        rows = db.execute(
            f"SELECT id, name, admitted, class_type, needs, created_at FROM query_logs WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page]
        ).fetchall()
    else:
        count = db.execute("SELECT COUNT(*) as cnt FROM query_logs").fetchone()["cnt"]
        rows = db.execute(
            "SELECT id, name, admitted, class_type, needs, created_at FROM query_logs ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page)
        ).fetchall()

    return jsonify({
        "total": count,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows]
    })


@app.route("/api/admin/logs/export")
@api_login_required
def admin_logs_export():
    """导出查询日志为 CSV"""
    db = get_db()
    rows = db.execute(
        "SELECT name, admitted, class_type, needs, created_at FROM query_logs ORDER BY id DESC"
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["姓名", "班型", "录取状态", "培养需求", "查询时间"])
    for r in rows:
        writer.writerow([
            r["name"],
            CLASS_TYPES.get(r["class_type"], {}).get("name", r["class_type"] or "-"),
            "已录取" if r["admitted"] else "未录取",
            r["needs"] or "-",
            r["created_at"]
        ])

    output.seek(0)
    resp = make_response(output.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
    resp.headers["Content-Disposition"] = "attachment; filename=query_logs.csv"
    return resp


@app.route("/api/admin/logs/batch-delete", methods=["POST"])
@api_login_required
def admin_logs_batch_delete():
    """批量删除查询日志"""
    data = request.get_json()
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"success": False, "message": "未选择记录"})
    db = get_db()
    placeholders = ",".join("?" * len(ids))
    db.execute(f"DELETE FROM query_logs WHERE id IN ({placeholders})", ids)
    db.commit()
    log_audit("批量删除查询日志", "", f"删除 {len(ids)} 条日志")
    return jsonify({"success": True, "deleted": len(ids)})


@app.route("/api/admin/logs/clear", methods=["DELETE"])
@api_login_required
def admin_logs_clear():
    """清空全部查询日志"""
    db = get_db()
    db.execute("DELETE FROM query_logs")
    db.commit()
    log_audit("清空查询日志", "", "已清空全部查询日志")
    return jsonify({"success": True})


# ──────────────────── 操作日志 ────────────────────

@app.route("/api/admin/audit-logs")
@api_login_required
def admin_audit_logs():
    """分页获取管理后台操作日志"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    db = get_db()
    count = db.execute("SELECT COUNT(*) as cnt FROM admin_audit_log").fetchone()["cnt"]
    rows = db.execute(
        "SELECT id, action, target, detail, admin_user, created_at FROM admin_audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
        (per_page, (page - 1) * per_page)
    ).fetchall()

    return jsonify({
        "total": count,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows]
    })


@app.route("/api/admin/audit-logs/clear", methods=["DELETE"])
@api_login_required
def admin_audit_logs_clear():
    """清空操作日志"""
    db = get_db()
    db.execute("DELETE FROM admin_audit_log")
    db.commit()
    return jsonify({"success": True})


# ──────────────────── 定期清理过期验证码 ────────────────────

@app.route("/api/captcha/cleanup")
def captcha_cleanup():
    """手动触发清理超过10分钟的未使用验证码"""
    db = get_db()
    db.execute("DELETE FROM captcha_store WHERE used = 0 AND datetime(created_at, '+10 minutes') < datetime('now')")
    db.commit()
    return jsonify({"success": True})


# ──────────────────── 启动 ────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
