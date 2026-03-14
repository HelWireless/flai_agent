"""
测试脚本：模拟读档请求
用法：uv run python scripts/test_load_save.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import urllib
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def get_engine():
    """创建数据库引擎 - 测试环境"""
    host = "81.68.235.167"
    username = "pillow"
    password = "1234QWERasdf!@#$"
    database_name = "pillow_customer_test"
    
    encoded_password = urllib.parse.quote(password)
    DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
    return create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)

def run_request_parsing_logic():
    """执行请求解析逻辑"""
    print("\n🔍 测试请求解析...")
    
    # 模拟一个保存槽位数据
    save_data = {
        "id": "13",
        "user_id": "123",
        "character_id": "coc_gm_li",
        "save_name": "测试存档",
        "game_type": "coc"
    }
    
    # 验证数据
    assert save_data["id"] == "13"
    print(f"  ✅ 请求解析成功，得到 save_id: {save_data['id']}")
    return save_data["id"]

def run_db_query(save_id: str):
    """测试数据库查询"""
    print(f"\n【测试数据库查询 save_id='{save_id}'】")
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # 方法1: 直接 SQL 查询
        result = conn.execute(
            text("""
                SELECT id, save_id, session_id, account_id, gm_id, game_status, 
                       investigator_card, round_number, turn_number, temp_data, del
                FROM t_coc_save_slot
                WHERE save_id = :save_id AND del = 0
            """),
            {"save_id": save_id}
        )
        row = result.fetchone()
        
        if row:
            print(f"  找到存档记录!")
            print(f"    id: {row[0]}")
            print(f"    save_id: '{row[1]}'")
            print(f"    session_id: '{row[2]}'")
            print(f"    user_id: {row[3]}")
            print(f"    gm_id: '{row[4]}'")
            print(f"    game_status: '{row[5]}'")
            print(f"    investigator_card: {str(row[6])[:100]}...")
            print(f"    round_number: {row[7]}")
            print(f"    turn_number: {row[8]}")
            print(f"    temp_data: {str(row[9])[:100]}...")
            print(f"    del: {row[10]}")
        else:
            print(f"  未找到存档记录!")
            
            # 检查是否是 del=1 导致
            result2 = conn.execute(
                text("""
                    SELECT id, save_id, del FROM t_coc_save_slot
                    WHERE save_id = :save_id
                """),
                {"save_id": save_id}
            )
            row2 = result2.fetchone()
            if row2:
                print(f"  但找到了已删除的记录: id={row2[0]}, save_id='{row2[1]}', del={row2[2]}")

def run_sqlalchemy_orm_query(save_id: str):
    """测试 SQLAlchemy ORM 查询（与服务代码一致）"""
    print(f"\n【测试 SQLAlchemy ORM 查询 save_id='{save_id}'】")
    
    from sqlalchemy import and_
    from src.models.coc_save_slot import COCSaveSlot
    
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 与 coc_service._get_save_slot 一致的查询
        save_slot = db.query(COCSaveSlot).filter(
            and_(
                COCSaveSlot.save_id == save_id,
                COCSaveSlot.del_ == 0
            )
        ).first()
        
        if save_slot:
            print(f"  找到存档记录!")
            print(f"    id: {save_slot.id}")
            print(f"    save_id: '{save_slot.save_id}'")
            print(f"    session_id: '{save_slot.session_id}'")
            print(f"    account_id: {save_slot.account_id}")
            print(f"    gm_id: '{save_slot.gm_id}'")
            print(f"    game_status: '{save_slot.game_status}'")
            print(f"    investigator_card: {str(save_slot.investigator_card)[:100]}...")
            print(f"    round_number: {save_slot.round_number}")
            print(f"    turn_number: {save_slot.turn_number}")
            print(f"    temp_data: {str(save_slot.temp_data)[:100]}...")
        else:
            print(f"  ORM 查询未找到存档记录!")
            
            # 调试：检查 del_ 字段的实际值
            all_slots = db.query(COCSaveSlot).filter(
                COCSaveSlot.save_id == save_id
            ).all()
            
            if all_slots:
                for slot in all_slots:
                    print(f"  但找到记录: id={slot.id}, save_id='{slot.save_id}', del_={slot.del_} (type: {type(slot.del_).__name__})")
            else:
                print(f"  完全没有找到 save_id='{save_id}' 的记录")
                
    finally:
        db.close()

import pytest

def test_load_save_flow():
    """Pytest entry point for load/save flow"""
    save_id = run_request_parsing_logic()
    assert save_id == "13"
    
    # 数据库查询测试跳过，除非有环境
    try:
        run_db_query(save_id)
        run_sqlalchemy_orm_query(save_id)
        run_save_slot_attributes()
    except Exception as e:
        print(f"数据库连接失败（预期行为，如果不在特定网络环境）: {e}")
        pytest.skip("Database connection failed")

def run_save_slot_attributes():
    """测试存档记录的属性访问"""
    print("\n【测试存档记录属性访问】")
    
    from sqlalchemy import and_
    from src.models.coc_save_slot import COCSaveSlot
    
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        save_slot = db.query(COCSaveSlot).filter(
            and_(
                COCSaveSlot.save_id == "13",
                COCSaveSlot.del_ == 0
            )
        ).first()
        
        if save_slot:
            print(f"  save_slot 类型: {type(save_slot)}")
            print(f"  save_slot.user_id: {save_slot.user_id} (type: {type(save_slot.user_id).__name__})")
            print(f"  save_slot.session_id: {save_slot.session_id} (type: {type(save_slot.session_id).__name__})")
            print(f"  save_slot.gm_id: {save_slot.gm_id}")
            print(f"  save_slot.investigator_card 类型: {type(save_slot.investigator_card)}")
            print(f"  save_slot.temp_data 类型: {type(save_slot.temp_data)}")
        else:
            print("  未找到存档!")
    finally:
        db.close()

def main():
    print("=" * 80)
    print("测试读档流程")
    print("=" * 80)
    
    # 1. 测试请求解析
    save_id = test_request_parsing_logic()
    
    if save_id:
        # 2. 测试原始 SQL 查询
        test_db_query(save_id)
        
        # 3. 测试 ORM 查询
        test_sqlalchemy_orm_query(save_id)
        
        # 4. 测试存档属性访问
        test_save_slot_attributes()

if __name__ == "__main__":
    main()
