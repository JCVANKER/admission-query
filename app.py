import random
import sqlite3
import os
import csv
import io
import time
from datetime import datetime

from flask import Flask, g, render_template, request, jsonify, redirect, url_for, flash, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from config import Config


app = Flask(__name__)
app.config.from_object(Config)

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
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS admissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            class_type TEXT DEFAULT 'kete',
            grade TEXT DEFAULT '',
            score TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_admissions_name ON admissions(name);

        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            admitted INTEGER DEFAULT 0,
            class_type TEXT DEFAULT '',
            schedule_date TEXT DEFAULT '',
            schedule_time TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_query_logs_name ON query_logs(name);
    """)
    # 兼容旧数据库：如果 admissions 表没有 class_type 列，自动添加
    try:
        db.execute("SELECT class_type FROM admissions LIMIT 1")
    except sqlite3.OperationalError:
        db.execute("ALTER TABLE admissions ADD COLUMN class_type TEXT DEFAULT 'kete'")
    try:
        db.execute("SELECT class_type FROM query_logs LIMIT 1")
    except sqlite3.OperationalError:
        db.execute("ALTER TABLE query_logs ADD COLUMN class_type TEXT DEFAULT ''")
    db.commit()
    db.close()


# ──────────────────── 班型配置 ────────────────────

CLASS_TYPES = {
    "kete": {"name": "科特班", "title": "科特班·英才计划录取结果查询", "category": "科特班·英才计划"},
    "yucai": {"name": "育才班", "title": "育才班·英才计划录取结果查询", "category": "育才班·英才计划"},
}


# ──────────────────── 辅助函数 ────────────────────

def generate_grade():
    """生成综合成绩：A-、A、A+"""
    grades = ["A-", "A", "A+"]
    weights = [0.2, 0.5, 0.3]  # A- 20%, A 50%, A+ 30%
    return random.choices(grades, weights=weights)[0]


def generate_score():
    """生成综合得分：91.3 到 97.6 之间，保留一位小数"""
    return round(random.uniform(91.3, 97.6), 1)


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

    if username == app.config["ADMIN_USERNAME"] and password == app.config["ADMIN_PASSWORD"]:
        session["admin_logged_in"] = True
        return jsonify({"success": True})
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


@app.route("/api/query")
def query():
    """查询是否被录取"""
    name = request.args.get("name", "").strip()
    class_type = request.args.get("class_type", "kete").strip()

    if not name:
        return jsonify({"success": False, "message": "请输入姓名"})

    db = get_db()
    row = db.execute(
        "SELECT name, category, class_type, grade, score FROM admissions WHERE name = ? AND class_type = ?",
        (name, class_type)
    ).fetchone()

    if row:
        # 已有记录，返回固定值
        grade = row["grade"] or generate_grade()
        score = row["score"] or str(generate_score())
        # 如果之前没有生成过，更新到数据库
        if not row["grade"] or not row["score"]:
            db.execute(
                "UPDATE admissions SET grade = ?, score = ? WHERE name = ? AND class_type = ?",
                (grade, score, name, class_type)
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
            "score": score
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
    return jsonify({"total": total, "kete": kete, "yucai": yucai})


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
            f"SELECT id, name, category, class_type, created_at FROM admissions WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page]
        ).fetchall()
    else:
        count = db.execute("SELECT COUNT(*) as cnt FROM admissions").fetchone()["cnt"]
        rows = db.execute(
            "SELECT id, name, category, class_type, created_at FROM admissions ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page)
        ).fetchall()

    return jsonify({
        "total": count,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows]
    })


@app.route("/api/admin/delete/<int:record_id>", methods=["DELETE"])
@api_login_required
def admin_delete(record_id):
    db = get_db()
    db.execute("DELETE FROM admissions WHERE id = ?", (record_id,))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/admin/clear", methods=["DELETE"])
@api_login_required
def admin_clear():
    db = get_db()
    db.execute("DELETE FROM admissions")
    db.commit()
    return jsonify({"success": True})


# ──────────────────── 查询日志 ────────────────────

@app.route("/api/schedule/confirm", methods=["POST"])
def schedule_confirm():
    """用户确认上课安排"""
    data = request.get_json()
    name = data.get("name", "").strip()
    date = data.get("date", "").strip()
    time_slot = data.get("time", "").strip()

    if not name:
        return jsonify({"success": False, "message": "缺少姓名"})

    db = get_db()
    # 更新最近一条该姓名的录取查询日志
    db.execute(
        "UPDATE query_logs SET schedule_date = ?, schedule_time = ? WHERE name = ? AND admitted = 1 AND id = (SELECT MAX(id) FROM query_logs WHERE name = ? AND admitted = 1)",
        (date, time_slot, name, name)
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

    db = get_db()

    if search:
        count = db.execute(
            "SELECT COUNT(*) as cnt FROM query_logs WHERE name LIKE ?",
            (f"%{search}%",)
        ).fetchone()["cnt"]
        rows = db.execute(
            "SELECT id, name, admitted, class_type, schedule_date, schedule_time, created_at FROM query_logs WHERE name LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (f"%{search}%", per_page, (page - 1) * per_page)
        ).fetchall()
    else:
        count = db.execute("SELECT COUNT(*) as cnt FROM query_logs").fetchone()["cnt"]
        rows = db.execute(
            "SELECT id, name, admitted, class_type, schedule_date, schedule_time, created_at FROM query_logs ORDER BY id DESC LIMIT ? OFFSET ?",
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
        "SELECT name, admitted, class_type, schedule_date, schedule_time, created_at FROM query_logs ORDER BY id DESC"
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["姓名", "班型", "录取状态", "上课日期", "上课时段", "查询时间"])
    for r in rows:
        writer.writerow([
            r["name"],
            CLASS_TYPES.get(r["class_type"], {}).get("name", r["class_type"] or "-"),
            "已录取" if r["admitted"] else "未录取",
            r["schedule_date"] or "-",
            r["schedule_time"] or "-",
            r["created_at"]
        ])

    output.seek(0)
    resp = make_response(output.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
    resp.headers["Content-Disposition"] = "attachment; filename=query_logs.csv"
    return resp


# ──────────────────── 启动 ────────────────────

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
