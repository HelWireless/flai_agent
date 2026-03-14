-- =====================================================
-- 数据库性能优化脚本
-- 针对高频率查询添加优化索引
-- 创建时间: 2026-02-13
-- =====================================================

-- ==================== 1. 对话历史表优化 ====================
-- 对话历史表通常面临以下查询模式：
-- 1. 按 session_id + del 状态查询特定会话
-- 2. 按 account_id + session_id 查询用户对话
-- 3. 按时间范围查询
-- 4. 分页查询优化

-- 添加复合索引优化最常用的查询
ALTER TABLE `t_freak_world_dialogue` 
ADD INDEX `idx_session_del_time` (`session_id`, `del`, `create_time`),
ADD INDEX `idx_account_session` (`account_id`, `session_id`),
ADD INDEX `idx_create_time_del` (`create_time`, `del`);

-- ==================== 2. COC游戏状态表优化 ====================
-- 游戏状态表查询模式：
-- 1. 按 user_id + session_id 查询用户会话
-- 2. 按 game_status 查询特定状态的游戏
-- 3. 按 create_time 排序查看最近活动

ALTER TABLE `t_coc_game_state` 
ADD INDEX `idx_user_status_time` (`user_id`, `game_status`, `update_time`),
ADD INDEX `idx_status_update_time` (`game_status`, `update_time`),
ADD INDEX `idx_user_update_time` (`user_id`, `update_time`);

-- ==================== 3. 副本世界游戏状态表优化 ====================
ALTER TABLE `t_freak_world_game_state` 
ADD INDEX `idx_user_status_time` (`user_id`, `game_status`, `update_time`),
ADD INDEX `idx_world_user_time` (`freak_world_id`, `user_id`, `create_time`);

-- ==================== 4. 存档表优化 ====================
-- 存档查询模式：
-- 1. 按 session_id 查询某个会话的所有存档
-- 2. 按 user_id 查询用户的所有存档
-- 3. 按 save_id 查询特定存档

ALTER TABLE `t_coc_save_slot`
ADD INDEX `idx_session_id_del` (`session_id`, `del`),
ADD INDEX `idx_user_id_del` (`user_id`, `del`);

-- ==================== 5. Prompt配置表优化 ====================
ALTER TABLE `t_prompt_config`
ADD INDEX `idx_type_status_order` (`type`, `status`, `sort_order`),
ADD INDEX `idx_status_updated` (`status`, `updated_at`);

-- ==================== 6. 查询分析和统计 ====================

-- 查看表索引使用情况
SHOW INDEX FROM `t_freak_world_dialogue`;
SHOW INDEX FROM `t_coc_game_state`;
SHOW INDEX FROM `t_freak_world_game_state`;
SHOW INDEX FROM `t_coc_save_slot`;
SHOW INDEX FROM `t_prompt_config`;

-- 查看索引大小
SELECT 
    TABLE_NAME,
    INDEX_NAME,
    ROUND(STAT_VALUE * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE index_name IS NOT NULL
AND STAT_VALUE > 0
ORDER BY size_mb DESC;

-- ==================== 7. 表结构优化建议 ====================

-- 1. 对话历史表分区（如果数据量很大）
-- 建议按时间分区或按account_id哈希分区

-- 2. 考虑添加覆盖索引减少回表
-- ALTER TABLE `t_freak_world_dialogue` 
-- ADD INDEX `idx_covering_session` (`session_id`, `del`, `id`, `message`, `text`);

-- 3. 定期清理已删除的数据
-- 添加定时任务清理 del=1 的数据

-- ==================== 8. 慢查询日志配置 ====================

-- 启用慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1; -- 记录超过1秒的查询
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow-query.log';

-- 记录没有使用索引的查询
SET GLOBAL log_queries_not_using_indexes = 'ON';

-- ==================== 9. 常见性能问题SQL模板 ====================

-- 查询最慢的对话历史查询
-- EXPLAIN 
SELECT fwd.* 
FROM t_freak_world_dialogue fwd
WHERE fwd.session_id = '特定session_id'
  AND fwd.del = 0
ORDER BY fwd.id ASC;

-- 查询COC会话状态的执行计划
-- EXPLAIN 
SELECT cgs.*
FROM t_coc_game_state cgs
WHERE cgs.user_id = 12345
  AND cgs.game_status = 'playing'
ORDER BY cgs.update_time DESC;

-- ==================== 10. 性能监控建议 ====================

-- 定期运行ANALYZE TABLE更新统计信息
-- ANALYZE TABLE t_freak_world_dialogue, t_coc_game_state, t_freak_world_game_state;

-- 监控表大小增长
SELECT 
    table_name,
    table_rows,
    ROUND(data_length/1024/1024, 2) as data_size_mb,
    ROUND(index_length/1024/1024, 2) as index_size_mb
FROM information_schema.tables 
WHERE table_schema = DATABASE()
ORDER BY data_length DESC;

-- ==================== 11. 数据归档策略 ====================

-- 对话历史归档(超过6个月的已删除数据)
-- CREATE EVENT archive_old_dialogues
-- ON SCHEDULE EVERY 1 MONTH
-- DO
-- BEGIN
--   DELETE FROM t_freak_world_dialogue 
--   WHERE del = 1 
--     AND create_time < DATE_SUB(NOW(), INTERVAL 6 MONTH);
-- END;

-- ==================== 12. 查询优化建议 ====================

-- 避免SELECT *，只选择需要的字段
-- 使用LIMIT限制结果集大小
-- 避免在WHERE条件中对字段进行函数操作
-- 合理使用JOIN，避免笛卡尔积

-- 示例优化查询：
-- 原查询可能：
-- SELECT * FROM t_freak_world_dialogue WHERE session_id = '123';

-- 优化后：
-- SELECT id, account_id, session_id, message, text, create_time 
-- FROM t_freak_world_dialogue 
-- WHERE session_id = '123' AND del = 0
-- ORDER BY id ASC
-- LIMIT 100;