"""
测试脚本：检查 t_coc_game_state 表结构
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib
from sqlalchemy import create_engine, text

def get_engine():
    host = "81.68.235.167"
    username = "pillow"
    password = "1234QWERasdf!@#$"
    database_name = "pillow_customer_test"
    
    encoded_password = urllib.parse.quote(password)
    DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
    return create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)

def main():
    engine = get_engine()
    
    with engine.connect() as conn:
        # 检查表是否存在
        print("【检查 t_coc_game_state 表】")
        result = conn.execute(text("SHOW TABLES LIKE 't_coc_game_state'"))
        tables = result.fetchall()
        if tables:
            print("  表存在!")
            
            # 查看表结构
            print("\n【表结构】")
            result = conn.execute(text("DESCRIBE t_coc_game_state"))
            for row in result.fetchall():
                print(f"  {row[0]}: {row[1]} | {row[2]} | {row[3]}")
        else:
            print("  表不存在!")
            
            # 列出所有表
            print("\n【数据库中的表】")
            result = conn.execute(text("SHOW TABLES"))
            for row in result.fetchall():
                print(f"  {row[0]}")

if __name__ == "__main__":
    main()
