"""
为 world_01 生成两遍预制数据并生成 Markdown 报告
演示用途
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import SessionLocal
from src.models.world_preset_data_optimized import (
    WorldRaceAppearance,
    WorldGenderPersonality, 
    WorldSurname,
    WorldGivenName,
    WorldPresetDataManager
)
from datetime import datetime

def generate_demo_report():
    """生成演示报告"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("为 world_01 生成示例角色（两遍）并创建 Markdown 报告...")
        print("=" * 80)
        
        preset_manager = WorldPresetDataManager(db)
        all_characters = []
        
        # 第一遍：生成 5 个男性角色 + 5 个女性角色
        print("\n[第 1 遍] 生成 10 个角色...")
        for i in range(5):
            male_chars = preset_manager.generate_character_combinations("world_01", "male", 1)
            for char in male_chars:
                char['world_name'] = '暗湖酒馆·永夜歌谣'
                char['generation'] = 1
                all_characters.append(char)
            
            female_chars = preset_manager.generate_character_combinations("world_01", "female", 1)
            for char in female_chars:
                char['world_name'] = '暗湖酒馆·永夜歌谣'
                char['generation'] = 1
                all_characters.append(char)
        
        print(f"   已生成 {len(all_characters)} 个角色")
        
        # 第二遍：再生成 5 个男性角色 + 5 个女性角色
        print("\n[第 2 遍] 生成另外 10 个角色...")
        for i in range(5):
            male_chars = preset_manager.generate_character_combinations("world_01", "male", 1)
            for char in male_chars:
                char['world_name'] = '暗湖酒馆·永夜歌谣'
                char['generation'] = 2
                all_characters.append(char)
            
            female_chars = preset_manager.generate_character_combinations("world_01", "female", 1)
            for char in female_chars:
                char['world_name'] = '暗湖酒馆·永夜歌谣'
                char['generation'] = 2
                all_characters.append(char)
        
        print(f"   总计 {len(all_characters)} 个角色")
        
        # 生成 Markdown 报告
        print("\n生成 Markdown 报告...")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        md_content = f"""# 副本世界角色生成报告 - world_01 演示

**生成时间**: {timestamp}  
**世界名称**: 暗湖酒馆·永夜歌谣 (world_01)  
**世界风格**: 西方奇幻 + 深渊神秘  
**生成模型**: qwen3_max（种族、个性） + qwen_turbo（名字）  
**总计**: {len(all_characters)} 个示例角色（分两遍生成）

---

## 第一遍生成（5 男 5 女）

"""
        
        gen1_chars = [c for c in all_characters if c.get('generation') == 1]
        gen2_chars = [c for c in all_characters if c.get('generation') == 2]
        
        for i, char in enumerate(gen1_chars, 1):
            full_name = char.get('full_name', '无名')
            race = char.get('race', '未知种族')
            appearance = char.get('appearance', '')
            personality = char.get('personality', '')
            gender = char.get('gender', '')
            
            md_content += f"""### 角色 {i}: **{full_name}** {'♂️' if gender == 'male' else '♀️'}

| 属性 | 描述 |
|------|------|
| **性别** | {gender} |
| **种族/职业** | {race} |
| **外貌描述** | {appearance} |
| **个性特点** | {personality} |

---

"""
        
        md_content += f"""
## 第二遍生成（5 男 5 女）

"""
        
        for i, char in enumerate(gen2_chars, 1):
            full_name = char.get('full_name', '无名')
            race = char.get('race', '未知种族')
            appearance = char.get('appearance', '')
            personality = char.get('personality', '')
            gender = char.get('gender', '')
            
            md_content += f"""### 角色 {i+10}: **{full_name}** {'♂️' if gender == 'male' else '♀️'}

| 属性 | 描述 |
|------|------|
| **性别** | {gender} |
| **种族/职业** | {race} |
| **外貌描述** | {appearance} |
| **个性特点** | {personality} |

---

"""
        
        # 统计信息
        md_content += f"""## 统计信息

- **总角色数**: {len(all_characters)}
- **第一遍**: {len(gen1_chars)} 个角色
- **第二遍**: {len(gen2_chars)} 个角色
- **男性角色**: {len([c for c in all_characters if c.get('gender') == 'male'])} 个
- **女性角色**: {len([c for c in all_characters if c.get('gender') == 'female'])} 个

## 数据来源

所有角色的：
- **姓名**: 从预制池随机组合（姓 + 名，70% 概率 2 字名）
- **种族/外貌**: 从 20 条预制数据中随机抽取
- **性别/个性**: 从 20 条预制数据中随机抽取

**预制数据库存**:
- t_world_surnames: 36 个姓氏
- t_world_given_names: 54 个名字（1 字 +2 字）
- t_world_race_appearance: 20 条种族外貌
- t_world_gender_personality: 20 条性别个性

**可组合角色数**: 约 1,944 种不同姓名 × 20 种族 × 20 个性 = **777,600 种可能**

---

*本报告由 AI 自动生成，所有角色数据已存入数据库可供调用*
"""
        
        # 保存文件
        output_path = project_root / "unit_test" / "generated_characters_demo.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"\n[OK] Markdown 报告已保存至：{output_path}")
        print(f"\n{'='*80}")
        print("演示完成！共生成 20 个角色（两遍各 10 个）")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\n[ERROR] 生成失败：{e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    generate_demo_report()
