-- =====================================================
-- 生产环境数据库部署执行脚本
-- 目标数据库: pillow_customer_prod
-- 执行顺序: 
-- 1. 创建基础表结构
-- 2. 性能优化索引
-- 3. 数据验证
-- =====================================================

-- ========================= 注意事项 =========================
-- ⚠️  生产环境执行前务必：
-- 1. 备份所有数据
-- 2. 确认无业务流量或安排在维护窗口
-- 3. 准备回滚方案
-- 4. 监控执行过程中的数据库性能

-- =====================================================
-- 步骤1: 创建COC跑团系统表结构
-- =====================================================

-- 1.1 COC游戏状态表
CREATE TABLE IF NOT EXISTS `t_coc_game_state` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `user_id` INT UNSIGNED NOT NULL COMMENT '用户id',
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
  
  -- 对话历史总结
  `dialogue_summary` TEXT DEFAULT NULL COMMENT '对话历史总结(滚动更新)',
  
  `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `del` BIT(1) NOT NULL DEFAULT b'0' COMMENT '是否删除',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_session_id` (`session_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_game_status` (`game_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='克苏鲁跑团游戏状态表';

-- 1.2 COC存档表
CREATE TABLE IF NOT EXISTS `t_coc_save_slot` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `save_id` VARCHAR(32) NOT NULL COMMENT '存档ID',
  `session_id` CHAR(16) NOT NULL COMMENT '关联会话ID',
  `user_id` INT UNSIGNED NOT NULL COMMENT '用户ID',
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
  KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='克苏鲁跑团存档槽表';

-- =====================================================
-- 步骤2: 创建副本世界系统表结构
-- =====================================================

-- 2.1 副本世界游戏状态表
CREATE TABLE IF NOT EXISTS `t_freak_world_game_state` (
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

-- 2.2 Prompt配置统一表（如果不存在）
CREATE TABLE IF NOT EXISTS `t_prompt_config` (
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

-- =====================================================
-- 步骤3: 数据库性能优化索引
-- （仅添加不存在的索引）
-- =====================================================

-- 3.1 为现有对话表添加优化索引（如果不存在）
-- 注意：这里假设 t_freak_world_dialogue 表已经存在

-- 检查并添加索引（使用单独的SQL文件更好管理）
-- 这里只是示例，实际执行时应使用 optimize_database_indexes.sql

-- =====================================================
-- 步骤4: 数据验证查询
-- =====================================================

SELECT '=== 表创建验证 ===' as check_type;

-- 检查所有必需的表
SELECT 
    TABLE_NAME,
    TABLE_ROWS,
    CREATE_TIME,
    UPDATE_TIME
FROM information_schema.tables 
WHERE table_schema = 'pillow_customer_prod'
AND table_name IN (
    't_coc_game_state',
    't_coc_save_slot', 
    't_freak_world_game_state',
    't_prompt_config'
);

-- 检查关键表的结构
SELECT '=== COC游戏状态表结构 ===' as check_type;
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'pillow_customer_prod' 
  AND TABLE_NAME = 't_coc_game_state'
ORDER BY ORDINAL_POSITION;

SELECT '=== 副本世界游戏状态表结构 ===' as check_type;
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'pillow_customer_prod' 
  AND TABLE_NAME = 't_freak_world_game_state'
ORDER BY ORDINAL_POSITION;

-- =====================================================
-- 步骤5: 部署完成验证
-- =====================================================

SELECT '=== 部署状态总结 ===' as result;
SET @total_tables = 0;
SET @success_tables = 0;

-- 统计表创建状态
SELECT COUNT(*) INTO @total_tables FROM (
    SELECT TABLE_NAME FROM information_schema.tables 
    WHERE table_schema = 'pillow_customer_prod'
    AND table_name IN ('t_coc_game_state', 't_coc_save_slot', 't_freak_world_game_state', 't_prompt_config')
) as existing_tables;

SELECT COUNT(*) INTO @required_tables FROM (
    SELECT 't_coc_game_state' as table_name UNION ALL
    SELECT 't_coc_save_slot' UNION ALL  
    SELECT 't_freak_world_game_state' UNION ALL
    SELECT 't_prompt_config'
) as required_tables;

SELECT 
    '数据库部署验证' as title,
    @success_tables as created_tables,
    @required_tables as required_tables,
    IF(@success_tables = @required_tables, '✅ 成功', '❌ 失败') as status,
    NOW() as check_time;

-- =====================================================
-- 执行建议
-- =====================================================

/*
📋 生产环境部署建议:

1. 分步执行，不要一次性运行整个脚本

2. 建议执行命令:
   mysql -u pillow -p pillow_customer_prod < deploy_to_production.sql

3. 按步骤验证:
   - 步骤1创建后，验证表结构
   - 步骤2执行后，验证数据
   - 步骤3执行后，验证索引

4. 回滚准备:
   - 如果表创建有问题，使用 DROP TABLE 语句
   - 如果有数据冲突，检查现有数据

5. 监控指标:
   - 表空间使用情况
   - 索引大小
   - 查询性能
*/

-- =====================================================
-- 结束
-- =====================================================