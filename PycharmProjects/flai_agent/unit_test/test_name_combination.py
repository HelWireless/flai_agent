"""
测试优化后的名字组合功能（姓 + 名）
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import SessionLocal
from src.models.world_preset_data_optimized import WorldPresetDataManager

def test_name_generation():
    """测试名字生成"""
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("[TEST] 测试姓 + 名组合功能")
        print("=" * 60)
        
        preset_manager = WorldPresetDataManager(db)
        
        # 测试 1：单独获取姓氏
        print("\n[TEST 1] 随机获取姓氏...")
        surnames = preset_manager.get_random_surname("world_01", 5)
        print(f"   获取到的姓氏：{', '.join(surnames)}")
        
        # 测试 2：单独获取 1 字名字
        print("\n[TEST 2] 随机获取 1 字名字...")
        given_names_1 = preset_manager.get_random_given_name("world_01", character_count=1, count=5)
        print(f"   获取到的 1 字名：{', '.join(given_names_1)}")
        
        # 测试 3：单独获取 2 字名字
        print("\n[TEST 3] 随机获取 2 字名字...")
        given_names_2 = preset_manager.get_random_given_name("world_01", character_count=2, count=5)
        print(f"   获取到的 2 字名：{', '.join(given_names_2)}")
        
        # 测试 4：按性别获取名字
        print("\n[TEST 4] 获取男性倾向的名字...")
        male_names = preset_manager.get_random_given_name("world_01", gender_tendency='男性', count=5)
        print(f"   男性名字：{', '.join(male_names)}")
        
        print("\n[TEST 5] 获取女性倾向的名字...")
        female_names = preset_manager.get_random_given_name("world_01", gender_tendency='女性', count=5)
        print(f"   女性名字：{', '.join(female_names)}")
        
        # 测试 5：生成完整姓名
        print("\n[TEST 6] 生成完整姓名（姓 + 名）...")
        print("   男性姓名:")
        for i in range(5):
            full_name = preset_manager.generate_full_name("world_01", gender='male')
            print(f"     {i+1}. {full_name}")
        
        print("   女性姓名:")
        for i in range(5):
            full_name = preset_manager.generate_full_name("world_01", gender='female')
            print(f"     {i+1}. {full_name}")
        
        # 测试 6：生成角色组合（包含完整姓名）
        print("\n[TEST 7] 生成角色组合（含完整姓名）...")
        characters = preset_manager.generate_character_combinations("world_01", "male", 3)
        
        for i, char in enumerate(characters, 1):
            print(f"\n   角色 {i}:")
            print(f"     姓名：{char.get('full_name')}")
            print(f"     种族：{char.get('race')}")
            print(f"     外貌：{char.get('appearance')[:50]}...")
            print(f"     个性：{char.get('personality')[:30]}...")
        
        # 统计信息
        print("\n[TEST 8] 数据统计...")
        from sqlalchemy import func
        from src.models.world_preset_data_optimized import WorldSurname, WorldGivenName
        
        surname_count = db.query(func.count(WorldSurname.id)).filter(
            WorldSurname.world_id == 'world_01'
        ).scalar()
        
        given_name_count = db.query(func.count(WorldGivenName.id)).filter(
            WorldGivenName.world_id == 'world_01'
        ).scalar()
        
        print(f"   world_01 名字数据:")
        print(f"   - 姓氏：{surname_count} 个")
        print(f"   - 名字：{given_name_count} 个")
        print(f"   - 可组合姓名数：约 {surname_count * given_name_count} 种")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败：{e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_name_generation()
