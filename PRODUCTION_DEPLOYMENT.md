# Flai Agent Production Deployment Guide

## Prerequisites

### Database Setup
1. 必须已在 MySQL 数据库服务器 (81.68.235.167) 创建生产数据库：
   - `pillow_customer_prod`
   - 确保用户 `pillow` 有对 `pillow_customer_prod` 的全部权限
2. 数据库表结构使用已提供的 SQL 脚本自动创建

### Server Requirements
- Python 3.11+
- Windows 10/11 或 Linux 64-bit
- 4GB+ RAM
- 8GB+ 磁盘空间（用于日志和模型缓存）

## FastAPI Configuration

### 配置路径
生产配置文件: `flai_agent/config/config.yaml`

### 关键配置项
```
database_name: "pillow_customer_prod"
debug_mode: false
log_level: INFO
vectors_collection_name: "pillow_prod"
```

## Startup Process

### 方法 1: Direct Start
```cmd
cd c:\Users\cody\PycharmProjects\flai_agent
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 方法 2: Batch Script (Recommended)
使用 `startup_production.bat`:
- 双击运行，或直接执行脚本

## Database Verification

### 验证所有核心表已创建:
```sql
USE pillow_customer_prod;
SHOW TABLES;
-- Should show 3 tables:
-- t_coc_game_state
-- t_freak_world_game_state
-- t_prompt_config
```

### 检查所有表的结构和索引优化:
Run `scripts/optimize_database_indexes.sql`

## Health Monitoring

### Check API Health
```cmd
curl http://localhost:8000/health
```
响应格式: JSON with status indicators

### Log Monitoring
- Location: `logs/app.log`
- Log format: `<time> | <level> | <module> - <message>`
- Monitor for ERROR level messages and performance warnings

### Performance Monitoring
The following metrics are automatically collected:
- Request response times
- Conversation metrics (turns, token usage)
- Error rates
- Database query performance
- Memory usage trends

## LLM API Keys
Ensure all API keys are valid:
- Qwen API (all models): Key in config.yaml
- Embedding API: For vector database operations
- Speech API: For voice synthesis features

## Service Ports
- Main API: 8000 (TCP)
- Vector DB: 6333 (TCP) - if enabled

## Backup and Recovery

### Backup Strategy
1. 每日备份数据库:
   ```cmd
   mysqldump -u pillow -p1234QWERasdf!@#$ pillow_customer_prod > backup_$(date +%F).sql
   ```

2. 配置文件保存版本

3. 日志按 `retention: "60 days"` 策略自动轮转

### Recovery Process
1. 停止服务
2. 执行数据库恢复 SQL
3. 验证数据完整性
4. 重启服务

## Troubleshooting

### Startup Failure
- 检查端口 8000 是否已被占用
- 检查所有 API keys 是否正确
- 使用 netstat 确认数据库连接

### 数据库连接问题
- 验证防火墙设置
- 确认主机名/IP 正确 (81.68.235.167)
- 检查数据库连接字符串格式

### 向量数据库问题
- 确认向量数据库服务正在运行 (端口 6333)
- 校验 collection_name: `pillow_prod`
- 验证码认证 (如果启用)

### Performance Issues
- 查看日志中的慢查询警告
- 调整 workers 数量 (更多是 CPU 密集型)
- 检查内存使用情况
- 考虑启用 Redis 缓存 (未来升级)

### Specific LLM Errors
- 429 错误: 增加 API 调用间隔或升级账户
- 500 错误: 检查模型端点 URL
- 返回格式错误: 验证请求格式

## Monitoring and Alerts

### Recommended Monitoring Setup
- Prometheus endpoint: `/metrics`
- 告警条件:
  - 错误率 > 5%/5min
  - 平均响应时间 > 5s
  - 数据库连接失败

### Nightly Log Report Script
```python
import logging

def send_nightly_report():
    total_requests = get_total_requests()
    error_count = get_error_count()
    avg_response_time = get_avg_response_time()
    # Send daily report via webhook or email
```

## Reload Configuration
To reload configuration without restarting the service:
```cmd
curl -X POST http://localhost:8000/reload-config
```
(Note: Only non-database changes will be effective)

## SSL Setup (Production Recommendation)
Use Nginx or Apache as reverse proxy with SSL certificates. Example Nginx:
```
location / {
    proxy_pass http://localhost:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Scaling Guide

### Single Server (1-1000 daily users)
- Workers: CPU core count (typically 4-8)
- No additional changes needed

### Multi-Server (1000+ daily users)
1. 使用负载均衡器分发流量
2. 所有实例共享 central pillow_customer_prod 数据库
3. 每个实例配置自己的向量数据库分区（可选）
4. 自动 failover 注意事项

## Maintenance Tasks

### Weekly
- 清理旧的对话记录（避免无限增长）
- 优化数据库表（OPTIMIZE TABLE）
- 备份配置文件和数据库

### Monthly
- Review and rotate API keys
- Update model parameters
- Archive old logs (older than 60 days automatically handled)
- 检查数据库索引性能

This guide provides a comprehensive overview for deploying and managing Flai Agent in a production environment. Refer to the specific sections above based on your use case and requirements.
