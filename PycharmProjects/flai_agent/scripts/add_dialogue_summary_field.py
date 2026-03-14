"""
添加 dialogue_summary 字段到游戏状态表
"""
import urllib
from sqlalchemy import create_engine, text

# 数据库配置
host = '81.68.235.167'
username = 'pillow'
password = '1234QWERasdf!@#$'
database_name = 'pillow_customer_test'

encoded_password = urllib.parse.quote(password)
DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
engine = create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)


def add_dialogue_summary_field():
    """添加 dialogue_summary 字段"""
    with engine.connect() as conn:
        # 检查 t_coc_game_state 表是否已有该字段
        result = conn.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 't_coc_game_state' AND COLUMN_NAME = 'dialogue_summary'
        """), {"db": database_name})
        
        if not result.fetchone():
            print("Adding dialogue_summary to t_coc_game_state...")
            conn.execute(text("""
                ALTER TABLE t_coc_game_state 
                ADD COLUMN dialogue_summary TEXT COMMENT '对话历史总结（滚动更新）'
            """))
            conn.commit()
            print("Done.")
        else:
            print("t_coc_game_state.dialogue_summary already exists.")
        
        # 检查 t_freak_world_game_state 表是否已有该字段
        result = conn.execute(text("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 't_freak_world_game_state' AND COLUMN_NAME = 'dialogue_summary'
        """), {"db": database_name})
        
        if not result.fetchone():
            print("Adding dialogue_summary to t_freak_world_game_state...")
            conn.execute(text("""
                ALTER TABLE t_freak_world_game_state 
                ADD COLUMN dialogue_summary TEXT COMMENT '对话历史总结（滚动更新）'
            """))
            conn.commit()
            print("Done.")
        else:
            print("t_freak_world_game_state.dialogue_summary already exists.")


if __name__ == "__main__":
    add_dialogue_summary_field()
    print("\nAll done!")
