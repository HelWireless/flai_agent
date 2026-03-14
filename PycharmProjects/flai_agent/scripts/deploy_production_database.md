# 🛠️ 生产环境数据库部署指南

## 📋 概述
本指南用于在`pillow_customer_prod`生产数据库中部署Flai Agent系统所需的数据表。

## 🗂️ 部署文件
- `create_coc_tables.sql` - COC跑团系统表
- `create_instance_world_tables.sql` - 副本世界系统表  
- `optimize_database_indexes.sql` - 性能优化索引
- `add_dialogue_summary_field.py` - 对话总结字段迁移
- `migrate_prompt_configs.py` - Prompt配置数据迁移

## 📋 部署前准备

### 1. 数据库连接信息确认
```yaml
host: "81.68.235.167"
username: "pillow"
password: "1234QWERasdf!@#"
database_name: "pillow_customer_prod"  # 生产环境
```

### 2. 检查现有数据
```sql
-- 检查生产库是否已存在相关表
SELECT 
    TABLE_NAME, 
    TABLE_ROWS,
    CREATE_TIME
FROM information_schema.tables 
WHERE table_schema = 'pillow_customer_prod'
AND table_name LIKE '%coc%' 
   OR table_name LIKE '%freak%' 
   OR table_name LIKE '%prompt%';
```

## 🔄 部署步骤

### 步骤1：备份现有数据（重要！）
```bash
# 备份整个生产库
mysqldump -u pillow -p pillow_customer_prod > backup_pillow_customer_prod_$(date +%Y%m%d).sql

# 如果有重要的对话历史数据，单独备份
mysqldump -u pillow -p pillow_customer_prod t_freak_world_dialogue > backup_dialogues_$(date +%Y%m%d).sql
```

### 步骤2：创建新表结构
```bash
# 切换到生产数据库
mysql -u pillow -p pillow_customer_prod

# 执行建表脚本
source scripts/create_coc_tables.sql;
source scripts/create_instance_world_tables.sql;
```

### 步骤3：运行数据迁移
```bash
# 添加对话总结字段
python scripts/add_dialogue_summary_field.py

# 迁移Prompt配置
python scripts/migrate_prompt_configs.py
```

### 步骤4：性能优化
```bash
# 添加优化索引
mysql -u pillow -p pillow_customer_prod

source scripts/optimize_database_indexes.sql;
```

### 步骤5：验证部署
```sql
-- 检查所有表是否创建成功
SHOW TABLES IN pillow_customer_prod;

-- 检查关键表结构
DESCRIBE t_coc_game_state;
DESCRIBE t_freak_world_game_state;
DESCRIBE t_prompt_config;

-- 检查索引
SHOW INDEX FROM t_coc_game_state;
SHOW INDEX FROM t_freak_world_dialogue;
```

## 📊 数据验证

### 1. 表结构验证
```sql
-- 检查COC游戏状态表
SELECT COUNT(*) FROM t_coc_game_state;

-- 检查副本世界游戏状态表  
SELECT COUNT(*) FROM t_freak_world_game_state;

-- 检查Prompt配置表
SELECT COUNT(*) FROM t_prompt_config;
```

### 2. 索引验证
```sql
-- 验证复合索引是否创建成功
SHOW INDEX FROM t_freak_world_dialogue WHERE Key_name LIKE 'idx_%';
SHOW INDEX FROM t_coc_game_state WHERE Key_name LIKE 'idx_%';
```

### 3. 数据完整性验证
```sql
-- 检查COC表必要字段
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_COMMENT 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'pillow_customer_prod' 
  AND TABLE_NAME = 't_coc_game_state'
ORDER BY ORDINAL_POSITION;

-- 检查对话总结字段是否添加
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'pillow_customer_prod' 
  AND TABLE_NAME IN ('t_coc_game_state', 't_freak_world_game_state')
  AND COLUMN_NAME = 'dialogue_summary';
```

## ⚠️ 注意事项

### 1. 权限要求
```bash
GRANT ALL PRIVILEGES ON pillow_customer_prod.* TO 'pillow'@'%';
FLUSH PRIVILEGES;
```

### 2. 性能考虑
- 在低峰时段执行部署
- 大表操作可能需要较长时间
- 监控MySQL连接数和负载

### 3. 回滚计划
```sql
-- 如果出现问题，可以删除新建的表
DROP TABLE IF EXISTS t_coc_save_slot;
DROP TABLE IF EXISTS t_coc_game_state;
DROP TABLE IF EXISTS t_freak_world_game_state;
DROP TABLE IF EXISTS t_prompt_config;
```

## 🔍 生产环境监控

### 1. 慢查询监控
```sql
-- 检查是否有慢查询
SELECT 
    query_time,
    rows_examined,
    rows_sent,
    db,
    sql_text
FROM mysql.slow_log
WHERE db = 'pillow_customer_prod'
ORDER BY start_time DESC
LIMIT 10;
```

### 2. 表大小监控
```sql
SELECT 
    table_name,
    table_rows,
    ROUND(data_length/1024/1024, 2) as data_size_mb,
    ROUND(index_length/1024/1024, 2) as index_size_mb
FROM information_schema.tables 
WHERE table_schema = 'pillow_customer_prod'
ORDER BY data_length DESC;
```

## ✅ 完成检查清单

- [ ] ✅ 数据库连接信息确认
- [ ] ✅ 现有数据备份完成
- [ ] ✅ 新表结构创建成功
- [ ] ✅ 数据迁移脚本执行完成
- [ ] ✅ 索引优化完成
- [ ] ✅ 表结构和数据验证通过
- [ ] ✅ 权限设置正确
- [ ] ✅ 监控系统配置完成

## 📞 支持信息

如遇部署问题，请检查：
1. 数据库连接权限
2. 现有数据冲突
3. MySQL版本兼容性（推荐5.7+）
4. 磁盘空间是否充足