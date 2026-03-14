#!/usr/bin/env python3
"""
Prompt 配置迁移脚本
将现有的 GM、第三方人物、世界配置从 JSON 文件迁移到数据库
"""
import os
import sys
import json
import yaml
import urllib.parse

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.prompt_config import PromptConfig, Base


def load_config():
    """加载数据库配置"""
    config_path = os.path.join(project_root, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_database_session():
    """获取数据库会话"""
    config = load_config()
    db_config = config['database']
    encoded_password = urllib.parse.quote(db_config['password'])
    DATABASE_URI = f"mysql+pymysql://{db_config['username']}:{encoded_password}@{db_config['host']}/{db_config['database_name']}"
    
    engine = create_engine(DATABASE_URI)
    Session = sessionmaker(bind=engine)
    return Session()


def load_json_file(filepath: str) -> dict:
    """加载 JSON 文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  [警告] 文件不存在: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        print(f"  [错误] JSON 解析失败: {filepath} - {e}")
        return {}


def load_text_file(filepath: str) -> str:
    """加载文本文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"  [警告] 文件不存在: {filepath}")
        return ""


def migrate_gms(session, config_dir: str):
    """迁移 GM 配置"""
    print("\n=== 迁移 GM 配置 ===")
    
    gm_dir = os.path.join(config_dir, "instance_world", "gm")
    index_path = os.path.join(gm_dir, "index.json")
    
    index = load_json_file(index_path)
    if not index:
        print("  [跳过] 未找到 GM 索引文件")
        return 0
    
    count = 0
    for gm_id, info in index.items():
        gm_file = os.path.join(gm_dir, info.get("file", ""))
        gm_data = load_json_file(gm_file)
        
        if not gm_data:
            continue
        
        # 检查是否已存在
        config_id = f"gm_{gm_id}"
        existing = session.query(PromptConfig).filter(PromptConfig.config_id == config_id).first()
        if existing:
            print(f"  [跳过] GM {gm_id} ({gm_data.get('name', '')}) 已存在")
            continue
        
        # 创建 GM 配置
        gm = PromptConfig.create_gm(
            gm_id=gm_id,
            name=gm_data.get("name", ""),
            gender=gm_data.get("gender", ""),
            traits=gm_data.get("traits", ""),
            prompt=gm_data.get("prompt", ""),
            sort_order=int(gm_id) if gm_id.isdigit() else 0
        )
        session.add(gm)
        count += 1
        print(f"  [添加] GM {gm_id}: {gm_data.get('name', '')}")
    
    session.commit()
    print(f"  共迁移 {count} 个 GM")
    return count


def migrate_worlds(session, config_dir: str):
    """迁移世界配置"""
    print("\n=== 迁移世界配置 ===")
    
    world_dir = os.path.join(config_dir, "instance_world", "world")
    index_path = os.path.join(world_dir, "index.json")
    
    index = load_json_file(index_path)
    if not index:
        print("  [跳过] 未找到世界索引文件")
        return 0
    
    count = 0
    for world_id, info in index.items():
        world_file = os.path.join(world_dir, info.get("file", ""))
        world_data = load_json_file(world_file)
        
        if not world_data:
            continue
        
        # 检查是否已存在
        config_id = f"world_{world_id}"
        existing = session.query(PromptConfig).filter(PromptConfig.config_id == config_id).first()
        if existing:
            print(f"  [跳过] 世界 {world_id} ({world_data.get('name', '')}) 已存在")
            continue
        
        # 加载世界设定文件内容
        setting_file = world_data.get("setting_file", "")
        setting_content = ""
        if setting_file:
            setting_path = os.path.join(project_root, setting_file)
            setting_content = load_text_file(setting_path)
        
        # 创建世界配置
        world = PromptConfig.create_world(
            world_id=world_id,
            name=world_data.get("name", ""),
            theme=world_data.get("theme", ""),
            setting=setting_content,
            description=world_data.get("description", ""),
            setting_file=setting_file,
            sort_order=int(world_id) if world_id.isdigit() else 0
        )
        session.add(world)
        count += 1
        print(f"  [添加] 世界 {world_id}: {world_data.get('name', '')}")
    
    session.commit()
    print(f"  共迁移 {count} 个世界")
    return count


def migrate_characters(session, prompts_dir: str):
    """迁移第三方人物配置"""
    print("\n=== 迁移第三方人物配置 ===")
    
    characters_path = os.path.join(prompts_dir, "characters.json")
    data = load_json_file(characters_path)
    
    if not data:
        print("  [跳过] 未找到 characters.json")
        return 0
    
    # 获取 characters 字典
    characters = data.get("characters", data)
    
    count = 0
    skipped = 0
    
    for char_id, char_data in characters.items():
        # 跳过非角色配置 (default, fortune_teller_detail 等)
        if not char_id.startswith("c1s1c1_") and char_id not in ["default"]:
            # 检查是否是角色配置（有 name 和 traits_detail 字段）
            if "name" not in char_data or "traits_detail" not in char_data:
                continue
        
        # 跳过 default 等特殊配置
        if char_id in ["default", "fortune_teller_detail", "fortune_teller_summary", 
                       "world_background", "guidance"]:
            continue
        
        # 检查是否已存在（人物 ID 保持原始格式，不加前缀）
        config_id = char_id
        existing = session.query(PromptConfig).filter(PromptConfig.config_id == config_id).first()
        if existing:
            skipped += 1
            continue
        
        # 提取 traits
        traits = char_data.get("traits", [])
        if isinstance(traits, str):
            traits = [traits]
        
        # 创建人物配置
        try:
            character = PromptConfig.create_character(
                char_id=char_id,
                name=char_data.get("name", ""),
                traits=traits,
                traits_detail=char_data.get("traits_detail", ""),
                age=char_data.get("age"),
                occupation=char_data.get("character_occupation"),
                appearance_scene=char_data.get("appearance_scene"),
                summary=char_data.get("summary"),
                rules=char_data.get("rules"),
                world_background=char_data.get("world_background"),
                first_interaction=char_data.get("first_interaction"),
                image_prompt=char_data.get("image_prompt"),
                user_prompt=char_data.get("user_prompt"),
                guest_prompt=char_data.get("guest_prompt"),
                sort_order=count
            )
            session.add(character)
            count += 1
            
            if count % 10 == 0:
                print(f"  [进度] 已处理 {count} 个人物...")
                session.commit()
                
        except Exception as e:
            print(f"  [错误] 处理人物 {char_id} 失败: {e}")
            continue
    
    session.commit()
    print(f"  共迁移 {count} 个人物, 跳过 {skipped} 个已存在")
    return count


def migrate_default_character(session, prompts_dir: str):
    """迁移默认角色 (Pillow/辟璐) 配置"""
    print("\n=== 迁移默认角色配置 ===")
    
    characters_path = os.path.join(prompts_dir, "characters.json")
    data = load_json_file(characters_path)
    
    if not data:
        return 0
    
    characters = data.get("characters", data)
    default_config = characters.get("default", {})
    
    if not default_config:
        print("  [跳过] 未找到默认角色配置")
        return 0
    
    # 检查是否已存在（默认角色保持 "default" ID）
    config_id = "default"
    existing = session.query(PromptConfig).filter(PromptConfig.config_id == config_id).first()
    if existing:
        print("  [跳过] 默认角色已存在")
        return 0
    
    # 创建默认角色配置
    character = PromptConfig(
        config_id=config_id,
        type=PromptConfig.TYPE_CHARACTER,
        name="Pillow (辟璐)",
        gender="female",
        traits="体贴,俏皮,幽默,好奇,傲娇,敏感",
        prompt=default_config.get("user_prompt", ""),
        config={
            "user_prompt": default_config.get("user_prompt"),
            "guest_prompt": default_config.get("guest_prompt")
        },
        status=1,
        sort_order=-1  # 默认角色排序最前
    )
    session.add(character)
    session.commit()
    print("  [添加] 默认角色: Pillow (辟璐)")
    return 1


def main():
    """主函数"""
    print("=" * 60)
    print("Prompt 配置迁移脚本")
    print("=" * 60)
    
    config_dir = os.path.join(project_root, "config")
    prompts_dir = os.path.join(config_dir, "prompts")
    
    print(f"项目根目录: {project_root}")
    print(f"配置目录: {config_dir}")
    
    # 获取数据库会话
    session = get_database_session()
    
    try:
        total = 0
        
        # 1. 迁移 GM 配置
        total += migrate_gms(session, config_dir)
        
        # 2. 迁移世界配置
        total += migrate_worlds(session, config_dir)
        
        # 3. 迁移默认角色
        total += migrate_default_character(session, prompts_dir)
        
        # 4. 迁移第三方人物配置
        total += migrate_characters(session, prompts_dir)
        
        print("\n" + "=" * 60)
        print(f"迁移完成! 共导入 {total} 条配置")
        print("=" * 60)
        
        # 显示统计
        gm_count = session.query(PromptConfig).filter(PromptConfig.type == 'gm').count()
        char_count = session.query(PromptConfig).filter(PromptConfig.type == 'character').count()
        world_count = session.query(PromptConfig).filter(PromptConfig.type == 'world').count()
        
        print(f"\n数据库统计:")
        print(f"  - GM: {gm_count}")
        print(f"  - 第三方人物: {char_count}")
        print(f"  - 世界: {world_count}")
        print(f"  - 总计: {gm_count + char_count + world_count}")
        
    except Exception as e:
        print(f"\n[错误] 迁移失败: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
