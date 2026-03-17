"""
创建优化后的预制数据表（姓氏池 + 名字池）
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import engine
from src.models.world_preset_data_optimized import WorldSurname, WorldGivenName

def create_name_tables():
    """创建姓氏和名字表"""
    print("=" * 60)
    print("开始创建姓氏和名字表...")
    print("=" * 60)
    
    # 手动创建所有表
    print("\nCreating t_world_surnames (姓氏池)...")
    WorldSurname.__table__.create(bind=engine)
    
    print("Creating t_world_given_names (名字池)...")
    WorldGivenName.__table__.create(bind=engine)
    
    print("\n[SUCCESS] 表创建成功！")
    print("\n已创建的表:")
    print("  - t_world_surnames (姓氏池)")
    print("  - t_world_given_names (名字池，分 1 字/2 字)")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        create_name_tables()
    except Exception as e:
        print(f"\n[ERROR] 创建表失败：{e}")
        import traceback
        traceback.print_exc()
