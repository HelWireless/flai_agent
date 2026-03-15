"""
创建预制数据表
运行此脚本创建 t_world_race_appearance 和 t_world_gender_personality 表
"""
import sys
from pathlib import Path

# 将项目根目录添加到 python 路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import engine
from src.models.world_preset_data import Base

def create_tables():
    """创建预制数据表"""
    print("开始创建预制数据表...")
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    print("✅ 表创建完成！")
    print("- t_world_race_appearance: 种族/外貌预制表")
    print("- t_world_gender_personality: 性别/个性预制表")

if __name__ == "__main__":
    create_tables()
