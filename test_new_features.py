"""
测试新增4个功能：
1. 查询验证码
2. 管理后台操作日志
3. 管理后台统计概览
4. 查询日志颜色标记（前端功能，后端数据验证确认状态）
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 使用测试数据库
os.environ["FLASK_ENV"] = "testing"

from app import app, init_db
import config

# 使用临时数据库
TEST_DB = "/tmp/test_admission_new_features.db"
app.config["DATABASE"] = TEST_DB
app.config["TESTING"] = True


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前重建数据库"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def admin_client(client):
    """登录后的管理后台客户端"""
    resp = client.post("/admin/login", json={"username": "admin", "password": "admin123456"})
    assert resp.get_json()["success"] is True
    return client


# ═══════════════════════════════════════════
# 1. 验证码测试
# ═══════════════════════════════════════════

def test_captcha_generation(client):
    """测试验证码生成"""
    resp = client.get("/api/captcha")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data
    assert "expression" in data
    assert len(data["token"]) == 16
    assert "?" in data["expression"]


def test_captcha_required_for_query(client):
    """测试查询需要验证码"""
    # 先上传一个名字
    admin_login(client)
    client.post("/api/admin/upload", json={"names": [{"name": "测试学生"}], "class_type": "kete"})

    # 不带验证码查询应该失败
    resp = client.get("/api/query?name=测试学生&class_type=kete")
    data = resp.get_json()
    assert data["success"] is False
    assert "验证码" in data["message"]


def test_captcha_validation_wrong_answer(client):
    """测试错误验证码"""
    resp = client.get("/api/captcha")
    token = resp.get_json()["token"]

    resp2 = client.get(f"/api/query?name=测试&class_type=kete&captcha_token={token}&captcha_answer=99999")
    data = resp2.get_json()
    assert data["success"] is False
    assert "验证码错误" in data["message"]


def test_captcha_validation_correct(client):
    """测试正确验证码查询"""
    # 获取验证码
    resp = client.get("/api/captcha")
    data = resp.get_json()
    token = data["token"]

    # 解析答案
    import re
    match = re.match(r"(\d+)\s*([+\-×])\s*(\d+)", data["expression"].replace(" = ?", ""))
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    if op == "+":
        answer = a + b
    elif op == "-":
        answer = a - b
    elif op == "×":
        answer = a * b

    # 上传名字后查询
    admin_login(client)
    client.post("/api/admin/upload", json={"names": [{"name": "正确验证码测试"}], "class_type": "kete"})

    resp2 = client.get(f"/api/query?name=正确验证码测试&class_type=kete&captcha_token={token}&captcha_answer={answer}")
    data2 = resp2.get_json()
    assert data2["success"] is True
    assert data2["admitted"] is True


def test_captcha_reuse_prevented(client):
    """测试验证码不能重复使用"""
    resp = client.get("/api/captcha")
    data = resp.get_json()
    token = data["token"]

    import re
    match = re.match(r"(\d+)\s*([+\-×])\s*(\d+)", data["expression"].replace(" = ?", ""))
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    if op == "+": answer = a + b
    elif op == "-": answer = a - b
    elif op == "×": answer = a * b

    admin_login(client)
    client.post("/api/admin/upload", json={"names": [{"name": "验证码复用测试"}], "class_type": "kete"})

    # 第一次使用
    resp1 = client.get(f"/api/query?name=验证码复用测试&class_type=kete&captcha_token={token}&captcha_answer={answer}")
    assert resp1.get_json()["success"] is True

    # 第二次使用同一token
    resp2 = client.get(f"/api/query?name=验证码复用测试&class_type=kete&captcha_token={token}&captcha_answer={answer}")
    data2 = resp2.get_json()
    assert data2["success"] is False
    assert "已使用" in data2["message"]


# ═══════════════════════════════════════════
# 2. 操作日志测试
# ═══════════════════════════════════════════

def test_audit_log_on_upload(admin_client):
    """测试上传操作被记录"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "日志测试A"}], "class_type": "kete"})

    resp = admin_client.get("/api/admin/audit-logs")
    data = resp.get_json()
    assert data["total"] >= 1
    log = data["items"][0]
    assert log["action"] == "上传录取名单"
    assert "科特班" in log["target"] or "成功" in log["detail"]


def test_audit_log_on_delete(admin_client):
    """测试删除操作被记录"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "日志测试B"}], "class_type": "kete"})
    # 获取刚上传记录的ID
    list_resp = admin_client.get("/api/admin/list?page=1&per_page=1")
    record_id = list_resp.get_json()["items"][0]["id"]
    admin_client.delete(f"/api/admin/delete/{record_id}")

    resp = admin_client.get("/api/admin/audit-logs")
    logs = resp.get_json()["items"]
    delete_logs = [l for l in logs if l["action"] == "删除录取名单"]
    assert len(delete_logs) >= 1
    assert "日志测试B" in delete_logs[0]["target"]


def test_audit_log_on_batch_delete(admin_client):
    """测试批量删除操作被记录"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "C"}, {"name": "D"}], "class_type": "kete"})
    admin_client.post("/api/admin/batch-delete", json={"ids": [1, 2]})

    resp = admin_client.get("/api/admin/audit-logs")
    logs = resp.get_json()["items"]
    batch_logs = [l for l in logs if l["action"] == "批量删除录取名单"]
    assert len(batch_logs) >= 1
    assert "2 条" in batch_logs[0]["detail"]


def test_audit_log_on_clear(admin_client):
    """测试清空操作被记录"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "E"}], "class_type": "kete"})
    admin_client.delete("/api/admin/clear")

    resp = admin_client.get("/api/admin/audit-logs")
    logs = resp.get_json()["items"]
    clear_logs = [l for l in logs if l["action"] == "清空录取名单"]
    assert len(clear_logs) >= 1


def test_audit_log_pagination(admin_client):
    """测试操作日志分页"""
    for i in range(5):
        admin_client.post("/api/admin/upload", json={"names": [{"name": f"分页测试{i}"}], "class_type": "kete"})
        admin_client.delete(f"/api/admin/delete/{i+1}")

    resp = admin_client.get("/api/admin/audit-logs?page=1&per_page=2")
    data = resp.get_json()
    assert len(data["items"]) == 2
    assert data["total"] >= 10


def test_audit_log_clear(admin_client):
    """测试清空操作日志"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "清理测试"}], "class_type": "kete"})

    resp = admin_client.delete("/api/admin/audit-logs/clear")
    assert resp.get_json()["success"] is True

    resp2 = admin_client.get("/api/admin/audit-logs")
    assert resp2.get_json()["total"] == 0


# ═══════════════════════════════════════════
# 3. 增强统计测试
# ═══════════════════════════════════════════

def test_enhanced_stats(admin_client):
    """测试增强统计API"""
    # 先清空确保干净
    admin_client.delete("/api/admin/clear")
    # 上传一些数据
    admin_client.post("/api/admin/upload", json={"names": [{"name": "统计A"}, {"name": "统计B"}], "class_type": "kete"})
    admin_client.post("/api/admin/upload", json={"names": [{"name": "统计C"}], "class_type": "yucai"})

    resp = admin_client.get("/api/admin/stats")
    data = resp.get_json()

    assert data["total"] == 3
    assert data["kete"] == 2
    assert data["yucai"] == 1
    assert "today_queries" in data
    assert "total_queries" in data
    assert "confirmed" in data
    assert "admission_rate" in data
    assert "today_new" in data


def test_stats_with_queries(admin_client, client):
    """测试统计包含查询数据"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "查询统计"}], "class_type": "kete"})

    # 模拟查询（需要验证码）
    captcha_resp = client.get("/api/captcha")
    captcha_data = captcha_resp.get_json()
    import re
    match = re.match(r"(\d+)\s*([+\-×])\s*(\d+)", captcha_data["expression"].replace(" = ?", ""))
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    if op == "+": answer = a + b
    elif op == "-": answer = a - b
    elif op == "×": answer = a * b

    client.get(f"/api/query?name=查询统计&class_type=kete&captcha_token={captcha_data['token']}&captcha_answer={answer}")

    resp = admin_client.get("/api/admin/stats")
    data = resp.get_json()
    assert data["total_queries"] >= 1


# ═══════════════════════════════════════════
# 4. 查询日志确认状态测试
# ═══════════════════════════════════════════

def test_logs_show_confirmed_status(admin_client, client):
    """测试日志中确认状态字段正确返回"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "确认测试"}], "class_type": "kete"})

    # 获取验证码
    captcha_resp = client.get("/api/captcha")
    captcha_data = captcha_resp.get_json()
    import re
    match = re.match(r"(\d+)\s*([+\-×])\s*(\d+)", captcha_data["expression"].replace(" = ?", ""))
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    if op == "+": answer = a + b
    elif op == "-": answer = a - b
    elif op == "×": answer = a * b

    client.get(f"/api/query?name=确认测试&class_type=kete&captcha_token={captcha_data['token']}&captcha_answer={answer}")

    # 确认上课安排
    client.post("/api/schedule/confirm", json={"name": "确认测试", "date": "周六", "time": "14:00-15:00"})

    # 检查日志
    resp = admin_client.get("/api/admin/logs")
    logs = resp.get_json()["items"]
    admitted_logs = [l for l in logs if l["name"] == "确认测试" and l["admitted"] == 1]
    assert len(admitted_logs) >= 1
    log = admitted_logs[0]
    assert log["schedule_date"] == "周六"
    assert log["schedule_time"] == "14:00-15:00"


def test_schedule_confirm_returns_success(client, admin_client):
    """测试确认上课安排返回成功"""
    admin_client.post("/api/admin/upload", json={"names": [{"name": "安排确认"}], "class_type": "kete"})

    captcha_resp = client.get("/api/captcha")
    captcha_data = captcha_resp.get_json()
    import re
    match = re.match(r"(\d+)\s*([+\-×])\s*(\d+)", captcha_data["expression"].replace(" = ?", ""))
    a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
    if op == "+": answer = a + b
    elif op == "-": answer = a - b
    elif op == "×": answer = a * b

    client.get(f"/api/query?name=安排确认&class_type=kete&captcha_token={captcha_data['token']}&captcha_answer={answer}")

    resp = client.post("/api/schedule/confirm", json={"name": "安排确认", "date": "周日", "time": "10:00-11:00"})
    assert resp.get_json()["success"] is True


# ═══════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════

def admin_login(client):
    client.post("/admin/login", json={"username": "admin", "password": "admin123456"})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
