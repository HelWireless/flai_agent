"""
测试脚本：查询存档记录
用法：python scripts/check_save_slot.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib
from sqlalchemy import create_engine, text

def get_engine():
    """创建数据库引擎 - 测试环境"""
    host = "81.68.235.167"
    username = "pillow"
    password = "1234QWERasdf!@#$"
    database_name = "pillow_customer_test"
    
    encoded_password = urllib.parse.quote(password)
    DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
    return create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)

def main():
    print("=" * 80)
    print("查询存档表 t_coc_save_slot")
    print("=" * 80)
    
    try:
        engine = get_engine()
        
        # 1. 查询表结构
        print("\n【表结构 - t_coc_save_slot】")
        with engine.connect() as conn:
            result = conn.execute(text("DESCRIBE t_coc_save_slot"))
            for row in result.fetchall():
                print(f"  {row[0]}: {row[1]} | {row[2]} | {row[3]}")
        
        # 2. 查询所有存档
        print("\n【所有存档记录】")
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, save_id, session_id, user_id, gm_id, game_status, create_time, del
                    FROM t_coc_save_slot
                    ORDER BY create_time DESC
                    LIMIT 20
                """)
            )
            rows = result.fetchall()
        
        if not rows:
            print("  没有找到存档记录！")
        else:
            print(f"  共找到 {len(rows)} 条记录\n")
            
            for i, row in enumerate(rows):
                record_id, save_id, session_id, user_id, gm_id, game_status, create_time, del_flag = row
                print(f"  [{i+1}] id={record_id}, save_id='{save_id}' (类型: {type(save_id).__name__})")
                print(f"       session_id={session_id}, user_id={user_id}")
                print(f"       gm_id={gm_id}, game_status={game_status}")
                print(f"       create_time={create_time}, del={del_flag}")
                print()
        
        # 3. 查询特定 save_id
        test_save_id = "13"
        print(f"\n【查询 save_id='{test_save_id}'】")
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, save_id, session_id, user_id, gm_id, game_status, create_time, del
                    FROM t_coc_save_slot
                    WHERE save_id = :save_id
                """),
                {"save_id": test_save_id}
            )
            rows = result.fetchall()
        
        if not rows:
            print(f"  没有找到 save_id='{test_save_id}' 的记录！")
            
            # 尝试模糊查询
            print(f"\n【模糊查询包含 '13' 的存档】")
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT id, save_id, session_id, user_id
                        FROM t_coc_save_slot
                        WHERE save_id LIKE :pattern
                    """),
                    {"pattern": "%13%"}
                )
                fuzzy_rows = result.fetchall()
            
            if fuzzy_rows:
                for row in fuzzy_rows:
                    print(f"  找到: id={row[0]}, save_id='{row[1]}', session={row[2]}, account={row[3]}")
            else:
                print("  模糊查询也没有找到！")
        else:
            print(f"  找到 {len(rows)} 条记录")
            for row in rows:
                print(f"  {row}")
        
        # 4. 查询 user_id=1000003 的存档
        print(f"\n【查询 user_id=1000003 的存档】")
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, save_id, session_id, user_id, gm_id, game_status, create_time, del
                    FROM t_coc_save_slot
                    WHERE user_id = 1000003
                    ORDER BY create_time DESC
                """)
            )
            rows = result.fetchall()
        
        if not rows:
            print("  没有找到该用户的存档！")
        else:
            print(f"  找到 {len(rows)} 条记录")
            for row in rows:
                print(f"    id={row[0]}, save_id='{row[1]}', session={row[2]}, del={row[7]}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
