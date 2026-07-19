import sqlite3
import os
from datetime import datetime

from flask import Flask, g, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from config import Config


app = Flask(__name__)
app.config.from_object(Config)


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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_admissions_name ON admissions(name);
    """)
    db.commit()
    db.close()


# ──────────────────── 认证 ────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login_page"))
        return f(*args, **kwargs)
    return decorated


# ──────────────────── 前端路由 ────────────────────

@app.route("/")
def index():
    """用户查询首页"""
    return render_template("index.html")


@app.route("/api/query")
def query():
    """查询是否被录取"""
    name = request.args.get("name", "").strip()

    if not name:
        return jsonify({"success": False, "message": "请输入姓名"})

    db = get_db()
    row = db.execute("SELECT name, category FROM admissions WHERE name = ?", (name,)).fetchone()

    if row:
        return jsonify({
            "success": True,
            "admitted": True,
            "name": row["name"],
            "category": row["category"]
        })
    else:
        return jsonify({"success": True, "admitted": False, "message": "未查询到录取信息"})


# ──────────────────── 管理后台路由 ────────────────────

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


@app.route("/api/admin/stats")
@login_required
def admin_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) as cnt FROM admissions").fetchone()["cnt"]
    return jsonify({"total": total})


@app.route("/api/admin/upload", methods=["POST"])
@login_required
def admin_upload():
    """上传录取名单 - 支持 JSON、纯文本、CSV"""
    data = request.get_json()
    if not data or "names" not in data:
        return jsonify({"success": False, "message": "未收到数据"})

    names = data["names"]
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

        # 检查重复（按姓名去重）
        existing = db.execute("SELECT id FROM admissions WHERE name = ?", (name,)).fetchone()

        if existing:
            skipped += 1
            continue

        try:
            db.execute("INSERT INTO admissions (name, category) VALUES (?, ?)", (name, category))
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
@login_required
def admin_list():
    """分页获取录取名单"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "").strip()

    db = get_db()

    if search:
        count = db.execute(
            "SELECT COUNT(*) as cnt FROM admissions WHERE name LIKE ?",
            (f"%{search}%",)
        ).fetchone()["cnt"]
        rows = db.execute(
            "SELECT id, name, category, created_at FROM admissions WHERE name LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (f"%{search}%", per_page, (page - 1) * per_page)
        ).fetchall()
    else:
        count = db.execute("SELECT COUNT(*) as cnt FROM admissions").fetchone()["cnt"]
        rows = db.execute(
            "SELECT id, name, category, created_at FROM admissions ORDER BY id DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page)
        ).fetchall()

    return jsonify({
        "total": count,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows]
    })


@app.route("/api/admin/delete/<int:record_id>", methods=["DELETE"])
@login_required
def admin_delete(record_id):
    db = get_db()
    db.execute("DELETE FROM admissions WHERE id = ?", (record_id,))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/admin/clear", methods=["DELETE"])
@login_required
def admin_clear():
    db = get_db()
    db.execute("DELETE FROM admissions")
    db.commit()
    return jsonify({"success": True})


# ──────────────────── 启动 ────────────────────

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
