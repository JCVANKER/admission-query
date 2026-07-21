"""
测试确认上课功能（修复网络错误）
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["FLASK_ENV"] = "testing"

from app import app, init_db

TEST_DB = "/tmp/test_confirm_fix.db"
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

def test_confirm_schedule():
    """测试确认上课安排"""
    setup()
    with app.test_client() as c:
        login(c)
        c.post("/api/admin/upload", json={"names": [{"name": "确认测试"}], "class_type": "kete"})
        
        token, ans = get_captcha(c)
        c.get(f"/api/query?name=确认测试&class_type=kete&captcha_token={token}&captcha_answer={ans}")
        
        resp = c.post("/api/schedule/confirm", json={"name": "确认测试", "date": "周一", "time": "14:00-15:00"})
        data = resp.get_json()
        assert data["success"] is True, f"Expected success, got {data}"
        print("✅ 确认上课测试通过")

def test_confirm_empty_name():
    """测试空姓名返回错误"""
    setup()
    with app.test_client() as c:
        resp = c.post("/api/schedule/confirm", json={"name": "", "date": "周一", "time": "14:00-15:00"})
        data = resp.get_json()
        assert data["success"] is False
        assert "姓名" in data["message"]
        print("✅ 空姓名测试通过")

def test_result_page_has_invite_link():
    """测试结果页包含跳转邀请函的链接"""
    setup()
    with app.test_client() as c:
        resp = c.get("/kete/result?name=测试&category=科特班·英才计划&grade=前3%")
        content = resp.data.decode()
        assert "window.location.href" in content
        assert "/invite" in content
        assert "英才计划录取通知书" in content
        assert "录取档案" in content
        print("✅ 结果页跳转测试通过")

def test_yucai_result_page():
    """测试育才班结果页"""
    setup()
    with app.test_client() as c:
        resp = c.get("/yucai/result?name=测试&category=育才班·英才计划&grade=前5%")
        content = resp.data.decode()
        # JS 会动态设置，检查 JS 逻辑存在
        assert "classType === 'yucai'" in content
        assert "顶级名校教育体系" in content
        print("✅ 育才班结果页测试通过")

if __name__ == "__main__":
    test_confirm_schedule()
    test_confirm_empty_name()
    test_result_page_has_modal()
    test_yucai_result_page()
    print("\n✅ 所有测试通过！")
