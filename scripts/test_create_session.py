"""
测试脚本：模拟读档时创建新 session 的流程
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

def get_engine():
    host = "81.68.235.167"
    username = "pillow"
    password = "1234QWERasdf!@#$"
    database_name = "pillow_customer_test"
    
    encoded_password = urllib.parse.quote(password)
    DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
    return create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)

def main():
    from src.models.coc_save_slot import COCSaveSlot
    from src.models.coc_game_state import COCGameState
    
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 1. 查询存档
        print("【1. 查询存档 save_id='13'】")
        save_slot = db.query(COCSaveSlot).filter(
            and_(
                COCSaveSlot.save_id == "13",
                COCSaveSlot.del_ == 0
            )
        ).first()
        
        if not save_slot:
            print("  未找到存档!")
            return
            
        print(f"  存档 user_id: {save_slot.user_id}")
        print(f"  存档 session_id: {save_slot.session_id}")
        print(f"  存档 gm_id: {save_slot.gm_id}")
        
        # 2. 检查 session_id 是否已存在
        print(f"\n【2. 检查 session_id='{save_slot.session_id}' 是否已存在】")
        existing_session = db.query(COCGameState).filter(
            COCGameState.session_id == save_slot.session_id
        ).first()
        
        if existing_session:
            print(f"  已存在! id={existing_session.id}, user_id={existing_session.user_id}")
            print(f"  如果尝试用同一个 session_id 创建新记录，会因为 unique 约束失败!")
        else:
            print("  不存在")
        
        # 3. 模拟读档请求（session_id 来自请求）
        request_session_id = "RvqqtAKiSVTRejrr"  # 与存档相同
        print(f"\n【3. 读档请求的 session_id: '{request_session_id}'】")
        
        if request_session_id == save_slot.session_id:
            print("  ⚠️ 请求的 session_id 与存档的 session_id 相同!")
            print("  如果 t_coc_game_state 中已有这个 session_id，插入会失败!")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
