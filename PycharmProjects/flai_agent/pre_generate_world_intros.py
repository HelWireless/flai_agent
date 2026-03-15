
import asyncio
import json
import os
import sys
from pathlib import Path

# 将项目根目录添加到 python 路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.database import SessionLocal
from src.models.prompt_config import PromptConfig
from src.services.llm_service import LLMService
from src.services.instance_world_prompts import build_system_prompt, get_gm_config
import yaml

async def pre_generate_world_intros():
    """为数据库中所有启用的世界生成固定背景内容"""
    print("开始预生成世界背景介绍...")
    
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
        
        # 获取一个默认 GM 用于生成（通常用第一个或指定的）
        default_gm = db.query(PromptConfig).filter(
            PromptConfig.type == PromptConfig.TYPE_GM,
            PromptConfig.status == 1
        ).order_by(PromptConfig.sort_order).first()
        
        if not default_gm:
            print("错误: 数据库中没有启用的 GM 配置")
            return
        
        gm_id = default_gm.config_id
        gm_name = default_gm.name
        
        print(f"使用 GM: {gm_name} ({gm_id}) 为 {len(worlds)} 个世界生成背景...")
        
        for world in worlds:
            world_id = world.config_id
            print(f"\n正在处理世界: {world.name} ({world_id})...")
            
            # 检查是否已经有了固定背景
            current_config = world.config or {}
            if current_config.get("fixed_intro"):
                print(f"跳过: 世界 {world.name} 已有固定背景")
                continue
            
            # 构建生成 Prompt
            system_prompt = build_system_prompt(
                gm_id=gm_id,
                world_id=world_id,
                is_loading=False,
                base_path=str(project_root)
            )
            
            try:
                # 调用 LLM 生成 (使用 qwen_turbo 提速)
                print(f"正在调用 LLM 生成 {world.name} 的开场介绍...")
                response = await llm.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "开始"}
                    ],
                    model_pool=["qwen_turbo"],
                    temperature=0.9,
                    top_p=0.85,
                    max_tokens=2048,
                    parse_json=False,
                    response_format="text"
                )
                
                content = response.get("content", "").strip()
                if not content:
                    print(f"警告: LLM 为 {world.name} 返回了空内容")
                    continue
                
                # 清理内容中的 JSON 标记（如果模型输出了的话）
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                # 如果返回的是 JSON 格式，尝试提取 content 字段
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "content" in parsed:
                        content = parsed["content"]
                except:
                    pass
                
                # 更新数据库
                new_config = dict(current_config)
                new_config["fixed_intro"] = content
                world.config = new_config
                
                db.commit()
                print(f"成功: 已为 {world.name} 生成并保存固定背景 (长度: {len(content)})")
                
                # 稍微延迟一下，避免 API 频率限制
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"错误: 为 {world.name} 生成背景时发生异常: {e}")
                db.rollback()

        print("\n所有世界背景预生成任务完成！")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(pre_generate_world_intros())
