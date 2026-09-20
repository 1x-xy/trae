-- =============================================================
-- 物品申报审批系统 数据库初始化脚本
-- 数据库：MySQL 5.7+ / 8.x，字符集 utf8mb4
-- 共 6 张表：user、item_apply、approval_record、message、friendship、friend_request
-- =============================================================

CREATE DATABASE IF NOT EXISTS item_approval
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE item_approval;

-- -------------------------------------------------------------
-- 1. 用户表：所有用户身份平等，无管理员角色
--    密码使用 bcrypt 加密后存入 password_hash，禁止明文
--    uid 为系统自动生成的唯一好友ID，可修改但不可重复
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `message`;
DROP TABLE IF EXISTS `friendship`;
DROP TABLE IF EXISTS `friend_request`;
DROP TABLE IF EXISTS `approval_record`;
DROP TABLE IF EXISTS `item_apply`;
DROP TABLE IF EXISTS `user`;

CREATE TABLE `user` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    `username`      VARCHAR(50)  NOT NULL COMMENT '登录账号（唯一）',
    `password_hash` VARCHAR(255) NOT NULL COMMENT 'bcrypt加密后的密码',
    `uid`           VARCHAR(20)  NOT NULL COMMENT '好友ID（自动生成，可修改，唯一）',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_username` (`username`),
    UNIQUE KEY `uk_user_uid` (`uid`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT ='用户表';

-- -------------------------------------------------------------
-- 2. 物品申请表
--    status: pending 待审批 / approved 已通过 / rejected 已驳回
--    user_id 为申请人，reviewer_id 为审批人（审批前允许为空）
--    image_path 仅保存图片在服务器上的访问路径，不存图片本体
-- -------------------------------------------------------------
CREATE TABLE `item_apply` (
    `id`            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '申请ID',
    `user_id`       BIGINT        NOT NULL COMMENT '申请人ID',
    `item_name`     VARCHAR(100)  NOT NULL COMMENT '物品名称',
    `price`         DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '物品价格',
    `description`   TEXT          NULL COMMENT '物品描述',
    `image_path`    VARCHAR(255)  NOT NULL COMMENT '图片访问路径',
    `status`        ENUM('pending', 'approved', 'rejected')
                                  NOT NULL DEFAULT 'pending' COMMENT '审批状态',
    `reviewer_id`   BIGINT        NULL COMMENT '审批人ID',
    `review_reason` VARCHAR(500)  NULL COMMENT '审批理由（必填）',
    `reviewed_at`   DATETIME      NULL COMMENT '审批时间',
    `created_at`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
    PRIMARY KEY (`id`),
    KEY `idx_apply_user` (`user_id`),
    KEY `idx_apply_status_user` (`status`, `user_id`),
    CONSTRAINT `fk_apply_user`
        FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
    CONSTRAINT `fk_apply_reviewer`
        FOREIGN KEY (`reviewer_id`) REFERENCES `user` (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT ='物品申请表';

-- -------------------------------------------------------------
-- 2.5 审批记录表：每个用户对同一申请各审一次（多人审批）
--    UNIQUE(apply_id, reviewer_id) 保证同一用户不能对同一申请审批两次
-- -------------------------------------------------------------
CREATE TABLE `approval_record` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '审批记录ID',
    `apply_id`   BIGINT       NOT NULL COMMENT '关联申请ID',
    `reviewer_id` BIGINT      NOT NULL COMMENT '审批人ID',
    `action`     ENUM('approved', 'rejected') NOT NULL COMMENT '审批操作',
    `reason`     VARCHAR(500) NOT NULL COMMENT '审批理由',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '审批时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_apply_reviewer` (`apply_id`, `reviewer_id`),
    KEY `idx_ar_reviewer` (`reviewer_id`),
    CONSTRAINT `fk_ar_apply`
        FOREIGN KEY (`apply_id`) REFERENCES `item_apply` (`id`),
    CONSTRAINT `fk_ar_reviewer`
        FOREIGN KEY (`reviewer_id`) REFERENCES `user` (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT ='审批记录表';

-- -------------------------------------------------------------
-- 3. 消息通知表：审批完成后自动写入一条，接收人为申请人
--    申报提交后也会给好友写入推送消息
--    is_read: 0 未读 / 1 已读
-- -------------------------------------------------------------
CREATE TABLE `message` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '消息ID',
    `user_id`    BIGINT       NOT NULL COMMENT '接收人ID（申请提交人或好友）',
    `apply_id`   BIGINT       NOT NULL COMMENT '关联申请ID',
    `content`    VARCHAR(500) NOT NULL COMMENT '消息内容',
    `is_read`    TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否已读：0未读 1已读',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间',
    PRIMARY KEY (`id`),
    KEY `idx_msg_user_read` (`user_id`, `is_read`),
    CONSTRAINT `fk_msg_user`
        FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
    CONSTRAINT `fk_msg_apply`
        FOREIGN KEY (`apply_id`) REFERENCES `item_apply` (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT ='消息通知表';

-- -------------------------------------------------------------
-- 4. 好友关系表：记录用户之间的好友关系（单向存储，添加时双向写入）
-- -------------------------------------------------------------
CREATE TABLE `friendship` (
    `id`         BIGINT   NOT NULL AUTO_INCREMENT COMMENT '关系ID',
    `user_id`    BIGINT   NOT NULL COMMENT '用户ID',
    `friend_id`  BIGINT   NOT NULL COMMENT '好友用户ID',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '成为好友时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_friend_pair` (`user_id`, `friend_id`),
    KEY `idx_friend_user` (`user_id`),
    CONSTRAINT `fk_fs_user`
        FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
    CONSTRAINT `fk_fs_friend`
        FOREIGN KEY (`friend_id`) REFERENCES `user` (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT ='好友关系表';

-- -------------------------------------------------------------
-- 5. 好友申请表：发送申请→对方同意后双向写入 friendship
--    status: pending 待处理 / accepted 已同意 / rejected 已拒绝
-- -------------------------------------------------------------
CREATE TABLE `friend_request` (
    `id`          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '申请ID',
    `from_user_id` BIGINT     NOT NULL COMMENT '发起人ID',
    `to_user_id`   BIGINT     NOT NULL COMMENT '接收人ID',
    `status`      ENUM('pending', 'accepted', 'rejected')
                              NOT NULL DEFAULT 'pending' COMMENT '申请状态',
    `created_at`  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发起时间',
    `handled_at`  DATETIME    NULL COMMENT '处理时间（同意/拒绝时写入）',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_req_pair` (`from_user_id`, `to_user_id`),
    KEY `idx_req_to` (`to_user_id`, `status`),
    CONSTRAINT `fk_req_from`
        FOREIGN KEY (`from_user_id`) REFERENCES `user` (`id`),
    CONSTRAINT `fk_req_to`
        FOREIGN KEY (`to_user_id`) REFERENCES `user` (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT ='好友申请表';
