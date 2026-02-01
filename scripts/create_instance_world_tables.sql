-- 副本世界数据库表创建脚本
-- 数据库: pillow_customer_test
-- 创建时间: 2026-02-01

-- =====================================================
-- 1. 副本世界会话/存档表
-- =====================================================
CREATE TABLE `t_instance_world_session` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `session_id` VARCHAR(64) NOT NULL COMMENT '会话ID',
  `user_id` VARCHAR(64) NOT NULL COMMENT '用户ID (对应 account_id)',
  `world_id` VARCHAR(32) NOT NULL COMMENT '世界ID',
  `gm_id` VARCHAR(16) NOT NULL COMMENT '引导者ID',
  `game_phase` VARCHAR(32) NOT NULL DEFAULT 'gm_intro' COMMENT '游戏阶段: gm_intro/world_intro/character_select/playing/ended',
  `game_state` VARCHAR(16) NOT NULL DEFAULT 'playing' COMMENT '游戏状态: playing/ended/death',
  `gender_preference` VARCHAR(8) DEFAULT NULL COMMENT '原住民性别偏好: male/female',
  `current_character_id` VARCHAR(64) DEFAULT NULL COMMENT '当前交谈角色ID',
  `random_seed` BIGINT DEFAULT NULL COMMENT '随机种子',
  `characters` JSON DEFAULT NULL COMMENT '已生成的角色列表JSON',
  `status` TINYINT NOT NULL DEFAULT 1 COMMENT '会话状态: 1=活跃, 0=已结束',
  
  -- 存档相关字段
  `save_id` VARCHAR(64) DEFAULT NULL COMMENT '存档ID（存档后生成）',
  `save_data` JSON DEFAULT NULL COMMENT '存档内容JSON',
  `saved_at` DATETIME DEFAULT NULL COMMENT '存档时间',
  
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_save_id` (`save_id`),
  KEY `idx_world_id` (`world_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='副本世界会话/存档表';


-- =====================================================
-- 2. 副本世界对话历史表
-- =====================================================
CREATE TABLE `t_instance_world_dialogue` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `session_id` VARCHAR(64) NOT NULL COMMENT '会话ID',
  `user_id` VARCHAR(64) NOT NULL COMMENT '用户ID (对应 account_id)',
  `world_id` VARCHAR(32) NOT NULL COMMENT '世界ID',
  `role` VARCHAR(16) NOT NULL COMMENT '角色: user/assistant/system',
  `content` TEXT NOT NULL COMMENT '消息内容',
  `type` TINYINT NOT NULL DEFAULT 1 COMMENT '消息类型: 1=普通文字, 2=语音转文字, 3=系统消息',
  `is_save_point` TINYINT NOT NULL DEFAULT 0 COMMENT '是否为存档点: 0=否, 1=是',
  `is_deleted` TINYINT NOT NULL DEFAULT 0 COMMENT '是否已删除: 0=否, 1=是',
  `metadata` JSON DEFAULT NULL COMMENT '额外元数据JSON',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  PRIMARY KEY (`id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_world_id` (`world_id`),
  KEY `idx_is_deleted` (`is_deleted`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_session_created` (`session_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='副本世界对话历史表';


-- =====================================================
-- 3. Prompt 配置统一表 (GM/第三方人物/世界)
-- =====================================================
CREATE TABLE `t_prompt_config` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `config_id` VARCHAR(64) NOT NULL COMMENT '配置ID (如 gm_01, char_c1s1c1_0001, world_01)',
  `type` VARCHAR(16) NOT NULL COMMENT '类型: gm/character/world',
  `name` VARCHAR(128) NOT NULL COMMENT '名称',
  `gender` VARCHAR(8) DEFAULT NULL COMMENT '性别 (GM/人物适用)',
  `traits` VARCHAR(1024) DEFAULT NULL COMMENT '特质描述',
  `prompt` MEDIUMTEXT COMMENT '主 prompt 内容',
  `config` JSON COMMENT '类型特有配置 JSON',
  `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1=启用, 0=禁用',
  `sort_order` INT DEFAULT 0 COMMENT '排序权重',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_config_id` (`config_id`),
  KEY `idx_type` (`type`),
  KEY `idx_status` (`status`),
  KEY `idx_type_status` (`type`, `status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Prompt配置统一表(GM/人物/世界)';
