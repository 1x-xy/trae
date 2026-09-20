-- =============================================================
-- 物品申报审批系统 数据库初始化脚本（PostgreSQL / 云端部署）
-- 说明：云端部署时后端启动会自动建表（main.py startup），
--       本脚本仅用于手动初始化或本地 PostgreSQL 调试。
-- 共 6 张表：users、item_apply、approval_record、message、friendship、friend_request
-- =============================================================

-- 1. 用户表：所有用户身份平等，无管理员角色
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    uid           VARCHAR(20)  NOT NULL UNIQUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. 物品申请表：status 为 pending / approved / rejected
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
);

-- 2.5 审批记录表：UNIQUE(apply_id, reviewer_id) 保证同一用户不能重复审批
CREATE TABLE IF NOT EXISTS approval_record (
    id          BIGSERIAL PRIMARY KEY,
    apply_id    BIGINT       NOT NULL REFERENCES item_apply(id),
    reviewer_id BIGINT       NOT NULL REFERENCES users(id),
    action      VARCHAR(20)  NOT NULL,
    reason      VARCHAR(500) NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (apply_id, reviewer_id)
);

-- 3. 消息通知表：is_read 用 SMALLINT 保持与后端 0/1 判断兼容
CREATE TABLE IF NOT EXISTS message (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT       NOT NULL REFERENCES users(id),
    apply_id   BIGINT       NOT NULL REFERENCES item_apply(id),
    content    VARCHAR(500) NOT NULL,
    is_read    SMALLINT     NOT NULL DEFAULT 0,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. 好友关系表：单向存储，添加好友时双向写入
CREATE TABLE IF NOT EXISTS friendship (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT    NOT NULL REFERENCES users(id),
    friend_id  BIGINT    NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, friend_id)
);

-- 5. 好友申请表：pending / accepted / rejected
CREATE TABLE IF NOT EXISTS friend_request (
    id           BIGSERIAL PRIMARY KEY,
    from_user_id BIGINT      NOT NULL REFERENCES users(id),
    to_user_id   BIGINT      NOT NULL REFERENCES users(id),
    status       VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    handled_at   TIMESTAMP   NULL,
    UNIQUE (from_user_id, to_user_id)
);
