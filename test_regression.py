"""
回归测试：验证现有功能在新代码下仍然正常工作
"""

import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["FLASK_ENV"] = "testing"

from app import app, init_db

TEST_DB = "/tmp/test_regression.db"
app.config["DATABASE"] = TEST_DB
app.config["TESTING"] = True

def setup():
    if os.path.exists(TEST_DB): os.remove(TEST_DB)
    init_db()

def login(c):
    c.post("/admin/login", json={"username": "admin", "password": "admin123456"})

def get_captcha(c):
    resp = c.get("/api/captcha")
    data = resp.get_json()
    m = re.match(r"(\d+)\s*([+\-×])\s*(\d+)", data["expression"].replace(" = ?", ""))
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    if op == "+": ans = a + b
    elif op == "-": ans = a - b
    elif op == "×": ans = a * b
    return data["token"], ans

def test_existing_features():
    setup()
    with app.test_client() as c:
        # ── 1. 首页访问 ──
        resp = c.get("/")
        assert resp.status_code in (200, 302, 308)  # redirect

        resp = c.get("/kete")
        assert resp.status_code == 200
        assert "科特班" in resp.data.decode()

        resp = c.get("/yucai")
        assert resp.status_code == 200
        assert "育才班" in resp.data.decode()

        # ── 2. 管理员登录 ──
        resp = c.post("/admin/login", json={"username": "admin", "password": "admin123456"})
        assert resp.get_json()["success"] is True

        resp = c.get("/admin/dashboard")
        assert resp.status_code == 200

        # ── 3. 上传名单 ──
        resp = c.post("/api/admin/upload", json={"names": [{"name": "张三"}, {"name": "李四"}], "class_type": "kete"})
        data = resp.get_json()
        assert data["success"] is True
        assert data["inserted"] == 2

        resp = c.post("/api/admin/upload", json={"names": [{"name": "王五"}], "class_type": "yucai"})
        assert resp.get_json()["success"] is True

        # ── 4. 名单管理 ──
        resp = c.get("/api/admin/list")
        data = resp.get_json()
        assert data["total"] == 3

        resp = c.get("/api/admin/list?class_type=kete")
        assert resp.get_json()["total"] == 2

        resp = c.get("/api/admin/list?search=张")
        assert resp.get_json()["total"] == 1

        # ── 5. 查询录取（需要验证码） ──
        token, ans = get_captcha(c)
        resp = c.get(f"/api/query?name=张三&class_type=kete&captcha_token={token}&captcha_answer={ans}")
        data = resp.get_json()
        assert data["success"] is True
        assert data["admitted"] is True
        assert data["name"] == "张三"

        # 未录取查询
        token2, ans2 = get_captcha(c)
        resp = c.get(f"/api/query?name=不存在&class_type=kete&captcha_token={token2}&captcha_answer={ans2}")
        data = resp.get_json()
        assert data["success"] is True
        assert data["admitted"] is False

        # ── 6. 提交培养需求 ──
        resp = c.post("/api/schedule/confirm", json={"name": "张三", "needs": ["锻炼强大逻辑思维", "提升专注力"]})
        assert resp.get_json()["success"] is True

        # ── 7. 查询日志 ──
        resp = c.get("/api/admin/logs")
        data = resp.get_json()
        assert data["total"] >= 2

        # 日志搜索和过滤
        resp = c.get("/api/admin/logs?class_type=kete")
        assert resp.get_json()["total"] >= 1

        resp = c.get("/api/admin/logs?search=张三")
        assert resp.get_json()["total"] >= 1

        # ── 8. 日志导出 ──
        resp = c.get("/api/admin/logs/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["Content-Type"]

        # ── 9. 统计 ──
        resp = c.get("/api/admin/stats")
        data = resp.get_json()
        assert data["total"] == 3
        assert data["kete"] == 2
        assert data["yucai"] == 1
        assert data["total_queries"] >= 2
        assert data["confirmed"] >= 1

        # ── 10. 操作日志 ──
        resp = c.get("/api/admin/audit-logs")
        data = resp.get_json()
        assert data["total"] >= 1

        # ── 11. 结果页面（JS渲染，测试客户端不执行JS，仅验证页面可访问） ──
        resp = c.get("/kete/result?name=张三&category=科特班·英才计划&grade=A%2B&score=95.3")
        assert resp.status_code == 200
        assert "英才计划录取通知书" in resp.data.decode()

        # ── 12. 批量删除 ──
        resp = c.post("/api/admin/batch-delete", json={"ids": [1, 2]})
        assert resp.get_json()["success"] is True

        resp = c.get("/api/admin/list")
        assert resp.get_json()["total"] == 1

        # ── 13. 批量删除日志 ──
        resp = c.post("/api/admin/logs/batch-delete", json={"ids": [1]})
        assert resp.get_json()["success"] is True

        # ── 14. 清空 ──
        resp = c.delete("/api/admin/clear")
        assert resp.get_json()["success"] is True

        resp = c.delete("/api/admin/logs/clear")
        assert resp.get_json()["success"] is True

        print("✅ 所有回归测试通过！")


if __name__ == "__main__":
    test_existing_features()
