# -*- coding: utf-8 -*-
"""
物品申报审批系统 —— FastAPI 后端
功能：注册/登录(JWT)、物品申报(图片上传)、待审批列表、审批(拦截自审)、消息通知
所有业务接口均需携带 Token；核心业务规则全部在后端强制校验。

启动：uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import os
import uuid
import random
import string
import base64
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

import bcrypt
import pymysql
from pymysql.cursors import DictCursor
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from jose import jwt, JWTError

# ------------------------------------------------------------------
# 配置（可通过环境变量覆盖，便于本地/部署切换）
# ------------------------------------------------------------------
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "item_approval")

JWT_SECRET = os.getenv("JWT_SECRET", "item-approval-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # token 有效期 1 天

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 图片安全限制：仅 jpg/png/gif，大小不超过 2MB
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024

bearer_scheme = HTTPBearer(auto_error=True)

app = FastAPI(title="物品申报审批系统 API", version="1.0.0")

# 开发环境跨域（前端通过 Vite 代理访问，这里同时放开方便直连调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传文件静态访问：/static/images/xxx.jpg -> backend/uploads/images/xxx.jpg
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "uploads")), name="static")


# ------------------------------------------------------------------
# 数据库连接（每个请求一个连接）
# ------------------------------------------------------------------
def get_conn():
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def _bcrypt_digest(raw: str) -> bytes:
    # 先 SHA256 再 Base64（44 字节），保证任意长度密码都不超过 bcrypt 的 72 字节限制
    return base64.b64encode(hashlib.sha256(raw.encode("utf-8")).digest())


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_bcrypt_digest(raw), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(_bcrypt_digest(raw), hashed.encode("utf-8"))


def generate_uid() -> str:
    """生成 8 位随机好友 ID（大写字母+数字），保证数据库唯一。"""
    chars = string.ascii_uppercase + string.digits
    for _ in range(100):
        uid = "".join(random.choices(chars, k=8))
        return uid
    return "".join(random.choices(chars, k=12))


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def jsonable(row: dict) -> dict:
    """把 MySQL 返回的 datetime / Decimal 转成 JSON 友好类型。"""
    for key, value in list(row.items()):
        if isinstance(value, datetime):
            row[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, Decimal):
            row[key] = float(value)
    return row


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    conn=Depends(get_conn),
) -> dict:
    """Token 鉴权依赖：所有业务接口挂上它，未登录一律 401。"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, uid, created_at FROM user WHERE id = %s", (user_id,)
        )
        user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在，请重新登录")
    return jsonable(user)


# ------------------------------------------------------------------
# 请求模型
# ------------------------------------------------------------------
class AuthIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=64)


class ReviewIn(BaseModel):
    # 审批操作二选一
    action: Literal["approved", "rejected"]
    # 审批理由：后端强制非空（前端也做必填校验）
    reason: str = Field(..., max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("审批理由不能为空")
        return v.strip()


class UidIn(BaseModel):
    uid: str = Field(..., min_length=4, max_length=20)

    @field_validator("uid")
    @classmethod
    def uid_format(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("好友ID不能为空")
        if not all(c.isalnum() for c in v):
            raise ValueError("好友ID只能包含字母和数字")
        return v


# ==================================================================
# 一、注册 / 登录
# ==================================================================
@app.post("/api/auth/register")
def register(data: AuthIn, conn=Depends(get_conn)):
    username = data.username.strip()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM user WHERE username = %s", (username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="用户名已存在")

        # 生成唯一 uid，重试最多 100 次避免偶然碰撞
        for _ in range(100):
            uid = generate_uid()
            cur.execute("SELECT id FROM user WHERE uid = %s", (uid,))
            if not cur.fetchone():
                break

        cur.execute(
            "INSERT INTO user (username, password_hash, uid) VALUES (%s, %s, %s)",
            (username, hash_password(data.password), uid),
        )
        conn.commit()
        user_id = cur.lastrowid
    return {"id": user_id, "username": username, "uid": uid, "message": "注册成功"}


@app.post("/api/auth/login")
def login(data: AuthIn, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, uid FROM user WHERE username = %s",
            (data.username.strip(),),
        )
        user = cur.fetchone()
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    token = create_token(user["id"], user["username"])
    return {"token": token, "user": {"id": user["id"], "username": user["username"], "uid": user["uid"]}}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user


# ==================================================================
# 二、物品申报
# ==================================================================
@app.post("/api/applications")
async def submit_application(
    item_name: str = Form(..., max_length=100),
    price: float = Form(...),
    description: str = Form(default=""),
    image: UploadFile = File(...),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    item_name = item_name.strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="物品名称不能为空")
    if price < 0:
        raise HTTPException(status_code=400, detail="物品价格不能为负数")

    # ---- 图片安全校验（后端强制，不信任前端）----
    raw = await image.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="请上传物品图片")
    if len(raw) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="图片大小不能超过 2MB")
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 jpg、png、gif 格式图片")
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="仅支持 jpg、png、gif 格式图片")
    # jpeg 扩展名统一为 .jpg
    if ext == ".jpeg":
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(raw)
    # 数据库只存访问路径，不存图片二进制
    image_path = f"/static/images/{filename}"

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO item_apply
               (user_id, item_name, price, description, image_path, status)
               VALUES (%s, %s, %s, %s, %s, 'pending')""",
            (user["id"], item_name, price, description.strip(), image_path),
        )
        apply_id = cur.lastrowid

        # 申报提交后第一时间推送给所有好友
        cur.execute(
            "SELECT friend_id FROM friendship WHERE user_id = %s", (user["id"],)
        )
        friends = cur.fetchall()
        if friends:
            friend_content = (
                f"您的好友「{user['username']}」提交了新的物品申报「{item_name}」，"
                f"价格 {price:.2f} 元，等待审批"
            )
            for f in friends:
                cur.execute(
                    """INSERT INTO message (user_id, apply_id, content, is_read)
                       VALUES (%s, %s, %s, 0)""",
                    (f["friend_id"], apply_id, friend_content),
                )
        conn.commit()
    return {"id": apply_id, "message": "申报提交成功，等待其他用户审批"}


@app.get("/api/applications/mine")
def my_applications(user=Depends(current_user), conn=Depends(get_conn)):
    """我的申请记录：展示本人全部申请 + 所有用户的审批记录（多人审批）。"""
    with conn.cursor() as cur:
        # 1. 查我的所有申请
        cur.execute(
            """SELECT a.id, a.item_name, a.price, a.description, a.image_path,
                      a.status, a.created_at
               FROM item_apply a
               WHERE a.user_id = %s
               ORDER BY a.created_at DESC""",
            (user["id"],),
        )
        apps = cur.fetchall()

        # 2. 查这些申请的所有审批记录
        app_ids = [a["id"] for a in apps]
        approvals_map = {}
        if app_ids:
            placeholders = ",".join(["%s"] * len(app_ids))
            cur.execute(
                f"""SELECT r.apply_id, r.action, r.reason, r.created_at,
                          u.id AS reviewer_id, u.username AS reviewer_name
                   FROM approval_record r
                   INNER JOIN user u ON u.id = r.reviewer_id
                   WHERE r.apply_id IN ({placeholders})
                   ORDER BY r.created_at ASC""",
                app_ids,
            )
            for row in cur.fetchall():
                aid = row.pop("apply_id")
                approvals_map.setdefault(aid, []).append(jsonable(row))

    for a in apps:
        a["approvals"] = approvals_map.get(a["id"], [])

    return [jsonable(a) for a in apps]


@app.get("/api/applications/pending")
def pending_for_me(user=Depends(current_user), conn=Depends(get_conn)):
    """待我审批：别人提交的 pending 申请，且我还没审过的（多人审批模式）。"""
    sql = """
        SELECT a.id, a.item_name, a.price, a.description, a.image_path,
               a.created_at, a.user_id, u.username AS applicant_name
        FROM item_apply a
        INNER JOIN user u ON u.id = a.user_id
        WHERE a.status = 'pending' AND a.user_id <> %s
          AND NOT EXISTS (
            SELECT 1 FROM approval_record r
            WHERE r.apply_id = a.id AND r.reviewer_id = %s
          )
        ORDER BY a.created_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user["id"], user["id"]))
        rows = cur.fetchall()
    return [jsonable(r) for r in rows]


# ==================================================================
# 三、审批（核心约束：禁止审批自己的申请）
# ==================================================================
@app.post("/api/applications/{apply_id}/review")
def review_application(
    apply_id: int,
    data: ReviewIn,
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, item_name, status FROM item_apply WHERE id = %s FOR UPDATE",
                (apply_id,),
            )
            apply = cur.fetchone()

            if not apply:
                raise HTTPException(status_code=404, detail="申请不存在")

            # ★★★ 后端强制拦截：即使抓包直接调接口也不允许审批自己的申请
            if apply["user_id"] == user["id"]:
                raise HTTPException(status_code=400, detail="不允许审批自己提交的申请")

            if apply["status"] != "pending":
                raise HTTPException(status_code=400, detail="该申请已关闭，无法审批")

            # 检查是否已审批过（多人审批模式下每人只能审一次）
            cur.execute(
                "SELECT id FROM approval_record WHERE apply_id = %s AND reviewer_id = %s",
                (apply_id, user["id"]),
            )
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="您已审批过该申请，不能重复审批")

            # 写入审批记录（不改 item_apply.status，保持 pending 供其他用户继续审批）
            cur.execute(
                """INSERT INTO approval_record (apply_id, reviewer_id, action, reason)
                   VALUES (%s, %s, %s, %s)""",
                (apply_id, user["id"], data.action, data.reason),
            )

            # 审批完成后自动给申请人发一条通知消息
            result_text = "已通过" if data.action == "approved" else "已驳回"
            content = (
                f"您提交的物品申请「{apply['item_name']}」{result_text}，"
                f"审批人：{user['username']}，审批理由：{data.reason}"
            )
            cur.execute(
                """INSERT INTO message (user_id, apply_id, content, is_read)
                   VALUES (%s, %s, %s, 0)""",
                (apply["user_id"], apply_id, content),
            )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="审批失败，请稍后重试")

    return {"message": "审批完成"}


# ==================================================================
# 四、消息通知
# ==================================================================
@app.get("/api/messages")
def list_messages(user=Depends(current_user), conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, apply_id, content, is_read, created_at
               FROM message WHERE user_id = %s ORDER BY created_at DESC""",
            (user["id"],),
        )
        rows = cur.fetchall()
    return [jsonable(r) for r in rows]


@app.get("/api/messages/unread-count")
def unread_count(user=Depends(current_user), conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM message WHERE user_id = %s AND is_read = 0",
            (user["id"],),
        )
        row = cur.fetchone()
    return {"count": row["cnt"]}


@app.post("/api/messages/{message_id}/read")
def mark_read(message_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    with conn.cursor() as cur:
        # 只能操作自己的消息
        affected = cur.execute(
            "UPDATE message SET is_read = 1 WHERE id = %s AND user_id = %s",
            (message_id, user["id"]),
        )
        conn.commit()
    if affected == 0:
        raise HTTPException(status_code=404, detail="消息不存在")
    return {"message": "已标记为已读"}


@app.post("/api/messages/read-all")
def mark_all_read(user=Depends(current_user), conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE message SET is_read = 1 WHERE user_id = %s AND is_read = 0",
            (user["id"],),
        )
        conn.commit()
    return {"message": "全部已读"}


# ==================================================================
# 首页统计（待审批数 / 我的申请数 / 未读消息数）
# ==================================================================
@app.get("/api/stats")
def get_stats(user=Depends(current_user), conn=Depends(get_conn)):
    """首页三个统计卡片所需的聚合数据。"""
    with conn.cursor() as cur:
        # 待我审批：别人提交的 pending 且我尚未审批过的
        cur.execute(
            """SELECT COUNT(*) AS cnt FROM item_apply a
               WHERE a.status='pending' AND a.user_id <> %s
                 AND NOT EXISTS (
                   SELECT 1 FROM approval_record r
                   WHERE r.apply_id = a.id AND r.reviewer_id = %s
                 )""",
            (user["id"], user["id"]),
        )
        pending = cur.fetchone()["cnt"]

        # 我的申请总数
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM item_apply WHERE user_id = %s",
            (user["id"],),
        )
        mine_total = cur.fetchone()["cnt"]

        # 我的申请收到的审批结果明细
        cur.execute(
            """SELECT r.action, COUNT(*) AS cnt
               FROM approval_record r
               INNER JOIN item_apply a ON a.id = r.apply_id
               WHERE a.user_id = %s
               GROUP BY r.action""",
            (user["id"],),
        )
        action_counts = {row["action"]: row["cnt"] for row in cur.fetchall()}

        # 未读消息数
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM message WHERE user_id = %s AND is_read = 0",
            (user["id"],),
        )
        unread = cur.fetchone()["cnt"]

    return {
        "pending": pending,
        "mine_total": mine_total,
        "mine_approved": action_counts.get("approved", 0),
        "mine_rejected": action_counts.get("rejected", 0),
        "unread": unread,
    }


# ==================================================================
# 五、好友功能：UID 管理 / 搜索 / 添加 / 列表 / 删除
# ==================================================================
@app.put("/api/user/uid")
def update_uid(data: UidIn, user=Depends(current_user), conn=Depends(get_conn)):
    """修改自己的好友 ID，后端强制唯一校验。"""
    new_uid = data.uid.strip()
    with conn.cursor() as cur:
        # 检查是否被他人占用
        cur.execute(
            "SELECT id FROM user WHERE uid = %s AND id <> %s",
            (new_uid, user["id"]),
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="该ID已被使用，请重新修改")
        cur.execute("UPDATE user SET uid = %s WHERE id = %s", (new_uid, user["id"]))
        conn.commit()
    return {"uid": new_uid, "message": "好友ID修改成功"}


@app.get("/api/users/search")
def search_by_uid(q: str, user=Depends(current_user), conn=Depends(get_conn)):
    """通过好友 ID 搜索用户（排除自己）。"""
    q = q.strip()
    if not q:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, username, uid FROM user
               WHERE uid = %s AND id <> %s LIMIT 10""",
            (q, user["id"]),
        )
        rows = cur.fetchall()
    return [jsonable(r) for r in rows]


@app.get("/api/friends")
def list_friends(user=Depends(current_user), conn=Depends(get_conn)):
    """我的好友列表。"""
    sql = """
        SELECT u.id, u.username, u.uid, f.created_at
        FROM friendship f
        INNER JOIN user u ON u.id = f.friend_id
        WHERE f.user_id = %s
        ORDER BY f.created_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user["id"],))
        rows = cur.fetchall()
    return [jsonable(r) for r in rows]


@app.post("/api/friends/{target_user_id}")
def add_friend(target_user_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    """发送好友申请（对方需同意后才能成为好友）。"""
    if target_user_id == user["id"]:
        raise HTTPException(status_code=400, detail="不能添加自己为好友")
    try:
        with conn.cursor() as cur:
            # 确认目标用户存在
            cur.execute("SELECT id, username FROM user WHERE id = %s", (target_user_id,))
            target = cur.fetchone()
            if not target:
                raise HTTPException(status_code=404, detail="用户不存在")

            # 检查是否已是好友
            cur.execute(
                "SELECT id FROM friendship WHERE user_id = %s AND friend_id = %s",
                (user["id"], target_user_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="你们已经是好友了")

            # 检查是否已发过申请（pending 或 accepted 或 rejected 都查）
            cur.execute(
                """SELECT id, status FROM friend_request
                   WHERE from_user_id = %s AND to_user_id = %s""",
                (user["id"], target_user_id),
            )
            existing = cur.fetchone()
            if existing:
                if existing["status"] == "pending":
                    raise HTTPException(status_code=400, detail="已发送过申请，等待对方确认")
                if existing["status"] == "accepted":
                    raise HTTPException(status_code=400, detail="你们已经是好友了")
                # rejected 可以重新发起
                cur.execute(
                    "UPDATE friend_request SET status='pending', handled_at=NULL WHERE id=%s",
                    (existing["id"],),
                )
            else:
                cur.execute(
                    """INSERT INTO friend_request (from_user_id, to_user_id, status)
                       VALUES (%s, %s, 'pending')""",
                    (user["id"], target_user_id),
                )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="发送申请失败")
    return {"message": f"已向「{target['username']}」发送好友申请，等待对方确认"}


@app.get("/api/friend-requests")
def list_friend_requests(user=Depends(current_user), conn=Depends(get_conn)):
    """我收到的好友申请列表（待处理）。"""
    sql = """
        SELECT r.id, r.from_user_id, r.status, r.created_at,
               u.username AS from_username, u.uid AS from_uid
        FROM friend_request r
        INNER JOIN user u ON u.id = r.from_user_id
        WHERE r.to_user_id = %s AND r.status = 'pending'
        ORDER BY r.created_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user["id"],))
        rows = cur.fetchall()
    return [jsonable(r) for r in rows]


@app.get("/api/friend-requests/count")
def friend_request_count(user=Depends(current_user), conn=Depends(get_conn)):
    """待处理好友申请数量（轮询用）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM friend_request WHERE to_user_id = %s AND status = 'pending'",
            (user["id"],),
        )
        row = cur.fetchone()
    return {"count": row["cnt"]}


@app.post("/api/friend-requests/{request_id}/accept")
def accept_friend_request(request_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    """同意好友申请：更新申请状态 + 双向写入 friendship。"""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, from_user_id, to_user_id, status
                   FROM friend_request WHERE id = %s FOR UPDATE""",
                (request_id,),
            )
            req = cur.fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="好友申请不存在")
            if req["to_user_id"] != user["id"]:
                raise HTTPException(status_code=403, detail="无权处理此申请")
            if req["status"] != "pending":
                raise HTTPException(status_code=400, detail="该申请已处理过")

            # 更新申请状态
            now = datetime.now()
            cur.execute(
                "UPDATE friend_request SET status='accepted', handled_at=%s WHERE id=%s",
                (now, request_id),
            )

            # 双向写入好友关系
            cur.execute(
                "INSERT IGNORE INTO friendship (user_id, friend_id) VALUES (%s, %s)",
                (req["from_user_id"], req["to_user_id"]),
            )
            cur.execute(
                "INSERT IGNORE INTO friendship (user_id, friend_id) VALUES (%s, %s)",
                (req["to_user_id"], req["from_user_id"]),
            )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="处理申请失败")
    return {"message": "已同意好友申请"}


@app.post("/api/friend-requests/{request_id}/reject")
def reject_friend_request(request_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    """拒绝好友申请。"""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, to_user_id, status
                   FROM friend_request WHERE id = %s FOR UPDATE""",
                (request_id,),
            )
            req = cur.fetchone()
            if not req:
                raise HTTPException(status_code=404, detail="好友申请不存在")
            if req["to_user_id"] != user["id"]:
                raise HTTPException(status_code=403, detail="无权处理此申请")
            if req["status"] != "pending":
                raise HTTPException(status_code=400, detail="该申请已处理过")

            now = datetime.now()
            cur.execute(
                "UPDATE friend_request SET status='rejected', handled_at=%s WHERE id=%s",
                (now, request_id),
            )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="处理申请失败")
    return {"message": "已拒绝好友申请"}


@app.delete("/api/friends/{target_user_id}")
def remove_friend(target_user_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    """删除好友（双向删除）。"""
    with conn.cursor() as cur:
        affected = cur.execute(
            "DELETE FROM friendship WHERE user_id = %s AND friend_id = %s",
            (user["id"], target_user_id),
        )
        cur.execute(
            "DELETE FROM friendship WHERE user_id = %s AND friend_id = %s",
            (target_user_id, user["id"]),
        )
        conn.commit()
    if affected == 0:
        raise HTTPException(status_code=404, detail="该好友不存在")
    return {"message": "已删除好友"}


@app.get("/")
def health():
    return {"status": "ok", "service": "item-approval-api"}
