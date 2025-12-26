"""
测试脚本：查询用户对话历史
用法：python scripts/check_dialogue_history.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib
from sqlalchemy import create_engine, text
from datetime import datetime

# 配置
USER_ID = "1000028"
LIMIT = 50

def get_engine():
    """创建数据库引擎 - 测试环境"""
    host = "81.68.235.167"
    username = "pillow"
    password = "1234QWERasdf!@#$"
    database_name = "pillow_customer_test"
    
    encoded_password = urllib.parse.quote(password)
    DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
    return create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)

def test_dialogue_query_logic():
    """测试 _process_query_results 的逻辑"""
    print("\n【模拟 _process_query_results 逻辑】")
    
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT message, text, create_time
                FROM t_dialogue
                WHERE account_id = :user_id
                AND create_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)
                AND type in (1, 2)
                ORDER BY create_time DESC
                LIMIT 20
            """),
            {"user_id": USER_ID}
        )
        query_results = result.fetchall()
    
    print(f"  查询返回 {len(query_results)} 条记录")
    
    # 模拟 _process_query_results 逻辑
    temp_dict = {}
    for query_result in query_results:
        user_msg, assistant_msg, timestamp = query_result
        if timestamp not in temp_dict:
            temp_dict[timestamp] = {"user": "", "assistant": ""}
        if user_msg:
            temp_dict[timestamp]["user"] = user_msg
        if assistant_msg:
            if temp_dict[timestamp]["assistant"]:
                temp_dict[timestamp]["assistant"] += " " + assistant_msg
            else:
                temp_dict[timestamp]["assistant"] = assistant_msg
    
    print(f"  聚合后 {len(temp_dict)} 个时间点")
    
    sorted_keys = sorted(temp_dict.keys())
    print(f"\n  时间点排序后（升序）:")
    for i, key in enumerate(sorted_keys):
        user_msg = temp_dict[key]["user"][:30] if temp_dict[key]["user"] else "(无)"
        print(f"    [{i}] {key}: {user_msg}...")
    
    # 新逻辑：取最后N个
    limit = 20
    recent_keys = sorted_keys[-limit:] if len(sorted_keys) > limit else sorted_keys
    print(f"\n  新逻辑 sorted_keys[-{limit}:] 取到 {len(recent_keys)} 个时间点")
    
    # 旧逻辑：取前N个（错误的！）
    old_keys = sorted_keys[:7]
    print(f"  旧逻辑 sorted_keys[:7] 只取到:")
    for key in old_keys:
        user_msg = temp_dict[key]["user"][:30] if temp_dict[key]["user"] else "(无)"
        print(f"    {key}: {user_msg}...")

def main():
    print(f"=" * 80)
    print(f"查询用户 {USER_ID} 的对话历史")
    print(f"=" * 80)
    
    try:
        engine = get_engine()
        
        # 先测试查询逻辑
        test_dialogue_query_logic()
        
        # 1. 查询表结构
        print("\n【表结构 - t_dialogue】")
        with engine.connect() as conn:
            result = conn.execute(text("DESCRIBE t_dialogue"))
            for row in result.fetchall():
                print(f"  {row[0]}: {row[1]}")
        
        # 2. 查询对话历史
        print(f"\n【最近24小时的对话历史 - 用户 {USER_ID}】")
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, account_id, message, text, type, create_time
                    FROM t_dialogue
                    WHERE account_id = :user_id
                    AND create_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)
                    ORDER BY create_time DESC
                    LIMIT :limit
                """),
                {"user_id": USER_ID, "limit": LIMIT}
            )
            rows = result.fetchall()
        
        if not rows:
            print("  没有找到对话记录！")
        else:
            print(f"  共找到 {len(rows)} 条记录\n")
            
            for i, row in enumerate(rows):
                record_id, account_id, message, text_content, msg_type, create_time = row
                print(f"  [{i+1}] ID: {record_id}")
                print(f"      时间: {create_time}")
                print(f"      类型: {msg_type} (1=用户文字, 2=AI文字, 3=用户语音, 4=AI语音)")
                print(f"      message: {message[:200] if message else 'None'}")
                print(f"      text: {text_content[:200] if text_content else 'None'}")
                print()
        
        # 3. 检查 type 值的分布
        print("\n【消息类型分布】")
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT type, COUNT(*) as cnt
                    FROM t_dialogue
                    WHERE account_id = :user_id
                    AND create_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)
                    GROUP BY type
                """),
                {"user_id": USER_ID}
            )
            for row in result.fetchall():
                type_desc = {1: "用户文字", 2: "AI文字", 3: "用户语音", 4: "AI语音"}.get(row[0], f"未知({row[0]})")
                print(f"  类型 {row[0]} ({type_desc}): {row[1]} 条")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
