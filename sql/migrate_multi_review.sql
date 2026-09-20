-- =============================================================
-- 增量迁移脚本：多人审批功能
-- 在已有数据库上新增 approval_record 表
-- 不影响已有数据，已有审批数据保留在 item_apply 表中
-- =============================================================

USE item_approval;

CREATE TABLE IF NOT EXISTS `approval_record` (
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
