-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: localhost    Database: item_approval
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `item_approval`
--

/*!40000 DROP DATABASE IF EXISTS `item_approval`*/;

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `item_approval` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `item_approval`;

--
-- Table structure for table `approval_record`
--

DROP TABLE IF EXISTS `approval_record`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `approval_record` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '审批记录ID',
  `apply_id` bigint NOT NULL COMMENT '关联申请ID',
  `reviewer_id` bigint NOT NULL COMMENT '审批人ID',
  `action` enum('approved','rejected') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '审批操作',
  `reason` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '审批理由',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '审批时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_apply_reviewer` (`apply_id`,`reviewer_id`),
  KEY `idx_ar_reviewer` (`reviewer_id`),
  CONSTRAINT `fk_ar_apply` FOREIGN KEY (`apply_id`) REFERENCES `item_apply` (`id`),
  CONSTRAINT `fk_ar_reviewer` FOREIGN KEY (`reviewer_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审批记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `approval_record`
--

LOCK TABLES `approval_record` WRITE;
/*!40000 ALTER TABLE `approval_record` DISABLE KEYS */;
INSERT INTO `approval_record` VALUES (1,1,1,'approved','看起来颜值很高','2026-09-14 15:00:09'),(2,1,3,'approved','看起来好好吃','2026-09-14 15:01:16');
/*!40000 ALTER TABLE `approval_record` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `friend_request`
--

DROP TABLE IF EXISTS `friend_request`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `friend_request` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '申请ID',
  `from_user_id` bigint NOT NULL COMMENT '发起人ID',
  `to_user_id` bigint NOT NULL COMMENT '接收人ID',
  `status` enum('pending','accepted','rejected') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '申请状态',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发起时间',
  `handled_at` datetime DEFAULT NULL COMMENT '处理时间（同意/拒绝时写入）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_req_pair` (`from_user_id`,`to_user_id`),
  KEY `idx_req_to` (`to_user_id`,`status`),
  CONSTRAINT `fk_req_from` FOREIGN KEY (`from_user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_req_to` FOREIGN KEY (`to_user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='好友申请表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `friend_request`
--

LOCK TABLES `friend_request` WRITE;
/*!40000 ALTER TABLE `friend_request` DISABLE KEYS */;
INSERT INTO `friend_request` VALUES (1,2,3,'pending','2026-09-14 15:08:03',NULL);
/*!40000 ALTER TABLE `friend_request` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `friendship`
--

DROP TABLE IF EXISTS `friendship`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `friendship` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '关系ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `friend_id` bigint NOT NULL COMMENT '好友用户ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '成为好友时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_friend_pair` (`user_id`,`friend_id`),
  KEY `idx_friend_user` (`user_id`),
  KEY `fk_fs_friend` (`friend_id`),
  CONSTRAINT `fk_fs_friend` FOREIGN KEY (`friend_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_fs_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='好友关系表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `friendship`
--

LOCK TABLES `friendship` WRITE;
/*!40000 ALTER TABLE `friendship` DISABLE KEYS */;
/*!40000 ALTER TABLE `friendship` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `item_apply`
--

DROP TABLE IF EXISTS `item_apply`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `item_apply` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '申请ID',
  `user_id` bigint NOT NULL COMMENT '申请人ID',
  `item_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '物品名称',
  `price` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '物品价格',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '物品描述',
  `image_path` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '图片访问路径',
  `status` enum('pending','approved','rejected') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '审批状态',
  `reviewer_id` bigint DEFAULT NULL COMMENT '审批人ID',
  `review_reason` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '审批理由（必填）',
  `reviewed_at` datetime DEFAULT NULL COMMENT '审批时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
  PRIMARY KEY (`id`),
  KEY `idx_apply_user` (`user_id`),
  KEY `idx_apply_status_user` (`status`,`user_id`),
  KEY `fk_apply_reviewer` (`reviewer_id`),
  CONSTRAINT `fk_apply_reviewer` FOREIGN KEY (`reviewer_id`) REFERENCES `user` (`id`),
  CONSTRAINT `fk_apply_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='物品申请表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `item_apply`
--

LOCK TABLES `item_apply` WRITE;
/*!40000 ALTER TABLE `item_apply` DISABLE KEYS */;
INSERT INTO `item_apply` VALUES (1,2,'中秋曲奇饼干',69.00,'','/static/images/60cc4b5f71d44485b8a966e8f5ea9184.jpg','pending',NULL,NULL,NULL,'2026-09-14 14:57:46');
/*!40000 ALTER TABLE `item_apply` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `message`
--

DROP TABLE IF EXISTS `message`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `message` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '消息ID',
  `user_id` bigint NOT NULL COMMENT '接收人ID（申请提交人或好友）',
  `apply_id` bigint NOT NULL COMMENT '关联申请ID',
  `content` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '消息内容',
  `is_read` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否已读：0未读 1已读',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间',
  PRIMARY KEY (`id`),
  KEY `idx_msg_user_read` (`user_id`,`is_read`),
  KEY `fk_msg_apply` (`apply_id`),
  CONSTRAINT `fk_msg_apply` FOREIGN KEY (`apply_id`) REFERENCES `item_apply` (`id`),
  CONSTRAINT `fk_msg_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息通知表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `message`
--

LOCK TABLES `message` WRITE;
/*!40000 ALTER TABLE `message` DISABLE KEYS */;
INSERT INTO `message` VALUES (1,2,1,'您提交的物品申请「中秋曲奇饼干」已通过，审批人：xxx，审批理由：看起来颜值很高',0,'2026-09-14 15:00:09'),(2,2,1,'您提交的物品申请「中秋曲奇饼干」已通过，审批人：下小雨，审批理由：看起来好好吃',0,'2026-09-14 15:01:16');
/*!40000 ALTER TABLE `message` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user`
--

DROP TABLE IF EXISTS `user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录账号（唯一）',
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'bcrypt加密后的密码',
  `uid` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '好友ID（自动生成，可修改，唯一）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_username` (`username`),
  UNIQUE KEY `uk_user_uid` (`uid`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user`
--

LOCK TABLES `user` WRITE;
/*!40000 ALTER TABLE `user` DISABLE KEYS */;
INSERT INTO `user` VALUES (1,'xxx','$2b$12$XkMQVO8VPwUWKmvJaLbTM.xLhHLA9VCm/ZThZ2eNHilejIalRYog2','6UDNI72C','2026-09-14 14:46:14'),(2,'小小夏','$2b$12$JjdTx40or5NQGNqHIbM36ucsF.nmE/1S3UTsnvLCl4XJ63W10hfG6','EIE3IGJW','2026-09-14 14:55:00'),(3,'下小雨','$2b$12$Kp3hJfH6d.ZIVf8VgvhRSedg1Z6mEPwad52itU4duV3aH9Li76Qq6','87N38NC6','2026-09-14 15:00:57'),(4,'111','$2b$12$kL3BYMBkxr3YEmMZ.RGrGuj6Fum9BnrQfuEbUdkjVB1cKZGdnHdRq','1Q9G92SY','2026-09-14 15:04:27'),(5,'春日诗','$2b$12$/GpXpKBvztG4DIbUjeNNy.4Sq9xfpDmpwijuIpHfPOfj07WzoPWB6','OKIEGE47','2026-09-14 15:08:27');
/*!40000 ALTER TABLE `user` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-09-14 15:22:04
