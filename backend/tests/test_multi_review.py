"""
多人审批功能单元测试

核心业务规则：
1. 所有用户都能看到别人的 pending 申请，都有权审批
2. 禁止审批自己提交的申请（后端强制拦截）
3. 每个用户对同一申请只能审批一次（UNIQUE 约束 + 后端校验）
4. B 审完后 C 仍能看到该申请并独立审批
5. 审批理由必填（后端 Pydantic 校验）
6. 每次审批都给申请人发通知消息
7. 未登录不能访问业务接口
8. 我的申请记录返回所有审批人的独立记录
"""
import io
from tests.conftest import _register_and_login

# 1x1 透明 PNG 的 base64
TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def _make_image():
    """构造一个合法的 PNG UploadFile 内容。"""
    import base64
    return io.BytesIO(base64.b64decode(TINY_PNG_B64))


def _submit_application(client, token, item_name="测试物品", price=99.50, description="测试描述"):
    """提交一条物品申报，返回响应 JSON。"""
    resp = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token}"},
        data={"item_name": item_name, "price": str(price), "description": description},
        files={"image": ("test.png", _make_image(), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ==================================================================
# 测试 1：所有用户都能看到别人的 pending 申请
# ==================================================================
def test_all_users_see_pending(client):
    """A 提交申请后，B 和 C 都能在待审批列表看到。"""
    token_a, _ = _register_and_login(client, "userA")
    token_b, _ = _register_and_login(client, "userB")
    token_c, _ = _register_and_login(client, "userC")

    result = _submit_application(client, token_a, item_name="公开物品")
    apply_id = result["id"]

    # B 的待审批列表应包含该申请
    resp_b = client.get("/api/applications/pending", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    pending_b = resp_b.json()
    assert any(a["id"] == apply_id for a in pending_b), "B 应能看到 A 的申请"

    # C 的待审批列表也应包含该申请
    resp_c = client.get("/api/applications/pending", headers={"Authorization": f"Bearer {token_c}"})
    assert resp_c.status_code == 200
    pending_c = resp_c.json()
    assert any(a["id"] == apply_id for a in pending_c), "C 应能看到 A 的申请"


# ==================================================================
# 测试 2：禁止审批自己提交的申请
# ==================================================================
def test_cannot_review_own_application(client):
    """A 提交申请后，A 不能审批自己的申请。"""
    token_a, _ = _register_and_login(client, "selfA")

    result = _submit_application(client, token_a, item_name="自己的物品")
    apply_id = result["id"]

    resp = client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"action": "approved", "reason": "自审测试"},
    )
    assert resp.status_code == 400
    assert "不允许审批自己提交的申请" in resp.json()["detail"]


# ==================================================================
# 测试 3：每个用户对同一申请只能审批一次
# ==================================================================
def test_cannot_review_twice(client):
    """B 审批后，B 再次审批同一申请应被拒绝。"""
    token_a, _ = _register_and_login(client, "onceA")
    token_b, _ = _register_and_login(client, "onceB")

    result = _submit_application(client, token_a, item_name="一次审批")
    apply_id = result["id"]

    # B 第一次审批——成功
    resp1 = client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": "第一次审批"},
    )
    assert resp1.status_code == 200

    # B 第二次审批同一申请——拒绝
    resp2 = client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": "第二次审批"},
    )
    assert resp2.status_code == 400
    assert "不能重复审批" in resp2.json()["detail"]


# ==================================================================
# 测试 4：B 审完后 C 仍能看到并独立审批
# ==================================================================
def test_independent_multi_review(client):
    """B 审批通过后，C 的待审列表仍有该申请，C 可独立驳回。"""
    token_a, _ = _register_and_login(client, "indA")
    token_b, _ = _register_and_login(client, "indB")
    token_c, _ = _register_and_login(client, "indC")

    result = _submit_application(client, token_a, item_name="多审测试")
    apply_id = result["id"]

    # B 审批通过
    resp_b = client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": "B认为可以"},
    )
    assert resp_b.status_code == 200

    # B 的待审列表不再有该申请
    pending_b = client.get(
        "/api/applications/pending", headers={"Authorization": f"Bearer {token_b}"}
    ).json()
    assert not any(a["id"] == apply_id for a in pending_b), "B 审完后不应再看到该申请"

    # C 的待审列表仍有该申请
    pending_c = client.get(
        "/api/applications/pending", headers={"Authorization": f"Bearer {token_c}"}
    ).json()
    assert any(a["id"] == apply_id for a in pending_c), "C 仍应能看到该申请"

    # C 独立驳回（不受 B 的影响）
    resp_c = client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_c}"},
        json={"action": "rejected", "reason": "C认为不行"},
    )
    assert resp_c.status_code == 200


# ==================================================================
# 测试 5：审批理由必填（后端校验）
# ==================================================================
def test_reason_required(client):
    """空理由应被后端拒绝（422）。"""
    token_a, _ = _register_and_login(client, "reasonA")
    token_b, _ = _register_and_login(client, "reasonB")

    result = _submit_application(client, token_a, item_name="理由测试")
    apply_id = result["id"]

    # 空字符串理由
    resp = client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": ""},
    )
    assert resp.status_code == 422

    # 纯空格理由
    resp2 = client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": "   "},
    )
    assert resp2.status_code == 422


# ==================================================================
# 测试 6：每次审批都给申请人发通知消息
# ==================================================================
def test_review_sends_notification(client):
    """B 和 C 各审批一次，A 应收到 2 条通知。"""
    token_a, _ = _register_and_login(client, "notifyA")
    token_b, _ = _register_and_login(client, "notifyB")
    token_c, _ = _register_and_login(client, "notifyC")

    result = _submit_application(client, token_a, item_name="通知测试")
    apply_id = result["id"]

    # B 审批
    client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": "B通过"},
    )
    # C 审批
    client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_c}"},
        json={"action": "rejected", "reason": "C驳回"},
    )

    # A 的消息列表应有 2 条
    resp = client.get("/api/messages", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    messages = resp.json()
    assert len(messages) == 2

    # 验证消息内容包含审批人和审批理由
    contents = [m["content"] for m in messages]
    assert any("notifyB" in c and "B通过" in c for c in contents), "应有 B 的通过通知"
    assert any("notifyC" in c and "C驳回" in c for c in contents), "应有 C 的驳回通知"


# ==================================================================
# 测试 7：未登录不能访问业务接口
# ==================================================================
def test_unauthenticated_blocked(client):
    """未携带 Token 访问业务接口应返回 401/403。"""
    # 待审批列表
    resp = client.get("/api/applications/pending")
    assert resp.status_code in (401, 403)

    # 我的申请
    resp = client.get("/api/applications/mine")
    assert resp.status_code in (401, 403)

    # 消息列表
    resp = client.get("/api/messages")
    assert resp.status_code in (401, 403)

    # 提交申报
    resp = client.post(
        "/api/applications",
        data={"item_name": "x", "price": "1", "description": "x"},
        files={"image": ("t.png", _make_image(), "image/png")},
    )
    assert resp.status_code in (401, 403)


# ==================================================================
# 测试 8：我的申请记录返回所有审批人的独立记录
# ==================================================================
def test_my_applications_shows_all_reviewers(client):
    """A 的申请记录应包含 B 和 C 两条独立审批记录。"""
    token_a, _ = _register_and_login(client, "recordA")
    token_b, _ = _register_and_login(client, "recordB")
    token_c, _ = _register_and_login(client, "recordC")

    result = _submit_application(client, token_a, item_name="记录测试")
    apply_id = result["id"]

    # B 通过
    client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": "B通过"},
    )
    # C 驳回
    client.post(
        f"/api/applications/{apply_id}/review",
        headers={"Authorization": f"Bearer {token_c}"},
        json={"action": "rejected", "reason": "C驳回"},
    )

    # 查 A 的申请记录
    resp = client.get("/api/applications/mine", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    apps = resp.json()
    assert len(apps) == 1

    app = apps[0]
    assert app["id"] == apply_id
    assert app["status"] == "pending"  # 多人审批模式不改 item_apply.status

    approvals = app["approvals"]
    assert len(approvals) == 2

    # 验证两条记录的审批人不同
    reviewer_names = {a["reviewer_name"] for a in approvals}
    assert reviewer_names == {"recordB", "recordC"}

    # 验证一条通过、一条驳回
    actions = {a["action"] for a in approvals}
    assert actions == {"approved", "rejected"}


# ==================================================================
# 测试 9：提交人不存在时审批应 404
# ==================================================================
def test_review_nonexistent_application(client):
    """审批不存在的申请 ID 应返回 404。"""
    token_b, _ = _register_and_login(client, "nfB")

    resp = client.post(
        "/api/applications/99999/review",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"action": "approved", "reason": "测试"},
    )
    assert resp.status_code == 404


# ==================================================================
# 测试 10：好友提交申报后推送通知给好友（需先发申请→同意→成为好友）
# ==================================================================
def test_friend_notification_on_submit(client):
    """A 向 B 发好友申请，B 同意后，A 提交申报，B 应收到推送消息。"""
    token_a, user_a = _register_and_login(client, "friendSubmitA")
    token_b, user_b = _register_and_login(client, "friendSubmitB")

    # A 用 B 的 uid 搜索
    resp_search = client.get(
        "/api/users/search",
        params={"q": user_b["uid"]},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_search.status_code == 200
    search_results = resp_search.json()
    assert len(search_results) == 1
    assert search_results[0]["id"] == user_b["id"]

    # A 向 B 发送好友申请
    resp_add = client.post(
        f"/api/friends/{user_b['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_add.status_code == 200

    # B 查看好友申请列表
    resp_reqs = client.get(
        "/api/friend-requests",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_reqs.status_code == 200
    requests = resp_reqs.json()
    assert len(requests) == 1
    request_id = requests[0]["id"]

    # B 同意好友申请
    resp_accept = client.post(
        f"/api/friend-requests/{request_id}/accept",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_accept.status_code == 200

    # A 提交申报
    result = _submit_application(client, token_a, item_name="好友推送物品")
    apply_id = result["id"]

    # B 应收到推送消息
    resp_msg = client.get("/api/messages", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_msg.status_code == 200
    messages = resp_msg.json()
    assert len(messages) == 1
    assert "friendSubmitA" in messages[0]["content"]
    assert "好友推送物品" in messages[0]["content"]


# ==================================================================
# 测试 12：好友申请流程——发送、接收、同意、成为好友
# ==================================================================
def test_friend_request_accept(client):
    """A 向 B 发好友申请 → B 同意 → 双方成为好友。"""
    token_a, user_a = _register_and_login(client, "frA")
    token_b, user_b = _register_and_login(client, "frB")

    # A 搜索 B 并发送申请
    resp = client.post(
        f"/api/friends/{user_b['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200
    assert "发送好友申请" in resp.json()["message"]

    # A 的好友列表应为空（还没成为好友）
    friends_a = client.get("/api/friends", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert len(friends_a) == 0

    # B 的好友申请列表应有 1 条
    reqs = client.get("/api/friend-requests", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert len(reqs) == 1
    assert reqs[0]["from_username"] == "frA"
    req_id = reqs[0]["id"]

    # B 同意
    resp_accept = client.post(
        f"/api/friend-requests/{req_id}/accept",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_accept.status_code == 200

    # 双方好友列表各 1 人
    friends_a = client.get("/api/friends", headers={"Authorization": f"Bearer {token_a}"}).json()
    friends_b = client.get("/api/friends", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert len(friends_a) == 1
    assert len(friends_b) == 1
    assert friends_a[0]["username"] == "frB"
    assert friends_b[0]["username"] == "frA"

    # B 的申请列表应清空
    reqs2 = client.get("/api/friend-requests", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert len(reqs2) == 0


# ==================================================================
# 测试 13：拒绝好友申请后可以重新发送
# ==================================================================
def test_friend_request_reject_and_resend(client):
    """A 向 B 发申请 → B 拒绝 → A 可重新发申请。"""
    token_a, user_a = _register_and_login(client, "rejA")
    token_b, user_b = _register_and_login(client, "rejB")

    # A 发申请
    client.post(f"/api/friends/{user_b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    reqs = client.get("/api/friend-requests", headers={"Authorization": f"Bearer {token_b}"}).json()
    req_id = reqs[0]["id"]

    # B 拒绝
    resp_reject = client.post(
        f"/api/friend-requests/{req_id}/reject",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_reject.status_code == 200

    # B 的申请列表清空
    reqs2 = client.get("/api/friend-requests", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert len(reqs2) == 0

    # 双方不是好友
    friends_a = client.get("/api/friends", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert len(friends_a) == 0

    # A 可重新发申请
    resp_resend = client.post(
        f"/api/friends/{user_b['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_resend.status_code == 200
    assert "发送好友申请" in resp_resend.json()["message"]

    # B 又能看到申请了
    reqs3 = client.get("/api/friend-requests", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert len(reqs3) == 1


# ==================================================================
# 测试 14：重复发送申请被拒绝
# ==================================================================
def test_duplicate_friend_request_blocked(client):
    """A 向 B 发了 pending 申请后，不能重复发。"""
    token_a, user_a = _register_and_login(client, "dupA")
    token_b, user_b = _register_and_login(client, "dupB")

    # 第一次发送
    resp1 = client.post(f"/api/friends/{user_b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp1.status_code == 200

    # 重复发送
    resp2 = client.post(f"/api/friends/{user_b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp2.status_code == 400
    assert "等待对方确认" in resp2.json()["detail"]


# ==================================================================
# 测试 15：无权处理他人的好友申请
# ==================================================================
def test_cannot_handle_others_request(client):
    """C 不能处理 A 发给 B 的好友申请。"""
    token_a, user_a = _register_and_login(client, "othA")
    token_b, user_b = _register_and_login(client, "othB")
    token_c, user_c = _register_and_login(client, "othC")

    # A 向 B 发申请
    client.post(f"/api/friends/{user_b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    reqs = client.get("/api/friend-requests", headers={"Authorization": f"Bearer {token_b}"}).json()
    req_id = reqs[0]["id"]

    # C 试图同意 B 收到的申请 → 403
    resp = client.post(
        f"/api/friend-requests/{req_id}/accept",
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert resp.status_code == 403

    # C 试图拒绝 → 403
    resp2 = client.post(
        f"/api/friend-requests/{req_id}/reject",
        headers={"Authorization": f"Bearer {token_c}"},
    )
    assert resp2.status_code == 403


# ==================================================================
# 测试 16：已是好友后不能再次发申请
# ==================================================================
def test_already_friends_cannot_request(client):
    """A 和 B 已是好友后，A 再发申请应提示已是好友。"""
    token_a, user_a = _register_and_login(client, "alA")
    token_b, user_b = _register_and_login(client, "alB")

    # A 发申请 → B 同意
    client.post(f"/api/friends/{user_b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    reqs = client.get("/api/friend-requests", headers={"Authorization": f"Bearer {token_b}"}).json()
    client.post(f"/api/friend-requests/{reqs[0]['id']}/accept",
                headers={"Authorization": f"Bearer {token_b}"})

    # A 再发申请
    resp = client.post(f"/api/friends/{user_b['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 400
    assert "已经是好友" in resp.json()["detail"]


# ==================================================================
# 测试 11：图片安全校验（非法格式 + 超大文件）
# ==================================================================
def test_image_validation(client):
    """上传非图片文件应被拒绝；超过 2MB 应被拒绝。"""
    token_a, _ = _register_and_login(client, "imgA")

    # 非法文件类型（txt 伪装 png）
    resp = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token_a}"},
        data={"item_name": "非法文件", "price": "10", "description": "test"},
        files={"image": ("evil.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "仅支持" in resp.json()["detail"]

    # 超大图片（>2MB）
    big_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 100)
    resp2 = client.post(
        "/api/applications",
        headers={"Authorization": f"Bearer {token_a}"},
        data={"item_name": "超大图片", "price": "10", "description": "test"},
        files={"image": ("big.png", io.BytesIO(big_data), "image/png")},
    )
    assert resp2.status_code == 400
    assert "2MB" in resp2.json()["detail"]
