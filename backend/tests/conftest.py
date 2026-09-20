"""
pytest 公共 fixture：
- 创建独立测试数据库 item_approval_test，避免污染开发数据
- 用 TestClient 启动 FastAPI 应用
- 提供注册+登录的辅助函数，减少测试样板代码
"""
import os
import sys
import pymysql
import pytest
from fastapi.testclient import TestClient

# 把 backend 目录加入 path，使测试能 import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 指向测试数据库（必须在实际导入 main 之前设置环境变量）
os.environ["DB_NAME"] = "item_approval_test"
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_USER", "root")
os.environ.setdefault("DB_PASSWORD", "xgj521478963")

import main as app_module

# 复用 init.sql 建表脚本，但把库名替换为测试库
INIT_SQL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "sql", "init.sql",
)


def _init_test_db():
    """连接 MySQL 服务器，创建测试库并执行建表脚本。"""
    conn = pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS item_approval_test "
                        "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        with open(INIT_SQL_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
        # 把 init.sql 里的 item_approval 替换为 item_approval_test
        sql = sql.replace("item_approval", "item_approval_test")
        with conn.cursor() as cur:
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    """session 级：整个测试会话开始前建库建表，结束后清空。"""
    _init_test_db()
    yield
    # 清理测试库
    conn = pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("DROP DATABASE IF EXISTS item_approval_test")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client():
    """每个测试函数都拿到干净的 TestClient。"""
    # 每个测试前清空所有表数据，保持隔离
    conn = pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database="item_approval_test",
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            cur.execute("TRUNCATE TABLE message")
            cur.execute("TRUNCATE TABLE approval_record")
            cur.execute("TRUNCATE TABLE friendship")
            cur.execute("TRUNCATE TABLE friend_request")
            cur.execute("TRUNCATE TABLE item_apply")
            cur.execute("TRUNCATE TABLE users")
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()
    finally:
        conn.close()

    with TestClient(app_module.app) as c:
        yield c


def _register_and_login(client, username: str, password: str = "123456"):
    """注册并登录，返回 (token, user_info)。"""
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    data = resp.json()
    return data["token"], data["user"]
