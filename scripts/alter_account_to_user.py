"""
脚本：修改数据库表字段 account_id -> user_id
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
        # 1. 修改 t_coc_game_state
        print('【修改 t_coc_game_state 表】')
        try:
            conn.execute(text('ALTER TABLE t_coc_game_state CHANGE account_id user_id INT UNSIGNED NOT NULL COMMENT "用户id"'))
            print('  字段 account_id -> user_id 修改成功')
        except Exception as e:
            print(f'  字段修改失败或已修改: {e}')
        
        try:
            conn.execute(text('ALTER TABLE t_coc_game_state DROP INDEX idx_account_id'))
            print('  删除旧索引 idx_account_id 成功')
        except Exception as e:
            print(f'  删除旧索引失败或不存在: {e}')
        
        try:
            conn.execute(text('ALTER TABLE t_coc_game_state ADD INDEX idx_user_id (user_id)'))
            print('  创建新索引 idx_user_id 成功')
        except Exception as e:
            print(f'  创建新索引失败或已存在: {e}')
        
        conn.commit()
        
        # 2. 修改 t_freak_world_game_state
        print('\n【修改 t_freak_world_game_state 表】')
        try:
            conn.execute(text('ALTER TABLE t_freak_world_game_state CHANGE account_id user_id INT UNSIGNED NOT NULL COMMENT "用户id"'))
            print('  字段 account_id -> user_id 修改成功')
        except Exception as e:
            print(f'  字段修改失败或已修改: {e}')
        
        try:
            conn.execute(text('ALTER TABLE t_freak_world_game_state DROP INDEX idx_account_id'))
            print('  删除旧索引 idx_account_id 成功')
        except Exception as e:
            print(f'  删除旧索引失败或不存在: {e}')
        
        try:
            conn.execute(text('ALTER TABLE t_freak_world_game_state ADD INDEX idx_user_id (user_id)'))
            print('  创建新索引 idx_user_id 成功')
        except Exception as e:
            print(f'  创建新索引失败或已存在: {e}')
        
        conn.commit()
        
        # 3. 修改 t_coc_save_slot
        print('\n【修改 t_coc_save_slot 表】')
        try:
            conn.execute(text('ALTER TABLE t_coc_save_slot CHANGE account_id user_id INT UNSIGNED NOT NULL COMMENT "用户ID"'))
            print('  字段 account_id -> user_id 修改成功')
        except Exception as e:
            print(f'  字段修改失败或已修改: {e}')
        
        try:
            conn.execute(text('ALTER TABLE t_coc_save_slot DROP INDEX idx_account_id'))
            print('  删除旧索引 idx_account_id 成功')
        except Exception as e:
            print(f'  删除旧索引失败或不存在: {e}')
        
        try:
            conn.execute(text('ALTER TABLE t_coc_save_slot ADD INDEX idx_user_id (user_id)'))
            print('  创建新索引 idx_user_id 成功')
        except Exception as e:
            print(f'  创建新索引失败或已存在: {e}')
        
        conn.commit()
        
        # 验证修改结果
        print('\n【验证修改结果】')
        for table in ['t_coc_game_state', 't_freak_world_game_state', 't_coc_save_slot']:
            result = conn.execute(text(f'DESCRIBE {table}'))
            columns = [row[0] for row in result.fetchall()]
            has_user_id = 'user_id' in columns
            has_account_id = 'account_id' in columns
            print(f'  {table}: user_id={has_user_id}, account_id={has_account_id}')

if __name__ == "__main__":
    main()
