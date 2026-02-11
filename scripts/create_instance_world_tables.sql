-- 异世界数据库表创建脚本
-- 用于测试环境和生产环境建表
-- 创建时间: 2026-02-01

-- =====================================================
-- 1. 异世界游戏状态表 (我们新增，存储游戏进度)
-- =====================================================
CREATE TABLE `t_freak_world_game_state` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键',
  `freak_world_id` int(11) unsigned NOT NULL COMMENT '异世界id',
  `user_id` int(32) unsigned NOT NULL COMMENT '用户id',
  `session_id` char(16) NOT NULL COMMENT '会话id',
  
  -- 游戏状态字段
  `gm_id` varchar(16) NOT NULL DEFAULT '01' COMMENT '引导者ID',
  `game_status` varchar(32) NOT NULL DEFAULT 'gm_intro' COMMENT '游戏状态: gm_intro/world_intro/character_select/playing/ended/death',
  `gender_preference` varchar(8) DEFAULT NULL COMMENT '原住民性别偏好: male/female',
  `current_character_id` varchar(64) DEFAULT NULL COMMENT '当前交谈角色ID',
  `random_seed` bigint DEFAULT NULL COMMENT '随机种子',
  `characters` json DEFAULT NULL COMMENT '已生成的角色列表JSON',
  
  -- 对话历史总结
  `dialogue_summary` TEXT DEFAULT NULL COMMENT '对话历史总结(滚动更新)',
  
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `del` bit(1) NOT NULL DEFAULT b'0' COMMENT '是否删除',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_freak_world_id` (`freak_world_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='异世界游戏状态表';

-- 说明：
-- - t_freak_world_dialogue: 现有对话表，Java 写入，Python 只读
-- - t_freak_world_save_slot: 现有存档槽表，Java 管理存档ID与对话ID的关联
-- - t_freak_world_game_state: 我们新增，存储游戏进度状态


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
