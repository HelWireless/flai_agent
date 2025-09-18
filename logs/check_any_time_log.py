#!/bin/bash

# 日志提取工具
# 用法：./log_extractor.sh [起始时间] [结束时间] [日志文件] (输出文件)
# 时间格式：YYYY-MM-DD HH:MM 或 YYYY-MM-DD HH:MM:SS

if [ $# -lt 3 ]; then
    echo "用法: $0 <起始时间> <结束时间> <日志文件> [输出文件]"
    echo "示例: $0 '2025-06-20 11:00' '2025-06-20 11:05' access.log output.txt"
    exit 1
fi

START_TIME="$1"
END_TIME="$2"
LOG_FILE="$3"
OUTPUT_FILE="${4:-extracted_logs_$(date +%s).txt}"

# 验证日志文件是否存在
if [ ! -f "$LOG_FILE" ]; then
    echo "错误: 日志文件 $LOG_FILE 不存在!"
    exit 1
fi

# 时间格式处理函数
normalize_time() {
    local time_str="$1"
    # 自动补全秒和毫秒部分
    if [[ $time_str =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}$ ]]; then
        echo "${time_str}:00.000"
    elif [[ $time_str =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
        echo "${time_str}.000"
    elif [[ $time_str =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}$ ]]; then
        echo "$time_str"
    else
        echo "错误: 无效的时间格式 '$time_str'"
        echo "请使用格式: YYYY-MM-DD HH:MM 或 YYYY-MM-DD HH:MM:SS"
        exit 1
    fi
}

# 标准化时间格式
NORM_START=$(normalize_time "$START_TIME")
NORM_END=$(normalize_time "$END_TIME")

# 提取日志
echo "正在提取日志: $START_TIME 到 $END_TIME ..."
awk -v start="$NORM_START" -v end="$NORM_END" '
{
    # 提取日志中的时间戳（第2列日期 + 第3列时间）
    log_ts = $2 " " $3
    
    # 比较时间戳
    if (log_ts >= start && log_ts <= end) {
        print $0
    }
}' "$LOG_FILE" > "$OUTPUT_FILE"

# 结果统计
LINE_COUNT=$(wc -l < "$OUTPUT_FILE")
FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)

echo "=============================================="
echo "日志提取完成!"
echo "输出文件: $OUTPUT_FILE"
echo "匹配行数: $LINE_COUNT"
echo "文件大小: $FILE_SIZE"
echo "时间范围: $NORM_START 至 $NORM_END"
echo "=============================================="
#bash 这个脚本.sh  "2025-06-20 11:00" "2025-06-20 11:05" accessee.log output.txt
