-- =============================================================
-- 增量迁移脚本：好友申请功能
-- 在已有数据库上新增 friend_request 表
-- =============================================================

USE item_approval;

CREATE TABLE IF NOT EXISTS `friend_request` (
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
