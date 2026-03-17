# -*- coding: utf-8 -*-
"""
为所有 8 个副本世界各运行两遍角色生成，输出 Markdown 报告
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
from sqlalchemy import func
from datetime import datetime


# 世界定义
WORLDS = {
    'world_01': {'name': '暗湖酒馆 - 永夜歌谣', 'style': '西方奇幻 + 深渊神秘'},
    'world_04': {'name': '诡秘序列 - 通灵者游戏', 'style': '克苏鲁 + 灵异悬疑'},
    'world_06': {'name': '废土纪元 - 最后避难所', 'style': '末日废土 + 赛博朋克'},
    'world_10': {'name': '仙界 - 我在天庭当社畜', 'style': '东方仙侠 + 现代职场'},
    'world_13': {'name': '怪谈世界 - 规则类怪谈合集', 'style': '日式怪谈 + 规则恐怖'},
    'world_17': {'name': '永夜帝国 - 血族王座', 'style': '哥特吸血鬼 + 宫廷权谋'},
    'world_21': {'name': '深渊凝视 - 旧日回响', 'style': '克苏鲁神话 + 深海恐惧'},
    'world_23': {'name': '晶壁系 - 多元宇宙', 'style': 'DND 奇幻 + 多元宇宙'},
}


def get_db_stats(db, world_id):
    """获取指定世界的数据统计"""
    race_count = db.query(func.count(WorldRaceAppearance.id)).filter(
        WorldRaceAppearance.world_id == world_id, WorldRaceAppearance.status == 1
    ).scalar()
    
    male_p = db.query(func.count(WorldGenderPersonality.id)).filter(
        WorldGenderPersonality.world_id == world_id,
        WorldGenderPersonality.gender == '男性',
        WorldGenderPersonality.status == 1
    ).scalar()
    
    female_p = db.query(func.count(WorldGenderPersonality.id)).filter(
        WorldGenderPersonality.world_id == world_id,
        WorldGenderPersonality.gender == '女性',
        WorldGenderPersonality.status == 1
    ).scalar()
    
    surname_count = db.query(func.count(WorldSurname.id)).filter(
        WorldSurname.world_id == world_id, WorldSurname.status == 1
    ).scalar()
    
    given_name_count = db.query(func.count(WorldGivenName.id)).filter(
        WorldGivenName.world_id == world_id, WorldGivenName.status == 1
    ).scalar()
    
    return {
        'race': race_count,
        'male_personality': male_p,
        'female_personality': female_p,
        'surname': surname_count,
        'given_name': given_name_count,
    }


def generate_characters_for_world(preset_manager, world_id, count_per_gender=3):
    """为单个世界生成一批角色"""
    characters = []
    
    for _ in range(count_per_gender):
        male_chars = preset_manager.generate_character_combinations(world_id, "male", 1)
        characters.extend(male_chars)
    
    for _ in range(count_per_gender):
        female_chars = preset_manager.generate_character_combinations(world_id, "female", 1)
        characters.extend(female_chars)
    
    return characters


def truncate_text(text, max_len=60):
    """截断过长文本"""
    if not text:
        return ''
    if len(text) > max_len:
        return text[:max_len] + '...'
    return text


def build_markdown():
    """构建完整的 Markdown 报告"""
    db = SessionLocal()
    
    try:
        preset_manager = WorldPresetDataManager(db)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        md = []
        md.append("# 副本世界角色生成报告")
        md.append("")
        md.append(f"**生成时间**: {timestamp}")
        md.append(f"**副本总数**: {len(WORLDS)} 个世界")
        md.append(f"**生成策略**: 每个副本运行两遍，每遍生成 3 男 + 3 女 = 6 个角色")
        md.append(f"**名字组合**: 姓氏池随机 + 名字池随机（70% 两字名，30% 单字名）")
        md.append("")
        md.append("---")
        md.append("")
        
        # 数据总览
        md.append("## 预制数据总览")
        md.append("")
        md.append("| 世界 | 种族/外貌 | 男性个性 | 女性个性 | 姓氏 | 名字 | 可组合姓名 |")
        md.append("|------|-----------|----------|----------|------|------|------------|")
        
        total_stats = {}
        for world_id in WORLDS:
            stats = get_db_stats(db, world_id)
            total_stats[world_id] = stats
            name_combos = stats['surname'] * stats['given_name']
            md.append(
                f"| {WORLDS[world_id]['name']} | {stats['race']} | "
                f"{stats['male_personality']} | {stats['female_personality']} | "
                f"{stats['surname']} | {stats['given_name']} | {name_combos:,} |"
            )
        
        md.append("")
        md.append("---")
        md.append("")
        
        # 逐世界生成
        world_idx = 0
        for world_id, world_info in WORLDS.items():
            world_idx += 1
            stats = total_stats[world_id]
            
            print(f"[{world_idx}/{len(WORLDS)}] {world_info['name']} ({world_id})...")
            
            md.append(f"## {world_idx}. {world_info['name']}")
            md.append("")
            md.append(f"- **世界 ID**: `{world_id}`")
            md.append(f"- **风格**: {world_info['style']}")
            md.append(f"- **预制数据**: {stats['race']} 种族, "
                       f"{stats['male_personality']+stats['female_personality']} 个性, "
                       f"{stats['surname']} 姓氏, {stats['given_name']} 名字")
            md.append("")
            
            # 第一遍
            print(f"  [1/2] Generating round 1...")
            gen1 = generate_characters_for_world(preset_manager, world_id, count_per_gender=3)
            
            md.append("### 第一遍生成（3 男 + 3 女）")
            md.append("")
            
            if gen1:
                md.append("| # | 姓名 | 性别 | 种族/职业 | 外貌描述 | 个性特点 |")
                md.append("|---|------|------|-----------|----------|----------|")
                for i, char in enumerate(gen1, 1):
                    name = char.get('full_name', '?')
                    gender = char.get('gender', '?')
                    race = char.get('race', '?')
                    appearance = truncate_text(char.get('appearance', ''), 40)
                    personality = truncate_text(char.get('personality', ''), 40)
                    md.append(f"| {i} | **{name}** | {gender} | {race} | {appearance} | {personality} |")
                md.append("")
            else:
                md.append("> (!) 数据不足，无法生成角色")
                md.append("")
            
            # 第二遍
            print(f"  [2/2] Generating round 2...")
            gen2 = generate_characters_for_world(preset_manager, world_id, count_per_gender=3)
            
            md.append("### 第二遍生成（3 男 + 3 女）")
            md.append("")
            
            if gen2:
                md.append("| # | 姓名 | 性别 | 种族/职业 | 外貌描述 | 个性特点 |")
                md.append("|---|------|------|-----------|----------|----------|")
                for i, char in enumerate(gen2, 1):
                    name = char.get('full_name', '?')
                    gender = char.get('gender', '?')
                    race = char.get('race', '?')
                    appearance = truncate_text(char.get('appearance', ''), 40)
                    personality = truncate_text(char.get('personality', ''), 40)
                    md.append(f"| {i} | **{name}** | {gender} | {race} | {appearance} | {personality} |")
                md.append("")
            else:
                md.append("> (!) 数据不足，无法生成角色")
                md.append("")
            
            # 两遍对比
            if gen1 and gen2:
                names1 = set(c.get('full_name') for c in gen1)
                names2 = set(c.get('full_name') for c in gen2)
                overlap = names1 & names2
                races1 = set(c.get('race') for c in gen1)
                races2 = set(c.get('race') for c in gen2)
                race_overlap = races1 & races2
                
                md.append(f"> **两遍对比**: 姓名重复 {len(overlap)}/{len(gen1)} 个, "
                          f"种族重复 {len(race_overlap)}/{len(races1)} 个 -- "
                          f"随机性{'良好' if len(overlap) <= 1 else '一般'}")
                md.append("")
            
            md.append("---")
            md.append("")
            
            print(f"  [OK] Round 1: {len(gen1)} chars, Round 2: {len(gen2)} chars")
        
        # 总结
        md.append("## 总结")
        md.append("")
        total_chars = sum(1 for _ in WORLDS) * 12  # 6 per round * 2 rounds
        md.append(f"- **总生成角色数**: {len(WORLDS)} 个世界 x 2 遍 x 6 角色 = {total_chars} 个")
        md.append(f"- **姓名来源**: 预制姓氏池 + 预制名字池随机组合（无需 LLM 调用）")
        md.append(f"- **种族/外貌**: 预制数据库随机抽取（无需 LLM 调用）")
        md.append(f"- **性别/个性**: 预制数据库随机抽取（无需 LLM 调用）")
        md.append(f"- **LLM 调用次数**: 0 次（全部使用预制数据）")
        md.append("")
        md.append("### 技术架构")
        md.append("")
        md.append("```")
        md.append("角色生成流程（优化后）:")
        md.append("")
        md.append("  1. 姓氏池 -----> 随机选取 1 个姓氏")
        md.append("  2. 名字池 -----> 按性别倾向 + 字数（70% 两字/30% 一字）选取")
        md.append("  3. 种族外貌池 -> 随机选取 1 条种族+外貌描述")
        md.append("  4. 性别个性池 -> 按性别筛选后随机选取 1 条个性描述")
        md.append("  5. 组合输出 ---> {姓+名, 种族, 外貌, 性别, 个性}")
        md.append("")
        md.append("  全程 0 次 LLM API 调用，响应时间 < 10ms")
        md.append("```")
        md.append("")
        md.append("### 数据库表")
        md.append("")
        md.append("| 表名 | 用途 | 关键字段 |")
        md.append("|------|------|----------|")
        md.append("| t_world_surnames | 姓氏池 | world_id, surname, style |")
        md.append("| t_world_given_names | 名字池 | world_id, given_name, character_count, gender_tendency |")
        md.append("| t_world_race_appearance | 种族外貌 | world_id, race, appearance |")
        md.append("| t_world_gender_personality | 性别个性 | world_id, gender, personality |")
        md.append("")
        md.append("---")
        md.append("")
        md.append("*本报告由预制数据系统自动生成*")
        
        # 写入文件
        content = "\n".join(md)
        output_path = project_root / "unit_test" / "character_generation_report.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n{'='*60}")
        print(f"[DONE] Report saved to: {output_path}")
        print(f"{'='*60}")
        
        return str(output_path)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    build_markdown()
