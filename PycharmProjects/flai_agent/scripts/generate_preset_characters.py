"""
生成副本世界角色预制数据
为每个世界生成：
1. 20条 race_appearance 组合
2. 20条 gender_personality 组合（男性10条，女性10条）
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 将项目根目录添加到 python 路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import SessionLocal
from src.models.prompt_config import PromptConfig
from src.services.llm_service import LLMService
from src.services.instance_world_prompts import load_world_setting
import yaml


async def generate_race_appearance_for_world(llm, world_id: str, world_name: str, world_setting: str, count: int = 20):
    """为指定世界生成种族/外貌组合"""
    
    prompt = f"""你是一个专业的角色设定生成器。请为以下世界生成{count}个独特的种族/职业与外貌描述组合。

【世界设定】
{world_setting[:1000]}

【要求】
1. 每个组合包含：
   - race: 种族/职业名称（2-6个字，符合世界观）
   - appearance: 外貌描述（一句话，包含服装、发型、特征等细节）

2. 种族/职业要多样化，涵盖：
   - 战斗类（如：剑士、刺客、法师）
   - 生活类（如：商人、学者、工匠）
   - 特殊类（如：异能者、混血种、古老种族）

3. 外貌描述要：
   - 具体且有画面感
   - 符合该种族/职业的特点
   - 避免过于笼统的词汇

请以JSON数组格式返回：
[
  {{"race": "血契贵族", "appearance": "银灰长发松挽，深红高开叉旗袍裹着冷艳曲线，指尖把玩着一柄血晶匕首。"}},
  {{"race": "影息族", "appearance": "烟雾般的靛蓝轮廓倚在墙角，胸口能量核心幽幽发亮，耳后延伸出两根感知震颤的晶须。"}}
]
只返回JSON数组，不要其他内容。"""

    try:
        response = await llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_pool=["qwen_turbo"],
            temperature=0.9,
            max_tokens=4096,
            parse_json=False,
            timeout=60
        )
        
        content = response.get("content", "")
        
        # 清理JSON格式
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        items = json.loads(content.strip())
        
        if isinstance(items, list) and len(items) > 0:
            print(f"✅ 成功生成 {len(items)} 条 race_appearance 数据")
            return items
        else:
            print(f"⚠️ 返回格式不正确")
            return []
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return []


async def generate_gender_personality_for_world(llm, world_id: str, world_name: str, world_setting: str, gender: str, count: int = 10):
    """为指定世界生成性别/个性组合"""
    
    prompt = f"""你是一个专业的角色设定生成器。请为以下世界生成{count}个独特的{gender}性角色个性描述。

【世界设定】
{world_setting[:1000]}

【要求】
1. 每个组合包含：
   - gender: "{gender}"
   - personality: 个性描述（一句话，包含性格特点、说话方式、行为习惯等）

2. 个性类型要多样化，涵盖：
   - 外向型（如：热情、豪爽、活泼）
   - 内向型（如：沉稳、忧郁、神秘）
   - 复杂型（如：外冷内热、亦正亦邪、矛盾纠结）

3. 个性描述要：
   - 具体且有辨识度
   - 符合该世界的氛围
   - 避免过于简单的形容词堆砌

请以JSON数组格式返回：
[
  {{"gender": "{gender}", "personality": "疏离而敏锐，言语如湖面涟漪般轻不可捉，却总能精准刺中他人未言之痛。"}},
  {{"gender": "{gender}", "personality": "恪守逻辑却厌恶规则，用讽刺当盾、悖论为矛，在秩序废墟上栽种自己的正义。"}}
]
只返回JSON数组，不要其他内容。"""

    try:
        response = await llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model_pool=["qwen_turbo"],
            temperature=0.9,
            max_tokens=4096,
            parse_json=False,
            timeout=60
        )
        
        content = response.get("content", "")
        
        # 清理JSON格式
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        items = json.loads(content.strip())
        
        if isinstance(items, list) and len(items) > 0:
            print(f"✅ 成功生成 {len(items)} 条 {gender} 的 gender_personality 数据")
            return items
        else:
            print(f"⚠️ 返回格式不正确")
            return []
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return []


async def save_to_database(db, world_id: str, race_appearance_items: list, gender_personality_items: list):
    """保存生成的数据到数据库"""
    from src.models.world_preset_data import WorldRaceAppearance, WorldGenderPersonality
    
    try:
        # 清空该世界的旧数据
        db.query(WorldRaceAppearance).filter(WorldRaceAppearance.world_id == world_id).delete()
        db.query(WorldGenderPersonality).filter(WorldGenderPersonality.world_id == world_id).delete()
        
        # 保存 race_appearance
        for i, item in enumerate(race_appearance_items):
            record = WorldRaceAppearance(
                world_id=world_id,
                race=item.get("race", ""),
                appearance=item.get("appearance", ""),
                status=1,
                sort_order=i
            )
            db.add(record)
        
        # 保存 gender_personality
        for i, item in enumerate(gender_personality_items):
            record = WorldGenderPersonality(
                world_id=world_id,
                gender=item.get("gender", ""),
                personality=item.get("personality", ""),
                status=1,
                sort_order=i
            )
            db.add(record)
        
        db.commit()
        print(f"✅ 数据已保存到数据库")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 保存失败: {e}")
        raise


async def main():
    """主函数"""
    print("=" * 60)
    print("开始生成副本世界角色预制数据")
    print("=" * 60)
    
    # 加载配置
    config_path = project_root / "config" / "config.yaml"
    if not config_path.exists():
        print(f"错误: 找不到配置文件 {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # 初始化 LLM 服务
    llm = LLMService(config)
    
    db = SessionLocal()
    try:
        # 查询所有启用的世界配置
        worlds = db.query(PromptConfig).filter(
            PromptConfig.type == PromptConfig.TYPE_WORLD,
            PromptConfig.status == 1
        ).all()
        
        print(f"\n找到 {len(worlds)} 个启用的世界")
        
        for world in worlds:
            world_id = world.config_id
            world_name = world.name
            
            print(f"\n{'='*60}")
            print(f"处理世界: {world_name} ({world_id})")
            print(f"{'='*60}")
            
            # 加载世界设定
            world_setting = load_world_setting(world_id, str(project_root))
            
            # 生成 race_appearance (20条)
            print(f"\n1. 生成种族/外貌组合...")
            race_appearance_items = await generate_race_appearance_for_world(
                llm, world_id, world_name, world_setting, count=20
            )
            
            # 生成 gender_personality (男性10条 + 女性10条 = 20条)
            print(f"\n2. 生成男性个性组合...")
            male_items = await generate_gender_personality_for_world(
                llm, world_id, world_name, world_setting, "男性", count=10
            )
            
            print(f"\n3. 生成女性个性组合...")
            female_items = await generate_gender_personality_for_world(
                llm, world_id, world_name, world_setting, "女性", count=10
            )
            
            gender_personality_items = male_items + female_items
            
            # 保存到数据库
            if race_appearance_items and gender_personality_items:
                print(f"\n4. 保存到数据库...")
                await save_to_database(db, world_id, race_appearance_items, gender_personality_items)
                print(f"✅ 世界 {world_name} 预制数据生成完成！")
            else:
                print(f"⚠️ 数据生成不完整，跳过保存")
            
            # 延迟一下，避免API频率限制
            await asyncio.sleep(2)
        
        print(f"\n{'='*60}")
        print("所有世界预制数据生成完成！")
        print(f"{'='*60}")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
