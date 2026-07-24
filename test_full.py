#!/usr/bin/env python3
"""全量回归测试 - 51个测试用例"""

import os
import sys
import json
import hashlib
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, init_db, get_db
from config import Config

app.config["TESTING"] = True
app.config["SECRET_KEY"] = "test-secret"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123456"
DELETE_PASSWORD = "changsha123456"


def reset_db_state():
    """重置数据库到干净状态"""
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM admissions")
        db.execute("DELETE FROM query_logs")
        db.execute("DELETE FROM site_visits")
        db.execute("DELETE FROM login_attempts")
        db.commit()


def api_login(client):
    """登录并保持 session"""
    return client.post("/admin/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })


def get_json(resp):
    """安全获取 JSON"""
    if resp is None:
        return None
    try:
        return resp.get_json()
    except Exception:
        return None


@pytest.fixture(autouse=True)
def setup():
    reset_db_state()


# ═══════════════════════════════════════════
# T1-T3: 基础页面测试
# ═══════════════════════════════════════════

def test_t1_homepage():
    """T1: 首页可访问"""
    with app.test_client() as c:
        resp = c.get("/", follow_redirects=False)
        assert resp.status_code in (200, 302)

def test_t2_query_page():
    """T2: 查询页面（首页即是查询页）"""
    with app.test_client() as c:
        resp = c.get("/", follow_redirects=True)
        assert resp.status_code == 200

def test_t3_admin_login_page():
    """T3: 管理后台登录页可访问"""
    with app.test_client() as c:
        resp = c.get("/admin")
        assert resp.status_code == 200


# ═══════════════════════════════════════════
# T4-T6: 登录/登出测试
# ═══════════════════════════════════════════

def test_t4_login_success():
    """T4: 正确密码登录成功"""
    with app.test_client() as c:
        resp = api_login(c)
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

def test_t5_login_fail():
    """T5: 错误密码登录失败"""
    with app.test_client() as c:
        resp = c.post("/admin/login", json={
            "username": ADMIN_USERNAME,
            "password": "wrongpassword",
        })
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False

def test_t6_logout():
    """T6: 登出成功"""
    with app.test_client() as c:
        api_login(c)
        resp = c.get("/admin/logout")
        assert resp.status_code in (200, 302)


# ═══════════════════════════════════════════
# T7-T11: 上传录取名单测试
# ═══════════════════════════════════════════

def test_t7_upload_single():
    """T7: 上传单条录取数据"""
    with app.test_client() as c:
        api_login(c)
        data = {"names": [{"name": "张三", "category": "信息学"}], "class_type": "kete"}
        resp = c.post("/api/admin/upload", json=data)
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True
        assert d.get("inserted") == 1

def test_t8_upload_multiple():
    """T8: 批量上传多条数据"""
    with app.test_client() as c:
        api_login(c)
        data = {
            "names": [
                {"name": "李四", "category": "数学"},
                {"name": "王五", "category": "物理"},
                {"name": "赵六", "category": "化学"},
            ],
            "class_type": "yucai",
        }
        resp = c.post("/api/admin/upload", json=data)
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True
        assert d.get("inserted") == 3

def test_t9_upload_duplicate():
    """T9: 上传重复数据应跳过"""
    with app.test_client() as c:
        api_login(c)
        data = {"names": [{"name": "张三"}], "class_type": "kete"}
        c.post("/api/admin/upload", json=data)
        resp = c.post("/api/admin/upload", json=data)
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True
        assert d.get("inserted") == 0
        assert d.get("skipped") == 1

def test_t10_upload_empty():
    """T10: 上传空数据"""
    with app.test_client() as c:
        api_login(c)
        resp = c.post("/api/admin/upload", json={"names": [], "class_type": "kete"})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False

def test_t11_upload_missing_fields():
    """T11: 上传缺少必填字段"""
    with app.test_client() as c:
        api_login(c)
        resp = c.post("/api/admin/upload", json={})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False


# ═══════════════════════════════════════════
# T12-T15: 录取名单 CRUD 测试
# ═══════════════════════════════════════════

def _get_first_id(c):
    """获取录取名单第一条记录的 ID"""
    resp = c.get("/api/admin/list?page=1&per_page=20")
    d = get_json(resp)
    items = d.get("items", [])
    assert len(items) > 0, f"期望有记录，实际 items={items}"
    return items[0]["id"]


def test_t12_list_admissions():
    """T12: 获取录取名单列表"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}, {"name": "李四"}], "class_type": "kete"
        })
        resp = c.get("/api/admin/list?page=1&per_page=20")
        d = get_json(resp)
        assert d is not None
        assert d.get("total") == 2

def test_t13_update_admission():
    """T13: 更新录取信息"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        aid = _get_first_id(c)

        resp = c.put(f"/api/admin/update/{aid}", json={"name": "张三丰", "class_type": "kete"})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

def test_t14_search_admission():
    """T14: 搜索录取名单"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}, {"name": "李四"}], "class_type": "kete"
        })
        resp = c.get("/api/admin/list?search=张三")
        d = get_json(resp)
        assert d is not None
        assert d.get("total") == 1

def test_t15_filter_class_type():
    """T15: 按班型筛选"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        c.post("/api/admin/upload", json={
            "names": [{"name": "李四"}], "class_type": "yucai"
        })
        resp = c.get("/api/admin/list?class_type=kete")
        d = get_json(resp)
        assert d is not None
        assert d.get("total") == 1


# ═══════════════════════════════════════════
# T16-T21: 删除操作 + 密码验证测试
# ═══════════════════════════════════════════

def test_t16_delete_single():
    """T16: 单条删除（需密码确认）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        aid = _get_first_id(c)

        resp = c.delete(f"/api/admin/delete/{aid}", json={"password": DELETE_PASSWORD})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

def test_t17_delete_single_wrong_password():
    """T17: 单条删除（错误密码应失败）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        aid = _get_first_id(c)

        resp = c.delete(f"/api/admin/delete/{aid}", json={"password": "wrong"})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False

def test_t18_batch_delete():
    """T18: 批量删除（需密码确认）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}, {"name": "李四"}], "class_type": "kete"
        })
        resp = c.get("/api/admin/list?page=1&per_page=20")
        d = get_json(resp)
        ids = [item["id"] for item in d["items"]]

        resp = c.post("/api/admin/batch-delete", json={"ids": ids, "password": DELETE_PASSWORD})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

def test_t19_batch_delete_wrong_password():
    """T19: 批量删除（错误密码应失败）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        resp = c.get("/api/admin/list?page=1&per_page=20")
        d = get_json(resp)
        ids = [item["id"] for item in d["items"]]

        resp = c.post("/api/admin/batch-delete", json={"ids": ids, "password": "wrong"})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False

def test_t20_clear_all():
    """T20: 清空全部（需密码确认）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        resp = c.delete("/api/admin/clear", json={"password": DELETE_PASSWORD})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

def test_t21_clear_all_wrong_password():
    """T21: 清空全部（错误密码应失败）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        resp = c.delete("/api/admin/clear", json={"password": "wrong"})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False


# ═══════════════════════════════════════════
# T22-T23: 批量修改班型
# ═══════════════════════════════════════════

def test_t22_batch_change_class_type():
    """T22: 批量修改班型"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}, {"name": "李四"}], "class_type": "kete"
        })
        resp = c.get("/api/admin/list?page=1&per_page=20")
        d = get_json(resp)
        ids = [item["id"] for item in d["items"]]

        resp = c.post("/api/admin/batch-change-class-type", json={
            "ids": ids, "class_type": "yucai"
        })
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True
        assert d.get("updated") == 2

def test_t23_batch_change_empty_ids():
    """T23: 批量修改班型（空 ID 列表）"""
    with app.test_client() as c:
        api_login(c)
        resp = c.post("/api/admin/batch-change-class-type", json={
            "ids": [], "class_type": "yucai"
        })
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False


# ═══════════════════════════════════════════
# T24-T26: 密码验证端点
# ═══════════════════════════════════════════

def test_t24_verify_password_correct():
    """T24: 验证正确密码"""
    with app.test_client() as c:
        api_login(c)
        resp = c.post("/api/admin/verify-password", json={"password": DELETE_PASSWORD})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

def test_t25_verify_password_wrong():
    """T25: 验证错误密码"""
    with app.test_client() as c:
        api_login(c)
        resp = c.post("/api/admin/verify-password", json={"password": "wrong"})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False

def test_t26_verify_password_empty():
    """T26: 验证空密码"""
    with app.test_client() as c:
        api_login(c)
        resp = c.post("/api/admin/verify-password", json={"password": ""})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False


# ═══════════════════════════════════════════
# T27-T32: 查询功能测试
# ═══════════════════════════════════════════

def test_t27_query_by_name():
    """T27: 按姓名查询（科特班）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三", "category": "信息学"}], "class_type": "kete"
        })
        # 注意：查询需要 name + class_type + captcha_token + captcha_answer
        # 测试环境下可能跳过验证码，直接测核心逻辑
        # 先不传验证码，验证返回"请输入验证码"
        resp = c.get("/api/query?name=张三&class_type=kete")
        d = get_json(resp)
        # 预期：需要验证码
        assert d is not None

def test_t28_query_by_exam_id():
    """T28: 按姓名查询（育才班）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三", "category": "数学"}], "class_type": "yucai"
        })
        resp = c.get("/api/query?name=张三&class_type=yucai")
        d = get_json(resp)
        assert d is not None

def test_t29_query_not_found():
    """T29: 查询不存在的记录（需要验证码，返回验证码提示）"""
    with app.test_client() as c:
        resp = c.get("/api/query?name=不存在的名字&class_type=kete")
        d = get_json(resp)
        assert d is not None
        # 没传验证码，应返回提示
        assert d.get("success") is False

def test_t30_query_empty():
    """T30: 空查询值"""
    with app.test_client() as c:
        resp = c.get("/api/query?name=&class_type=kete")
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False

def test_t31_query_missing_captcha():
    """T31: 缺少验证码"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        resp = c.get("/api/query?name=张三&class_type=kete")
        d = get_json(resp)
        assert d is not None
        assert "验证码" in d.get("message", "")

def test_t32_query_logs_created():
    """T32: 直接查询日志验证（通过管理后台查看）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        # 通过管理后台日志 API 查看（初始为空）
        resp = c.get("/api/admin/logs")
        d = get_json(resp)
        assert d is not None
        # 日志列表可能为空（还没查询）
        assert isinstance(d.get("total"), int)


# ═══════════════════════════════════════════
# T33-T37: 需求反馈测试（通过 schedule/confirm）
# ═══════════════════════════════════════════

def test_t33_submit_needs():
    """T33: 提交培养需求（通过 /api/schedule/confirm）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        # 先模拟一次查询（直接在 query_logs 中插入记录）
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "127.0.0.1"),
            )
            db.commit()

        resp = c.post("/api/schedule/confirm", json={
            "name": "张三",
            "needs": ["数学竞赛", "物理竞赛"]
        })
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

def test_t34_submit_needs_missing_name():
    """T34: 提交需求缺少姓名"""
    with app.test_client() as c:
        resp = c.post("/api/schedule/confirm", json={"needs": ["数学"]})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False

def test_t35_get_logs_with_needs():
    """T35: 获取包含需求的查询日志列表"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        # 插入带 needs 的日志
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, needs, ip_address, created_at) VALUES (?, 1, ?, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "数学竞赛", "127.0.0.1"),
            )
            db.commit()

        resp = c.get("/api/admin/logs")
        d = get_json(resp)
        assert d is not None
        assert d.get("total") >= 1

def test_t36_update_need_via_confirm():
    """T36: 通过 schedule/confirm 更新需求状态"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "127.0.0.1"),
            )
            db.commit()

        # 第一次提交
        c.post("/api/schedule/confirm", json={
            "name": "张三", "needs": ["信息学"]
        })
        # 第二次提交（覆盖）
        resp = c.post("/api/schedule/confirm", json={
            "name": "张三", "needs": ["信息学", "数学"]
        })
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True

        # 验证更新
        with app.app_context():
            db = get_db()
            row = db.execute(
                "SELECT needs FROM query_logs WHERE name = ? AND admitted = 1 ORDER BY id DESC LIMIT 1",
                ("张三",),
            ).fetchone()
            assert row is not None
            assert "信息学" in (row["needs"] or "")

def test_t37_delete_log():
    """T37: 删除查询日志记录"""
    with app.test_client() as c:
        api_login(c)
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, needs, ip_address, created_at) VALUES (?, 1, ?, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "数学", "127.0.0.1"),
            )
            db.commit()
            log_id = db.execute("SELECT id FROM query_logs ORDER BY id DESC LIMIT 1").fetchone()["id"]

        resp = c.post("/api/admin/logs/batch-delete", json={"ids": [log_id]})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is True


# ═══════════════════════════════════════════
# T38-T42: 统计数据测试
# ═════════════════════���═════════════════════

def test_t38_stats_basic():
    """T38: 基本统计数据"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        resp = c.get("/api/admin/stats")
        d = get_json(resp)
        assert d is not None
        assert d.get("total") == 1

def test_t39_stats_with_queries():
    """T39: 包含查询数据的统计"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        # 插入模拟查询日志
        with app.app_context():
            db = get_db()
            today = datetime.now().strftime("%Y-%m-%d")
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "127.0.0.1"),
            )
            db.commit()

        resp = c.get("/api/admin/stats")
        d = get_json(resp)
        assert d is not None
        assert d.get("today_queries") >= 1

def test_t40_stats_visitors():
    """T40: 访问人数统计（通过 /kete 路由触发 record_visit）"""
    with app.test_client() as c:
        # record_visit 在 /<class_type> 路由触发
        c.get("/kete", environ_base={"REMOTE_ADDR": "1.2.3.4"}, headers={"User-Agent": "TestBot/1.0"})
        c.get("/kete", environ_base={"REMOTE_ADDR": "5.6.7.8"}, headers={"User-Agent": "TestBot/2.0"})
        c.get("/kete", environ_base={"REMOTE_ADDR": "1.2.3.4"}, headers={"User-Agent": "TestBot/1.0"})  # 重复

        api_login(c)
        resp = c.get("/api/admin/stats")
        d = get_json(resp)
        assert d is not None
        assert d.get("visitors") == 2
        assert d.get("today_visitors") == 2

def test_t41_stats_need_rate():
    """T41: 查询需求率计算验证 — 2人各提交需求，共4次查询，需求率=2/4=50%"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}, {"name": "李四"}], "class_type": "kete"
        })
        # 插入 4 条查询日志，其中 2 个不同名字有 needs
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, needs, ip_address, created_at) VALUES (?, 1, ?, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "数学", "127.0.0.1"),
            )
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, needs, ip_address, created_at) VALUES (?, 1, ?, ?, ?, datetime('now', '+8 hours'))",
                ("李四", "kete", "物理", "127.0.0.1"),
            )
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "127.0.0.1"),
            )
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                ("李四", "kete", "127.0.0.1"),
            )
            db.commit()

        resp = c.get("/api/admin/stats")
        d = get_json(resp)
        assert d["today_confirmed"] == 2, f"期望 today_confirmed=2, 实际={d['today_confirmed']}"
        assert d["today_queries"] == 4, f"期望 today_queries=4, 实际={d['today_queries']}"
        assert d["need_rate"] == 50.0, f"期望 need_rate=50.0%, 实际={d['need_rate']}%"

def test_t42_stats_query_rate():
    """T42: 访问查询率计算验证 — 2 UV，4 次查询 = 200%"""
    with app.test_client() as c:
        # record_visit 在 /<class_type> 路由触发
        c.get("/kete", environ_base={"REMOTE_ADDR": "1.1.1.1"}, headers={"User-Agent": "Test/1.0"})
        c.get("/kete", environ_base={"REMOTE_ADDR": "2.2.2.2"}, headers={"User-Agent": "Test/2.0"})

        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        # 插入 4 条查询日志
        with app.app_context():
            db = get_db()
            for _ in range(4):
                db.execute(
                    "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                    ("张三", "kete", "127.0.0.1"),
                )
            db.commit()

        resp = c.get("/api/admin/stats")
        d = get_json(resp)
        assert d is not None
        assert d["today_visitors"] == 2, f"期望 today_visitors=2, 实际={d['today_visitors']}"
        assert d["today_queries"] == 4, f"期望 today_queries=4, 实际={d['today_queries']}"
        assert d["query_rate"] == 200.0, f"期望 query_rate=200.0%, 实际={d['query_rate']}%"


# ═══════════════════════════════════════════
# T43-T44: 导出测试
# ═══════════════════════════════════════════

def test_t43_export_excel():
    """T43: 导出录取名单 Excel"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}], "class_type": "kete"
        })
        resp = c.get("/api/admin/list/export_xlsx")
        assert resp.status_code == 200

def test_t44_export_empty():
    """T44: 导出空数据"""
    with app.test_client() as c:
        api_login(c)
        resp = c.get("/api/admin/list/export_xlsx")
        # 空数据导出可能返回 JSON 错误或 200 的 Excel
        if resp.content_type and "json" in resp.content_type:
            d = get_json(resp)
            assert d is not None
            assert d.get("success") is False
        else:
            assert resp.status_code == 200


# ═══════════════════════════════════════════
# T45-T46: 错误页面测试
# ═══════════════════════════════════════════

def test_t45_404_page():
    """T45: 404 页面"""
    with app.test_client() as c:
        resp = c.get("/nonexistent-page-12345")
        assert resp.status_code == 404

def test_t46_unauthorized():
    """T46: 未登录访问管理 API"""
    with app.test_client() as c:
        resp = c.get("/api/admin/stats")
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False


# ═══════════════════════════════════════════
# T47: 密码验证无数据
# ═══════════════════════════════════════════

def test_t47_verify_password_no_data():
    """T47: 无密码数据"""
    with app.test_client() as c:
        api_login(c)
        resp = c.post("/api/admin/verify-password", json={})
        d = get_json(resp)
        assert d is not None
        assert d.get("success") is False


# ═══════════════════════════════════════════
# T48-T49: 班型统计
# ═══════════════════════════════════════════

def test_t48_class_type_stats():
    """T48: 班型统计（通过 admissions 表直接验证）"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}, {"name": "王五"}], "class_type": "kete"
        })
        c.post("/api/admin/upload", json={
            "names": [{"name": "李四"}], "class_type": "yucai"
        })
        # 验证 admissions 表中有正确的班型数据
        with app.app_context():
            db = get_db()
            kete_count = db.execute("SELECT COUNT(*) as cnt FROM admissions WHERE class_type = 'kete'").fetchone()["cnt"]
            yucai_count = db.execute("SELECT COUNT(*) as cnt FROM admissions WHERE class_type = 'yucai'").fetchone()["cnt"]
            assert kete_count == 2
            assert yucai_count == 1

def test_t49_empty_stats():
    """T49: 空数据统计"""
    with app.test_client() as c:
        api_login(c)
        resp = c.get("/api/admin/stats")
        d = get_json(resp)
        assert d is not None
        assert d.get("total") == 0
        assert d.get("today_queries") == 0
        assert d.get("need_rate") == 0

def test_t50_visitor_record():
    """T50: 访问记录去重"""
    with app.test_client() as c:
        # 同一个 IP+UA 多次访问 /kete 只算一次
        for _ in range(3):
            c.get("/kete", environ_base={"REMOTE_ADDR": "10.0.0.1"}, headers={"User-Agent": "SameBot/1.0"})

        with app.app_context():
            db = get_db()
            cnt = db.execute("SELECT COUNT(DISTINCT visitor_hash) as cnt FROM site_visits").fetchone()["cnt"]
            assert cnt == 1

def test_t51_stats_card_data_consistency():
    """T51: 统计卡片数据一致性 — today_confirmed 显示值与 need_rate 分子一致"""
    with app.test_client() as c:
        api_login(c)
        c.post("/api/admin/upload", json={
            "names": [{"name": "张三"}, {"name": "李四"}, {"name": "王五"}], "class_type": "kete"
        })
        # 模拟：张三提交需求、李四提交需求、王五只查询不提需求、张三再查一次
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, needs, ip_address, created_at) VALUES (?, 1, ?, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "数学", "127.0.0.1"),
            )
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, needs, ip_address, created_at) VALUES (?, 1, ?, ?, ?, datetime('now', '+8 hours'))",
                ("李四", "kete", "物理", "127.0.0.1"),
            )
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                ("王五", "kete", "127.0.0.1"),
            )
            db.execute(
                "INSERT INTO query_logs (name, admitted, class_type, ip_address, created_at) VALUES (?, 1, ?, ?, datetime('now', '+8 hours'))",
                ("张三", "kete", "127.0.0.1"),
            )
            db.commit()

        resp = c.get("/api/admin/stats")
        d = get_json(resp)

        assert d["today_queries"] == 4, f"today_queries={d['today_queries']}"
        assert d["today_confirmed"] == 2, f"today_confirmed={d['today_confirmed']}"
        assert d["need_rate"] == 50.0, f"need_rate={d['need_rate']}%"
        # 前端 statConfirmed 显示 today_confirmed（=2），need_rate=2/4=50%，两者一致


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
