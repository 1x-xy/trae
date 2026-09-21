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
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from jose import jwt, JWTError

# ------------------------------------------------------------------
# 配置（可通过环境变量覆盖，便于本地/部署切换）
# ------------------------------------------------------------------
DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()  # mysql / postgres / sqlite
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "item_approval")
# Render 会提供 DATABASE_URL，优先使用
DATABASE_URL = os.getenv("DATABASE_URL", "")

JWT_SECRET = os.getenv("JWT_SECRET", "item-approval-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # token 有效期 1 天

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# SQLite 模式（PythonAnywhere 免费版无 MySQL/PG）：数据存服务器本地文件
SQLITE_FILE = os.getenv("DB_FILE", "") or os.path.join(BASE_DIR, "item_approval.db")
if DB_TYPE == "sqlite":
    os.makedirs(os.path.dirname(SQLITE_FILE), exist_ok=True)

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
# 云端部署：启动时自动建表（免手动执行 SQL），MySQL / PostgreSQL / SQLite 均支持
# ------------------------------------------------------------------
@app.on_event("startup")
def init_tables():
    if _is_postgres():
        _init_pg_tables()
    elif DB_TYPE == "sqlite":
        _init_sqlite_tables()
    else:
        _init_mysql_tables()


def _init_mysql_tables():
    """MySQL 自动建表（幂等：CREATE TABLE IF NOT EXISTS）。"""
    import pymysql
    from pymysql.cursors import DictCursor
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, database=DB_NAME,
        charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `users` (
                    `id`            BIGINT       NOT NULL AUTO_INCREMENT,
                    `username`      VARCHAR(50)  NOT NULL,
                    `password_hash` VARCHAR(255) NOT NULL,
                    `uid`           VARCHAR(20)  NOT NULL,
                    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uk_user_username` (`username`),
                    UNIQUE KEY `uk_user_uid` (`uid`)
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `item_apply` (
                    `id`            BIGINT        NOT NULL AUTO_INCREMENT,
                    `user_id`       BIGINT        NOT NULL,
                    `item_name`     VARCHAR(100)  NOT NULL,
                    `price`         DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                    `description`   TEXT          NULL,
                    `image_path`    VARCHAR(255)  NOT NULL,
                    `status`        VARCHAR(20)   NOT NULL DEFAULT 'pending',
                    `reviewer_id`   BIGINT        NULL,
                    `review_reason` VARCHAR(500)  NULL,
                    `reviewed_at`   DATETIME      NULL,
                    `created_at`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    KEY `idx_apply_user` (`user_id`),
                    KEY `idx_apply_status_user` (`status`, `user_id`),
                    CONSTRAINT `fk_apply_user`
                        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
                    CONSTRAINT `fk_apply_reviewer`
                        FOREIGN KEY (`reviewer_id`) REFERENCES `users` (`id`)
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `approval_record` (
                    `id`          BIGINT      NOT NULL AUTO_INCREMENT,
                    `apply_id`    BIGINT      NOT NULL,
                    `reviewer_id` BIGINT      NOT NULL,
                    `action`      VARCHAR(20) NOT NULL,
                    `reason`      VARCHAR(500) NOT NULL,
                    `created_at`  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uk_apply_reviewer` (`apply_id`, `reviewer_id`),
                    KEY `idx_ar_reviewer` (`reviewer_id`),
                    CONSTRAINT `fk_ar_apply`
                        FOREIGN KEY (`apply_id`) REFERENCES `item_apply` (`id`),
                    CONSTRAINT `fk_ar_reviewer`
                        FOREIGN KEY (`reviewer_id`) REFERENCES `users` (`id`)
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `message` (
                    `id`         BIGINT       NOT NULL AUTO_INCREMENT,
                    `user_id`    BIGINT       NOT NULL,
                    `apply_id`   BIGINT       NOT NULL,
                    `content`    VARCHAR(500) NOT NULL,
                    `is_read`    TINYINT(1)   NOT NULL DEFAULT 0,
                    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    KEY `idx_msg_user_read` (`user_id`, `is_read`),
                    CONSTRAINT `fk_msg_user`
                        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
                    CONSTRAINT `fk_msg_apply`
                        FOREIGN KEY (`apply_id`) REFERENCES `item_apply` (`id`)
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `friendship` (
                    `id`         BIGINT   NOT NULL AUTO_INCREMENT,
                    `user_id`    BIGINT   NOT NULL,
                    `friend_id`  BIGINT   NOT NULL,
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uk_friend_pair` (`user_id`, `friend_id`),
                    KEY `idx_friend_user` (`user_id`),
                    CONSTRAINT `fk_fs_user`
                        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
                    CONSTRAINT `fk_fs_friend`
                        FOREIGN KEY (`friend_id`) REFERENCES `users` (`id`)
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS `friend_request` (
                    `id`           BIGINT      NOT NULL AUTO_INCREMENT,
                    `from_user_id` BIGINT      NOT NULL,
                    `to_user_id`   BIGINT      NOT NULL,
                    `status`       VARCHAR(20) NOT NULL DEFAULT 'pending',
                    `created_at`   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `handled_at`   DATETIME    NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uk_req_pair` (`from_user_id`, `to_user_id`),
                    KEY `idx_req_to` (`to_user_id`, `status`),
                    CONSTRAINT `fk_req_from`
                        FOREIGN KEY (`from_user_id`) REFERENCES `users` (`id`),
                    CONSTRAINT `fk_req_to`
                        FOREIGN KEY (`to_user_id`) REFERENCES `users` (`id`)
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci
                """
            )
        conn.commit()
        print("[startup] MySQL 数据表已就绪（自动建表完成）")
    except Exception as e:
        conn.rollback()
        print(f"[startup] MySQL 自动建表失败: {e}")
    finally:
        conn.close()


def _init_pg_tables():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, dbname=DB_NAME,
            cursor_factory=RealDictCursor,
        )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id            BIGSERIAL PRIMARY KEY,
                    username      VARCHAR(50)  NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    uid           VARCHAR(20)  NOT NULL UNIQUE,
                    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS item_apply (
                    id            BIGSERIAL PRIMARY KEY,
                    user_id       BIGINT        NOT NULL REFERENCES users(id),
                    item_name     VARCHAR(100) NOT NULL,
                    price         NUMERIC(10,2) NOT NULL DEFAULT 0,
                    description   TEXT          NULL,
                    image_path    VARCHAR(255) NOT NULL,
                    status        VARCHAR(20)  NOT NULL DEFAULT 'pending',
                    reviewer_id   BIGINT        NULL REFERENCES users(id),
                    review_reason VARCHAR(500) NULL,
                    reviewed_at   TIMESTAMP     NULL,
                    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_record (
                    id          BIGSERIAL PRIMARY KEY,
                    apply_id    BIGINT       NOT NULL REFERENCES item_apply(id),
                    reviewer_id BIGINT       NOT NULL REFERENCES users(id),
                    action      VARCHAR(20)  NOT NULL,
                    reason      VARCHAR(500) NOT NULL,
                    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (apply_id, reviewer_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS message (
                    id         BIGSERIAL PRIMARY KEY,
                    user_id    BIGINT       NOT NULL REFERENCES users(id),
                    apply_id   BIGINT       NOT NULL REFERENCES item_apply(id),
                    content    VARCHAR(500) NOT NULL,
                    is_read    SMALLINT     NOT NULL DEFAULT 0,
                    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS friendship (
                    id         BIGSERIAL PRIMARY KEY,
                    user_id    BIGINT    NOT NULL REFERENCES users(id),
                    friend_id  BIGINT    NOT NULL REFERENCES users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, friend_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS friend_request (
                    id           BIGSERIAL PRIMARY KEY,
                    from_user_id BIGINT      NOT NULL REFERENCES users(id),
                    to_user_id   BIGINT      NOT NULL REFERENCES users(id),
                    status       VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    handled_at   TIMESTAMP   NULL,
                    UNIQUE (from_user_id, to_user_id)
                )
                """
            )
        conn.commit()
        print("[startup] PostgreSQL 数据表已就绪（自动建表完成）")
    except Exception as e:
        conn.rollback()
        print(f"[startup] 自动建表失败: {e}")
    finally:
        conn.close()


def _init_sqlite_tables():
    """SQLite 自动建表（幂等：CREATE TABLE IF NOT EXISTS）。"""
    import sqlite3
    conn = sqlite3.connect(SQLITE_FILE)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      VARCHAR(50)  NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                uid           VARCHAR(20)  NOT NULL UNIQUE,
                created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS item_apply (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER       NOT NULL REFERENCES users(id),
                item_name     VARCHAR(100)  NOT NULL,
                price         REAL          NOT NULL DEFAULT 0,
                description   TEXT          NULL,
                image_path    VARCHAR(255)  NOT NULL,
                status        VARCHAR(20)   NOT NULL DEFAULT 'pending',
                reviewer_id   INTEGER       NULL REFERENCES users(id),
                review_reason VARCHAR(500)  NULL,
                reviewed_at   TEXT          NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_record (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                apply_id    INTEGER      NOT NULL REFERENCES item_apply(id),
                reviewer_id INTEGER      NOT NULL REFERENCES users(id),
                action      VARCHAR(20)  NOT NULL,
                reason      VARCHAR(500) NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE (apply_id, reviewer_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS message (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER      NOT NULL REFERENCES users(id),
                apply_id   INTEGER      NOT NULL REFERENCES item_apply(id),
                content    VARCHAR(500) NOT NULL,
                is_read    INTEGER      NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS friendship (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                friend_id  INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                UNIQUE (user_id, friend_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS friend_request (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER      NOT NULL REFERENCES users(id),
                to_user_id   INTEGER      NOT NULL REFERENCES users(id),
                status       VARCHAR(20)  NOT NULL DEFAULT 'pending',
                created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                handled_at   TEXT         NULL,
                UNIQUE (from_user_id, to_user_id)
            )
            """
        )
        conn.commit()
        print("[startup] SQLite 数据表已就绪（自动建表完成）")
    except Exception as e:
        conn.rollback()
        print(f"[startup] SQLite 自动建表失败: {e}")
    finally:
        conn.close()


# ------------------------------------------------------------------
# 数据库连接（每个请求一个连接，根据 DB_TYPE 自动选择 MySQL / PostgreSQL / SQLite）
# ------------------------------------------------------------------
class _SqliteCursor:
    """SQLite 游标包装器：把 MySQL 风格的 %s 占位符翻译成 SQLite 的 ?，
    并抹掉 SQLite 不支持的语法，其余能力委托给原生 sqlite3 游标。
    返回 rowcount 以兼容 pymysql 的 execute() 语义（如 affected == 0 判断）。"""

    def __init__(self, cur):
        self._cur = cur

    @staticmethod
    def _translate(sql: str) -> str:
        sql = sql.replace("%s", "?").replace("INSERT IGNORE INTO", "INSERT OR IGNORE INTO")
        import re as _re
        return _re.sub(r"\s+FOR UPDATE", "", sql, flags=_re.IGNORECASE)

    def execute(self, sql, params=None):
        sql = self._translate(sql)
        if params is None:
            self._cur.execute(sql)
        else:
            self._cur.execute(sql, params)
        return self._cur.rowcount

    def executemany(self, sql, seq):
        self._cur.executemany(self._translate(sql), seq)
        return self._cur.rowcount

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size)

    def close(self):
        self._cur.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _SqliteConn:
    """SQLite 连接包装器：提供与 pymysql 连接相同的 cursor()/commit()/rollback()/close() 接口。"""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _SqliteCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_conn():
    if DB_TYPE == "sqlite":
        import sqlite3
        conn = sqlite3.connect(SQLITE_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield _SqliteConn(conn)
        return
    if DB_TYPE == "postgres" or DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        else:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, user=DB_USER,
                password=DB_PASSWORD, dbname=DB_NAME,
                cursor_factory=RealDictCursor,
            )
    else:
        import pymysql
        from pymysql.cursors import DictCursor
        conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER,
            password=DB_PASSWORD, database=DB_NAME,
            charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
        )
    try:
        yield conn
    finally:
        conn.close()


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def _is_postgres() -> bool:
    """当前是否运行在 PostgreSQL 模式（本地默认 MySQL，云端走 PostgreSQL）。"""
    return DB_TYPE == "postgres" or bool(DATABASE_URL)


def _insert_returning_id(cur, sql: str, params: tuple):
    """兼容 MySQL / PostgreSQL 的 INSERT：PostgreSQL 用 RETURNING id，MySQL 用 lastrowid。"""
    if _is_postgres():
        cur.execute(sql.rstrip(";") + " RETURNING id", params)
        return cur.fetchone()["id"]
    cur.execute(sql, params)
    return cur.lastrowid


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


def jsonable(row) -> dict:
    """把数据库返回的 datetime / Decimal 转成 JSON 友好类型（兼容 dict 与 sqlite3.Row）。"""
    if not isinstance(row, dict):
        row = dict(row)
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
            "SELECT id, username, uid, created_at FROM users WHERE id = %s", (user_id,)
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
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="用户名已存在")

        # 生成唯一 uid，重试最多 100 次避免偶然碰撞
        for _ in range(100):
            uid = generate_uid()
            cur.execute("SELECT id FROM users WHERE uid = %s", (uid,))
            if not cur.fetchone():
                break

        user_id = _insert_returning_id(
            cur,
            "INSERT INTO users (username, password_hash, uid) VALUES (%s, %s, %s)",
            (username, hash_password(data.password), uid),
        )
        conn.commit()
    return {"id": user_id, "username": username, "uid": uid, "message": "注册成功"}


@app.post("/api/auth/login")
def login(data: AuthIn, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, uid FROM users WHERE username = %s",
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
        apply_id = _insert_returning_id(
            cur,
            """INSERT INTO item_apply
               (user_id, item_name, price, description, image_path, status)
               VALUES (%s, %s, %s, %s, %s, 'pending')""",
            (user["id"], item_name, price, description.strip(), image_path),
        )

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
        apps = [dict(r) for r in cur.fetchall()]  # sqlite3.Row 不可变，先转 dict

        # 2. 查这些申请的所有审批记录
        app_ids = [a["id"] for a in apps]
        approvals_map = {}
        if app_ids:
            placeholders = ",".join(["%s"] * len(app_ids))
            cur.execute(
                f"""SELECT r.apply_id, r.action, r.reason, r.created_at,
                          u.id AS reviewer_id, u.username AS reviewer_name
                   FROM approval_record r
                   INNER JOIN users u ON u.id = r.reviewer_id
                   WHERE r.apply_id IN ({placeholders})
                   ORDER BY r.created_at ASC""",
                app_ids,
            )
            for row in cur.fetchall():
                row = dict(row)  # sqlite3.Row 不可变，先转 dict 再 pop
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
        INNER JOIN users u ON u.id = a.user_id
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
            "SELECT id FROM users WHERE uid = %s AND id <> %s",
            (new_uid, user["id"]),
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="该ID已被使用，请重新修改")
        cur.execute("UPDATE users SET uid = %s WHERE id = %s", (new_uid, user["id"]))
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
            """SELECT id, username, uid FROM users
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
        INNER JOIN users u ON u.id = f.friend_id
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
            cur.execute("SELECT id, username FROM users WHERE id = %s", (target_user_id,))
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
        INNER JOIN users u ON u.id = r.from_user_id
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


# 前端构建产物目录（frontend/dist）。若存在则由后端同域托管（PythonAnywhere 单应用部署）
FRONTEND_DIST = os.path.join(BASE_DIR, "..", "frontend", "dist")


@app.get("/")
def home():
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"status": "ok", "service": "item-approval-api"}


# Vue history 路由兜底：所有未匹配的非 API 路径回退到 index.html
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not Found")
    file_path = os.path.join(FRONTEND_DIST, full_path)
    if full_path and os.path.isfile(file_path):
        return FileResponse(file_path)
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
