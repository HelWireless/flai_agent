-- 异世界数据库表创建脚本
-- 用于测试环境和生产环境建表
-- 创建时间: 2026-02-01

-- =====================================================
-- 1. 异世界会话/存档表
-- =====================================================
CREATE TABLE `t_freak_world_session` (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='异世界会话/存档表';


-- =====================================================
-- 2. 异世界对话历史表 (现有表，新增 is_save_point 字段)
-- =====================================================
CREATE TABLE `t_freak_world_dialogue` (
  `id` int(32) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `account_id` int(32) NOT NULL COMMENT '用户id',
  `freak_world_id` int(16) NOT NULL COMMENT '异世界id',
  `session_id` int(16) NOT NULL COMMENT '对话id',
  `message` text CHARACTER SET utf8mb4 COMMENT '发送内容',
  `response` text CHARACTER SET utf8mb4 COMMENT '返回内容',
  `step` int(4) unsigned DEFAULT NULL COMMENT '初始加载步骤',
  `is_save_point` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否为存档点: 0=否, 1=是',
  `ext_param1` text CHARACTER SET utf8mb4 COMMENT '扩展参数1',
  `ext_param2` text COMMENT '扩展参数2',
  `ext_param3` text COMMENT '扩展参数3',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `del` bit(1) NOT NULL DEFAULT b'0' COMMENT '是否删除',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 ROW_FORMAT=DYNAMIC COMMENT='异世界对话表';


-- =====================================================
-- 3. Prompt 配置统一表 (GM/第三方人物/世界)
-- =====================================================
CREATE TABLE `t_prompt_config` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `config_id` VARCHAR(64) NOT NULL COMMENT '配置ID (如 gm_01, c1s1c1_0001, world_01)',
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
