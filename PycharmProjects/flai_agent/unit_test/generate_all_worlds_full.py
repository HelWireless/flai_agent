"""
为所有副本世界生成完整的预制数据
包括：
1. 种族/职业与外貌描述
2. 性别与个性描述
3. 姓氏池
4. 名字池（1 字 +2 字）
5. 生成示例角色并导出到 Markdown
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import SessionLocal
from src.models.prompt_config import PromptConfig
from src.models.world_preset_data_optimized import (
    WorldRaceAppearance,
    WorldGenderPersonality,
    WorldSurname,
    WorldGivenName,
    WorldPresetDataManager
)
from src.services.llm_service import LLMService
import yaml


class AllWorldDataGenerator:
    """所有世界的预制数据生成器"""
    
    def __init__(self):
        # 加载配置
        config_path = project_root / "config" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        
        self.llm = LLMService(self.config)
        self.db = SessionLocal()
        
        # 世界风格定义
        self.world_styles = {
            'world_01': {
                'name': '暗湖酒馆·永夜歌谣',
                'style': '西方奇幻 + 深渊神秘',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 36,
                'given_name_count': 54,
            },
            'world_04': {
                'name': '诡秘序列·通灵者游戏',
                'style': '克苏鲁 + 灵异悬疑',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 30,
                'given_name_count': 45,
            },
            'world_06': {
                'name': '废土纪元·最后避难所',
                'style': '末日废土 + 赛博朋克',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 25,
                'given_name_count': 40,
            },
            'world_10': {
                'name': '仙界·我在天庭当社畜',
                'style': '东方仙侠 + 现代职场',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 40,
                'given_name_count': 60,
            },
            'world_13': {
                'name': '怪谈世界·规则类怪谈合集',
                'style': '日式怪谈 + 规则恐怖',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 30,
                'given_name_count': 45,
            },
            'world_17': {
                'name': '永夜帝国·血族王座',
                'style': '哥特吸血鬼 + 宫廷权谋',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 35,
                'given_name_count': 50,
            },
            'world_21': {
                'name': '深渊凝视·旧日回响',
                'style': '克苏鲁神话 + 深海恐惧',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 30,
                'given_name_count': 45,
            },
            'world_23': {
                'name': '晶壁系·多元宇宙',
                'style': 'DND 奇幻 + 多元宇宙',
                'race_count': 20,
                'personality_count': 20,
                'surname_count': 40,
                'given_name_count': 60,
            },
        }
    
    async def generate_race_appearances(self, world_id: str, world_name: str, style: str, count: int) -> list:
        """使用 qwen3_max 生成种族/外貌描述"""
        prompt = f"""为"{world_name}"（风格：{style}）生成{count}个不同的种族/职业及其外貌描述。

要求：
1. 种族/职业要符合{style}风格
2. 外貌描述要生动具体（30-50 字）
3. 每个种族/职业有独特的视觉识别度

格式：种族/职业名称 | 外貌描述

只返回列表，不要其他内容。"""

        try:
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen3_max"],
                temperature=0.85,
                top_p=0.95,
                max_tokens=4096,
                parse_json=False,
                response_format="text",
                timeout=120
            )
            
            content = response.get("content", "")
            results = []
            
            for line in content.split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        race = parts[0].strip()
                        appearance = parts[1].strip()
                        if race and appearance and len(race) > 1 and len(appearance) > 10:
                            results.append({"race": race, "appearance": appearance})
            
            return results[:count]
            
        except Exception as e:
            print(f"生成种族外貌失败：{e}")
            return []
    
    async def generate_gender_personalities(self, world_id: str, world_name: str, style: str, count: int) -> list:
        """使用 qwen3_max 生成性别/个性描述"""
        prompt = f"""为"{world_name}"（风格：{style}）生成男女各{count//2}个不同的个性描述。

要求：
1. 个性要多样化，符合{style}风格
2. 每个个性描述生动具体（20-40 字）
3. 可以加入内心矛盾或反差萌

格式：男性 | 个性描述 或 女性 | 个性描述

只返回列表，不要其他内容。"""

        try:
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen3_max"],
                temperature=0.85,
                top_p=0.95,
                max_tokens=4096,
                parse_json=False,
                response_format="text",
                timeout=120
            )
            
            content = response.get("content", "")
            results = []
            
            for line in content.split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        gender = parts[0].strip()
                        personality = parts[1].strip()
                        if gender in ['男性', '女性'] and personality and len(personality) > 10:
                            results.append({"gender": gender, "personality": personality})
            
            return results
            
        except Exception as e:
            print(f"生成性别个性失败：{e}")
            return []
    
    async def generate_surnames(self, world_id: str, world_name: str, style: str, count: int) -> list:
        """生成姓氏"""
        prompt = f"""为"{world_name}"（风格：{style}）生成{count}个符合该世界特色的姓氏。

要求：
1. 符合{style}风格
2. 可以是中文复姓、西式姓氏、或奇幻风格
3. 1-4 个字为主

格式：姓氏 | 风格标签（如：西方/神秘/贵族等）

只返回列表，不要其他内容。"""

        try:
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen_turbo"],
                temperature=0.9,
                top_p=0.95,
                max_tokens=2048,
                parse_json=False,
                response_format="text",
                timeout=60
            )
            
            content = response.get("content", "")
            results = []
            
            for line in content.split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        surname = parts[0].strip()
                        style_tag = parts[1].strip()
                        if surname and 1 <= len(surname) <= 5:
                            results.append({"surname": surname, "style": style_tag})
            
            return results[:count]
            
        except Exception as e:
            print(f"生成姓氏失败：{e}")
            return []
    
    async def generate_given_names(self, world_id: str, world_name: str, style: str, count: int) -> tuple:
        """生成名字（分 1 字和 2 字）"""
        prompt_1char = f"""为"{world_name}"（风格：{style}）生成{count//3}个 1 字名字。

要求：
1. 符合{style}风格
2. 分男性、女性、中性三类
3. 每行格式：名字 | 性别倾向（男性/女性/中性）| 风格标签

只返回列表，不要其他内容。"""

        prompt_2char = f"""为"{world_name}"（风格：{style}）生成{count*2//3}个 2 字名字。

要求：
1. 符合{style}风格
2. 分男性、女性、中性三类
3. 每行格式：名字 | 性别倾向（男性/女性/中性）| 风格标签

只返回列表，不要其他内容。"""

        names_1char = []
        names_2char = []
        
        try:
            # 生成 1 字名
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt_1char}],
                model_pool=["qwen_turbo"],
                temperature=0.9,
                top_p=0.95,
                max_tokens=2048,
                parse_json=False,
                response_format="text",
                timeout=60
            )
            
            content = response.get("content", "")
            for line in content.split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        gender = parts[1].strip()
                        style_tag = parts[2].strip()
                        if name and len(name) == 1:
                            names_1char.append({
                                "given_name": name,
                                "character_count": 1,
                                "gender_tendency": gender,
                                "style": style_tag
                            })
            
            # 生成 2 字名
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt_2char}],
                model_pool=["qwen_turbo"],
                temperature=0.9,
                top_p=0.95,
                max_tokens=2048,
                parse_json=False,
                response_format="text",
                timeout=60
            )
            
            content = response.get("content", "")
            for line in content.split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        gender = parts[1].strip()
                        style_tag = parts[2].strip()
                        if name and len(name) == 2:
                            names_2char.append({
                                "given_name": name,
                                "character_count": 2,
                                "gender_tendency": gender,
                                "style": style_tag
                            })
            
            return names_1char, names_2char
            
        except Exception as e:
            print(f"生成名字失败：{e}")
            return [], []
    
    def save_to_database(self, world_id: str, race_data: list, gender_data: list, 
                        surname_data: list, given_names_1char: list, given_names_2char: list):
        """保存数据到数据库"""
        try:
            # 清空旧数据
            self.db.query(WorldRaceAppearance).filter(WorldRaceAppearance.world_id == world_id).delete()
            self.db.query(WorldGenderPersonality).filter(WorldGenderPersonality.world_id == world_id).delete()
            self.db.query(WorldSurname).filter(WorldSurname.world_id == world_id).delete()
            self.db.query(WorldGivenName).filter(WorldGivenName.world_id == world_id).delete()
            
            # 插入种族/外貌
            for i, item in enumerate(race_data):
                record = WorldRaceAppearance(
                    world_id=world_id,
                    race=item['race'],
                    appearance=item['appearance'],
                    status=1,
                    sort_order=i
                )
                self.db.add(record)
            
            # 插入性别/个性
            for i, item in enumerate(gender_data):
                record = WorldGenderPersonality(
                    world_id=world_id,
                    gender=item['gender'],
                    personality=item['personality'],
                    status=1,
                    sort_order=i
                )
                self.db.add(record)
            
            # 插入姓氏
            for i, item in enumerate(surname_data):
                record = WorldSurname(
                    world_id=world_id,
                    surname=item['surname'],
                    style=item['style'],
                    status=1,
                    sort_order=i
                )
                self.db.add(record)
            
            # 插入 1 字名
            for i, item in enumerate(given_names_1char):
                record = WorldGivenName(
                    world_id=world_id,
                    given_name=item['given_name'],
                    character_count=item['character_count'],
                    gender_tendency=item['gender_tendency'],
                    style=item['style'],
                    status=1,
                    sort_order=i
                )
                self.db.add(record)
            
            # 插入 2 字名
            offset = len(given_names_1char)
            for i, item in enumerate(given_names_2char):
                record = WorldGivenName(
                    world_id=world_id,
                    given_name=item['given_name'],
                    character_count=item['character_count'],
                    gender_tendency=item['gender_tendency'],
                    style=item['style'],
                    status=1,
                    sort_order=offset + i
                )
                self.db.add(record)
            
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"保存到数据库失败：{e}")
            return False
    
    def generate_sample_characters(self, world_id: str, world_name: str, count: int = 5) -> list:
        """生成示例角色"""
        preset_manager = WorldPresetDataManager(self.db)
        characters = []
        
        # 生成男性角色
        male_chars = preset_manager.generate_character_combinations(world_id, "male", count//2 + 1)
        for char in male_chars:
            char['world_name'] = world_name
            characters.append(char)
        
        # 生成女性角色
        female_chars = preset_manager.generate_character_combinations(world_id, "female", count//2 + 1)
        for char in female_chars:
            char['world_name'] = world_name
            characters.append(char)
        
        return characters[:count]
    
    async def generate_for_all_worlds(self):
        """为所有世界生成数据"""
        print("=" * 80)
        print("开始为所有副本世界生成预制数据...")
        print("=" * 80)
        
        all_characters = []
        
        for idx, (world_id, world_info) in enumerate(self.world_styles.items(), 1):
            world_name = world_info['name']
            style = world_info['style']
            
            print(f"\n{'='*80}")
            print(f"[{idx}/{len(self.world_styles)}] {world_name} ({world_id})")
            print(f"风格：{style}")
            print(f"{'='*80}")
            
            try:
                # 1. 生成种族/外貌
                print(f"\n[STEP 1] 生成种族/职业与外貌描述（{world_info['race_count']}条）...")
                race_data = await self.generate_race_appearances(
                    world_id, world_name, style, world_info['race_count']
                )
                print(f"   [OK] 生成了 {len(race_data)} 条")
                
                # 2. 生成性别/个性
                print(f"\n[STEP 2] 生成性别与个性描述（{world_info['personality_count']}条）...")
                gender_data = await self.generate_gender_personalities(
                    world_id, world_name, style, world_info['personality_count']
                )
                print(f"   [OK] 生成了 {len(gender_data)} 条")
                
                # 3. 生成姓氏
                print(f"\n[STEP 3] 生成姓氏池（{world_info['surname_count']}个）...")
                surname_data = await self.generate_surnames(
                    world_id, world_name, style, world_info['surname_count']
                )
                print(f"   [OK] 生成了 {len(surname_data)} 个姓氏")
                
                # 4. 生成名字
                print(f"\n[STEP 4] 生成名字池（{world_info['given_name_count']}个）...")
                given_names_1char, given_names_2char = await self.generate_given_names(
                    world_id, world_name, style, world_info['given_name_count']
                )
                print(f"   [OK] 生成了 {len(given_names_1char)} 个 1 字名 + {len(given_names_2char)} 个 2 字名")
                
                # 5. 保存到数据库
                print(f"\n[STEP 5] 保存到数据库...")
                if self.save_to_database(world_id, race_data, gender_data, surname_data, 
                                       given_names_1char, given_names_2char):
                    print(f"   [OK] 保存成功")
                else:
                    print(f"   [ERROR] 保存失败")
                    continue
                
                # 6. 生成示例角色
                print(f"\n[STEP 6] 生成示例角色...")
                sample_chars = self.generate_sample_characters(world_id, world_name, 5)
                all_characters.extend(sample_chars)
                print(f"   [OK] 生成了 {len(sample_chars)} 个示例角色")
                
                # 等待一下，避免 API 限流
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"\n[ERROR] {world_name} 生成失败：{e}")
        
        # 生成 Markdown 报告
        print(f"\n{'='*80}")
        print("生成 Markdown 报告...")
        print(f"{'='*80}")
        self.generate_markdown_report(all_characters)
        
        print(f"\n{'='*80}")
        print("[SUCCESS] 所有世界预制数据生成完成！")
        print(f"{'='*80}\n")
    
    def generate_markdown_report(self, characters: list):
        """生成 Markdown 格式的角色展示报告"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        md_content = f"""# 副本世界角色生成报告

**生成时间**: {timestamp}  
**生成模型**: qwen3_max（背景、种族、个性） + qwen_turbo（名字）  
**总计**: {len(characters)} 个示例角色

---

## 世界列表

"""
        
        # 按世界分组
        world_groups = {}
        for char in characters:
            world_name = char.get('world_name', '未知世界')
            if world_name not in world_groups:
                world_groups[world_name] = []
            world_groups[world_name].append(char)
        
        for world_name, chars in world_groups.items():
            md_content += f"### [{world_name}]\n\n"
            md_content += f"**角色数量**: {len(chars)}\n\n"
            
            for i, char in enumerate(chars, 1):
                full_name = char.get('full_name', '无名')
                race = char.get('race', '未知种族')
                appearance = char.get('appearance', '')
                personality = char.get('personality', '')
                gender = char.get('gender', '')
                
                md_content += f"""#### 角色 {i}: **{full_name}**

| 属性 | 描述 |
|------|------|
| **性别** | {gender} |
| **种族/职业** | {race} |
| **外貌描述** | {appearance} |
| **个性特点** | {personality} |

---

"""
        
        # 统计数据
        md_content += f"""## 统计信息

- **总角色数**: {len(characters)}
- **世界数量**: {len(world_groups)}
- **平均每个世界**: {len(characters)/len(world_groups):.1f} 个角色

---

*本报告由 AI 自动生成，所有角色数据已存入数据库可供调用*
"""
        
        # 保存文件
        output_path = project_root / "unit_test" / "generated_characters_report.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"[OK] Markdown 报告已保存至：{output_path}")


async def main():
    """主函数"""
    generator = AllWorldDataGenerator()
    await generator.generate_for_all_worlds()


if __name__ == "__main__":
    asyncio.run(main())
