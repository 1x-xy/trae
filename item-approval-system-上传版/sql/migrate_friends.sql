-- =============================================================
-- 增量迁移脚本：在已有数据库上增加好友功能
-- 前提：item_approval 数据库已存在且 user/item_apply/message 三张表已有数据
-- 执行后会：1) user 表加 uid 列并回填 2) 新建 friendship 表
-- =============================================================

USE item_approval;

-- 1. 给 user 表增加 uid 列（允许空，先回填再加 NOT NULL）
ALTER TABLE `user` ADD COLUMN `uid` VARCHAR(20) NULL COMMENT '好友ID（自动生成，可修改，唯一）' AFTER `password_hash`;

-- 2. 为已有用户回填随机 uid（8位大写字母+数字）
--    利用 UUID 截取前8位并大写
UPDATE `user` SET `uid` = UPPER(SUBSTRING(MD5(RAND()), 1, 8)) WHERE `uid` IS NULL;

-- 3. 确保回填后无空值，然后加 NOT NULL 和唯一约束
ALTER TABLE `user` MODIFY `uid` VARCHAR(20) NOT NULL COMMENT '好友ID（自动生成，可修改，唯一）';
ALTER TABLE `user` ADD UNIQUE KEY `uk_user_uid` (`uid`);

-- 4. 创建好友关系表
CREATE TABLE IF NOT EXISTS `friendship` (
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
