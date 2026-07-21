"""
测试3项新优化：
1. 文件上传支持 .xlsx
2. 育才班学习目标文案
3. 综合成绩改为前X%排名
"""

import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["FLASK_ENV"] = "testing"

from app import app, init_db, generate_grade

TEST_DB = "/tmp/test_optimization3.db"
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

# ═══════════════════════════════════════════
# 测试 1: 综合成绩改为前X%排名
# ═══════════════════════════════════════════

def test_generate_grade_format():
    """测试综合成绩格式为前X%"""
    for _ in range(20):
        g = generate_grade()
        assert g.startswith("前"), f"Expected '前X%' format, got '{g}'"
        assert g.endswith("%"), f"Expected '前X%' format, got '{g}'"
        pct = int(g[1:-1])
        assert 1 <= pct <= 9, f"Expected 1-9, got {pct}"

def test_grade_persisted():
    """测试相同姓名多次查询返回相同成绩"""
    setup()
    with app.test_client() as c:
        login(c)
        c.post("/api/admin/upload", json={"names": [{"name": "成绩固定测试"}], "class_type": "kete"})

        token1, ans1 = get_captcha(c)
        resp1 = c.get(f"/api/query?name=成绩固定测试&class_type=kete&captcha_token={token1}&captcha_answer={ans1}")
        grade1 = resp1.get_json()["grade"]

        token2, ans2 = get_captcha(c)
        resp2 = c.get(f"/api/query?name=成绩固定测试&class_type=kete&captcha_token={token2}&captcha_answer={ans2}")
        grade2 = resp2.get_json()["grade"]

        assert grade1 == grade2, f"成绩不一致: {grade1} vs {grade2}"

def test_query_returns_grade_no_score():
    """测试查询返回 grade 但 score 为空"""
    setup()
    with app.test_client() as c:
        login(c)
        c.post("/api/admin/upload", json={"names": [{"name": "无分数测试"}], "class_type": "kete"})

        token, ans = get_captcha(c)
        resp = c.get(f"/api/query?name=无分数测试&class_type=kete&captcha_token={token}&captcha_answer={ans}")
        data = resp.get_json()
        assert data["admitted"] is True
        assert data["grade"].startswith("前")
        assert data["score"] == ""

# ═══════════════════════════════════════════
# 测试 2: 育才班学习目标文案
# ═══════════════════════════════════════════

def test_kete_result_page_goal():
    """测试科特班结果页学习目标"""
    setup()
    with app.test_client() as c:
        login(c)
        c.post("/api/admin/upload", json={"names": [{"name": "科特学习目标"}], "class_type": "kete"})

        token, ans = get_captcha(c)
        c.get(f"/api/query?name=科特学习目标&class_type=kete&captcha_token={token}&captcha_answer={ans}")

        resp = c.get("/kete/result?name=科特学习目标&category=科特班·英才计划&grade=前3%")
        content = resp.data.decode()
        assert "英才计划录取通知书" in content
        assert "classType === 'yucai'" in content  # JS 中存在班型判断
        assert "白名单赛事" in content  # 科特班原文案

def test_yucai_result_page_goal():
    """测试育才班结果页学习目标（新文案）"""
    setup()
    with app.test_client() as c:
        login(c)
        c.post("/api/admin/upload", json={"names": [{"name": "育才学习目标"}], "class_type": "yucai"})

        token, ans = get_captcha(c)
        c.get(f"/api/query?name=育才学习目标&class_type=yucai&captcha_token={token}&captcha_answer={ans}")

        resp = c.get("/yucai/result?name=育才学习目标&category=育才班·英才计划&grade=前5%")
        content = resp.data.decode()
        assert "英才计划录取通知书" in content
        assert "顶级名校教育体系" in content
        assert "专注力开发体系" in content
        assert "科技特长认证的基础" in content

# ═══════════════════════════════════════════
# 测试 3: xlsx 上传（前端逻辑，验证模板页面）
# ═══════════════════════════════════════════

def test_admin_page_has_xlsx_support():
    """测试管理后台页面包含 xlsx 相关标记"""
    setup()
    with app.test_client() as c:
        login(c)
        resp = c.get("/admin/dashboard")
        content = resp.data.decode()
        assert ".xlsx" in content
        assert "xlsx.full.min.js" in content or "sheetjs" in content.lower()
        assert 'accept=".txt,.csv,.xlsx"' in content

def test_file_upload_still_works_txt():
    """测试 .txt 文件上传仍正常工作"""
    setup()
    with app.test_client() as c:
        login(c)
        # 模拟文本上传（和之前一样）
        resp = c.post("/api/admin/upload", json={"names": [{"name": "TXT测试A"}, {"name": "TXT测试B"}], "class_type": "kete"})
        data = resp.get_json()
        assert data["success"] is True
        assert data["inserted"] == 2

# ═══════════════════════════════════════════
# 测试 4: 回归测试
# ═══════════════════════════════════════════

def test_existing_upload_still_works():
    """测试现有 JSON 上传仍然正常"""
    setup()
    with app.test_client() as c:
        login(c)
        resp = c.post("/api/admin/upload", json={"names": [{"name": "回归测试"}], "class_type": "kete"})
        assert resp.get_json()["success"] is True

def test_admin_audit_logs_still_work():
    """测试操作日志功能正常"""
    setup()
    with app.test_client() as c:
        login(c)
        c.post("/api/admin/upload", json={"names": [{"name": "日志回归"}], "class_type": "kete"})
        resp = c.get("/api/admin/audit-logs")
        assert resp.get_json()["total"] >= 1

def test_captcha_still_works():
    """测试验证码功能正常"""
    setup()
    with app.test_client() as c:
        resp = c.get("/api/captcha")
        data = resp.get_json()
        assert "token" in data
        assert "expression" in data


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
