"""
测试入学邀请函独立页面
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["FLASK_ENV"] = "testing"

from app import app, init_db

TEST_DB = "/tmp/test_invite_page.db"
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

def test_invite_page_kete():
    """测试科特班邀请函页面"""
    setup()
    with app.test_client() as c:
        resp = c.get("/kete/invite?name=张三&date=周一&time=14:00-15:00")
        assert resp.status_code == 200
        content = resp.data.decode()
        assert "入学邀请函" in content
        assert "英才计划" in content
        assert "张三" in content
        assert "英才计划录取资格" in content
        assert "北大-点猫人工智能教育联合实验室" in content
        assert "深圳点猫科技有限公司" in content
        print("✅ 科特班邀请函测试通过")

def test_invite_page_yucai():
    """测试育才班邀请函页面"""
    setup()
    with app.test_client() as c:
        resp = c.get("/yucai/invite?name=李四&date=周六&time=19:00-20:00")
        assert resp.status_code == 200
        content = resp.data.decode()
        assert "入学邀请函" in content
        assert "李四" in content
        assert "英才计划录取资格" in content
        print("✅ 育才班邀请函测试通过")

def test_result_page_clean():
    """测试结果页不含弹窗代码"""
    setup()
    with app.test_client() as c:
        resp = c.get("/kete/result?name=测试&grade=前3%")
        content = resp.data.decode()
        assert "inviteModal" not in content
        assert "invite?" in content or "invite?" in content.lower()
        assert "window.location.href" in content
        print("✅ 结果页清理测试通过")

def test_confirm_flow():
    """测试完整确认流程"""
    setup()
    with app.test_client() as c:
        login(c)
        c.post("/api/admin/upload", json={"names": [{"name": "完整流程测试"}], "class_type": "kete"})
        
        token, ans = get_captcha(c)
        c.get(f"/api/query?name=完整流程测试&class_type=kete&captcha_token={token}&captcha_answer={ans}")
        
        resp = c.post("/api/schedule/confirm", json={"name": "完整流程测试", "date": "周一", "time": "14:00-15:00"})
        assert resp.get_json()["success"] is True
        
        # 验证邀请函页面可访问
        resp2 = c.get("/kete/invite?name=完整流程测试&date=周一&time=14:00-15:00")
        assert resp2.status_code == 200
        print("✅ 完整流程测试通过")

if __name__ == "__main__":
    test_invite_page_kete()
    test_invite_page_yucai()
    test_result_page_clean()
    test_confirm_flow()
    print("\n✅ 所有测试通过！")
