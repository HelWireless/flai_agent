-- 克苏鲁跑团(COC)数据库表创建脚本
-- 用于测试环境和生产环境建表
-- 创建时间: 2026-02-01

-- =====================================================
-- 1. 克苏鲁跑团游戏状态表
-- =====================================================
CREATE TABLE `t_coc_game_state` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `account_id` INT UNSIGNED NOT NULL COMMENT '用户id',
  `session_id` CHAR(16) NOT NULL COMMENT '会话id',
  
  -- GM相关
  `gm_id` VARCHAR(16) DEFAULT NULL COMMENT 'GM ID',
  `gm_gender` VARCHAR(8) DEFAULT NULL COMMENT 'GM性别偏好: male/female',
  
  -- 游戏状态
  `game_status` VARCHAR(32) NOT NULL DEFAULT 'gm_select' 
    COMMENT '游戏状态: gm_select/step1_attributes/step2_secondary/step3_profession/step4_background/step5_summary/playing/ended',
  
  -- 调查员人物卡
  `investigator_card` JSON DEFAULT NULL COMMENT '调查员人物卡JSON',
  
  -- 游戏进度
  `round_number` INT NOT NULL DEFAULT 1 COMMENT '回合数(天数)',
  `turn_number` INT NOT NULL DEFAULT 0 COMMENT '对话/行动轮数',
  `save_count` INT NOT NULL DEFAULT 0 COMMENT '存档计数',
  
  -- 临时数据
  `temp_data` JSON DEFAULT NULL COMMENT '临时数据JSON(步骤间传递)',
  
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `del` BIT(1) NOT NULL DEFAULT b'0' COMMENT '是否删除',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`),
  KEY `idx_account_id` (`account_id`),
  KEY `idx_game_status` (`game_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='克苏鲁跑团游戏状态表';


-- =====================================================
-- 2. 克苏鲁跑团存档槽表（一个 session 可有多个存档）
-- =====================================================
CREATE TABLE `t_coc_save_slot` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `save_id` VARCHAR(32) NOT NULL COMMENT '存档ID',
  `session_id` CHAR(16) NOT NULL COMMENT '关联会话ID',
  `account_id` INT UNSIGNED NOT NULL COMMENT '用户ID',
  `gm_id` VARCHAR(16) DEFAULT NULL COMMENT 'GM ID',
  `game_status` VARCHAR(32) NOT NULL COMMENT '存档时的游戏状态',
  `investigator_card` JSON DEFAULT NULL COMMENT '人物卡快照',
  `round_number` INT NOT NULL DEFAULT 1 COMMENT '回合数',
  `turn_number` INT NOT NULL DEFAULT 0 COMMENT '轮数',
  `temp_data` JSON DEFAULT NULL COMMENT 'GM信息等临时数据',
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `del` BIT(1) NOT NULL DEFAULT b'0' COMMENT '是否删除',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_save_id` (`save_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_account_id` (`account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='克苏鲁跑团存档槽表';


-- =====================================================
-- 说明：
-- - 对话历史复用 t_freak_world_dialogue 表
-- - GM配置复用 t_prompt_config 表 (type='coc_gm')
-- =====================================================

-- 调查员人物卡JSON结构示例:
-- {
--   "name": "林骁",
--   "gender": "男",
--   "age": 34,
--   "profession": "警探",
--   "professionSkills": ["射击", "法律", "心理学", ...],
--   "interestSkills": ["图书馆使用", "历史", ...],
--   "primaryAttributes": {
--     "STR": 50, "CON": 40, "DEX": 60, "SIZ": 80,
--     "INT": 70, "POW": 50, "APP": 50, "EDU": 60
--   },
--   "secondaryAttributes": {
--     "HP": 12, "MP": 10, "SAN": 50, "LUCK": 60,
--     "DB": 0, "Build": 130, "MOV": 8
--   },
--   "skills": {
--     "射击": 60, "法律": 60, "心理学": 50, "侦查": 70, ...
--   },
--   "equipment": ["史密斯M10左轮", "伸缩警棍", ...],
--   "background": "出生于上海闸北区..."
-- }
