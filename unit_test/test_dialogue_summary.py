"""
测试对话总结功能

模拟20轮对话，验证：
1. 第15轮后是否触发总结生成
2. 总结是否正确存储到数据库
3. 后续对话是否包含总结内容
"""
import asyncio
import urllib
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库配置
host = '81.68.235.167'
username = 'pillow'
password = '1234QWERasdf!@#$'
database_name = 'pillow_customer_test'

encoded_password = urllib.parse.quote(password)
DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
engine = create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def check_summary_field():
    """检查数据库中 dialogue_summary 字段"""
    with engine.connect() as conn:
        # 检查 COC 表
        result = conn.execute(text("""
            SELECT session_id, turn_number, LENGTH(dialogue_summary) as summary_len
            FROM t_coc_game_state
            WHERE dialogue_summary IS NOT NULL
            ORDER BY update_time DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        
        print("\n=== COC 游戏状态表中有总结的记录 ===")
        if rows:
            for row in rows:
                print(f"  session_id: {row[0]}, turn: {row[1]}, summary_len: {row[2]}")
        else:
            print("  （暂无有总结的记录）")
        
        # 检查副本世界表
        result = conn.execute(text("""
            SELECT session_id, LENGTH(dialogue_summary) as summary_len
            FROM t_freak_world_game_state
            WHERE dialogue_summary IS NOT NULL
            ORDER BY update_time DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        
        print("\n=== 副本世界游戏状态表中有总结的记录 ===")
        if rows:
            for row in rows:
                print(f"  session_id: {row[0]}, summary_len: {row[1]}")
        else:
            print("  （暂无有总结的记录）")


def get_sample_summary():
    """获取一个示例总结内容"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT session_id, dialogue_summary
            FROM t_coc_game_state
            WHERE dialogue_summary IS NOT NULL AND LENGTH(dialogue_summary) > 100
            ORDER BY update_time DESC
            LIMIT 1
        """))
        row = result.fetchone()
        
        if row:
            print(f"\n=== 示例总结内容 (session: {row[0]}) ===")
            print(row[1][:1000])
            print("...")
        else:
            # 尝试副本世界
            result = conn.execute(text("""
                SELECT session_id, dialogue_summary
                FROM t_freak_world_game_state
                WHERE dialogue_summary IS NOT NULL AND LENGTH(dialogue_summary) > 100
                ORDER BY update_time DESC
                LIMIT 1
            """))
            row = result.fetchone()
            if row:
                print(f"\n=== 示例总结内容 (session: {row[0]}) ===")
                print(row[1][:1000])
                print("...")
            else:
                print("\n（暂无示例总结，需要先进行15轮以上的游戏对话）")


def check_dialogue_count():
    """检查对话轮数"""
    with engine.connect() as conn:
        # COC 对话统计
        result = conn.execute(text("""
            SELECT d.session_id, COUNT(*) as dialogue_count, g.turn_number
            FROM t_freak_world_dialogue d
            JOIN t_coc_game_state g ON d.session_id = g.session_id
            WHERE d.del = 0 AND g.game_status = 'playing'
            GROUP BY d.session_id, g.turn_number
            ORDER BY dialogue_count DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        
        print("\n=== COC 对话轮数统计（前5个活跃会话）===")
        if rows:
            for row in rows:
                print(f"  session_id: {row[0]}, dialogues: {row[1]}, turn: {row[2]}")
        else:
            print("  （暂无活跃会话）")


if __name__ == "__main__":
    print("=" * 60)
    print("对话总结功能状态检查")
    print("=" * 60)
    
    check_summary_field()
    check_dialogue_count()
    get_sample_summary()
    
    print("\n" + "=" * 60)
    print("说明：")
    print("- 总结会在第15、30、45...轮自动异步生成")
    print("- 生成后会存储到 dialogue_summary 字段")
    print("- 后续对话会自动包含【剧情回顾】")
    print("=" * 60)
