#!/usr/bin/env python3
"""
克苏鲁跑团 GM 配置迁移脚本
将 GM 列表从文本文件迁移到 t_prompt_config 数据库表
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


# 克苏鲁跑团 GM 数据
COC_GMS = [
    # 女性GM (5位)
    {
        "config_id": "coc_gm_li",
        "name": "璃",
        "gender": "female",
        "traits": '冷静中带着利落感，说话逻辑清晰、不拖沓；气质凝练如淬过的银刃，自带距离感却不冷漠；机警度高，能快速捕捉环境细节，引导时会隐含"风险提示"般的细致。',
        "sort_order": 1
    },
    {
        "config_id": "coc_gm_yan",
        "name": "焰",
        "gender": "female",
        "traits": "自信飒爽，行事干脆利落；大气温柔，待人有包容感；聪慧机敏，能精准捕捉用户需求，引导时逻辑清晰且不失温度。",
        "sort_order": 2
    },
    {
        "config_id": "coc_gm_dong",
        "name": "鸫",
        "gender": "female",
        "traits": '说话元气满满，热情得会主动分享小细节，眼睛像含着光；清纯感体现在语气的"无防备"，会用可爱比喻，容易让用户放松。',
        "sort_order": 3
    },
    {
        "config_id": "coc_gm_ai",
        "name": "霭",
        "gender": "female",
        "traits": '神秘深邃，成熟娴静，说话语速偏慢，像裹着一层薄雾；魅惑感体现在低柔的语调与偶尔的眼神暗示（文字中用"指尖轻划""眼尾微挑"等动作描述）；天然呆体现在偶尔"忘词"或"搞错细节"，会轻轻笑自己。',
        "sort_order": 4
    },
    {
        "config_id": "coc_gm_su",
        "name": "苏",
        "gender": "female",
        "traits": '青春四射，清纯活泼，说话会有点结巴或小声，尤其提到"可爱""有趣"的事时；青春感体现在喜欢用"同学""小伙伴"类词汇，会分享小八卦；羞涩时会有一些小动作，需要用文字描述，亲和力拉满。',
        "sort_order": 5
    },
    # 男性GM (3位)
    {
        "config_id": "coc_gm_zhu",
        "name": "筑",
        "gender": "male",
        "traits": '气质沉静，稳重成熟，说话语调平稳，像坚实的地基；稳重感体现在"提前考虑风险""清晰规划流程"；让人安心的点在于会主动说"有我在" "别担心"，传递可靠感。',
        "sort_order": 6
    },
    {
        "config_id": "coc_gm_huai",
        "name": "淮",
        "gender": "male",
        "traits": '潇洒风流，放荡不羁，大气随性，说话带江湖气，像仗剑走天涯的侠客；潇洒感体现在"不纠结细节""随遇而安"；大气随性的点在于会说"跟着感觉走""不用拘谨"，让用户放松。',
        "sort_order": 7
    },
    {
        "config_id": "coc_gm_duo",
        "name": "铎",
        "gender": "male",
        "traits": '阳光活力，纯情温和，干劲满满，说话像刚晒过太阳，带着暖意；阳光感体现在"主动分享快乐""积极乐观"；纯情温和的点在于被感谢时会不好意思会脸红（文字描述），干劲满满体现在"提前做准备""主动帮忙"。',
        "sort_order": 8
    },
]


def load_gm_system_prompt() -> str:
    """加载 GM 系统 prompt"""
    prompt_path = os.path.join(project_root, "data", "tmp_prompt", "克苏鲁", "00-GM全局规则-Op.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"  [警告] GM 系统 prompt 文件不存在: {prompt_path}")
        return ""


def migrate_coc_gms():
    """迁移克苏鲁跑团 GM 配置"""
    print("\n=== 开始迁移克苏鲁跑团 GM 配置 ===\n")
    
    session = get_database_session()
    system_prompt = load_gm_system_prompt()
    
    imported_count = 0
    updated_count = 0
    
    for gm in COC_GMS:
        config_id = gm["config_id"]
        
        # 检查是否已存在
        existing = session.query(PromptConfig).filter(
            PromptConfig.config_id == config_id
        ).first()
        
        if existing:
            # 更新现有记录
            existing.name = gm["name"]
            existing.gender = gm["gender"]
            existing.traits = gm["traits"]
            existing.prompt = system_prompt
            existing.sort_order = gm["sort_order"]
            existing.config = json.dumps({
                "role": "gm",
                "game": "coc",
                "personality": gm["traits"][:100]
            })
            updated_count += 1
            print(f"  [更新] {gm['name']} ({config_id})")
        else:
            # 创建新记录
            prompt_config = PromptConfig(
                config_id=config_id,
                type="coc_gm",
                name=gm["name"],
                gender=gm["gender"],
                traits=gm["traits"],
                prompt=system_prompt,
                config=json.dumps({
                    "role": "gm",
                    "game": "coc",
                    "personality": gm["traits"][:100]
                }),
                status=1,
                sort_order=gm["sort_order"]
            )
            session.add(prompt_config)
            imported_count += 1
            print(f"  [新增] {gm['name']} ({config_id})")
    
    session.commit()
    session.close()
    
    print(f"\n=== 迁移完成 ===")
    print(f"新增: {imported_count} 条")
    print(f"更新: {updated_count} 条")
    print(f"总计: {len(COC_GMS)} 条 GM 配置\n")


def query_coc_gms():
    """查询已迁移的 GM 配置"""
    print("\n=== 查询克苏鲁跑团 GM 配置 ===\n")
    
    session = get_database_session()
    
    gms = session.query(PromptConfig).filter(
        PromptConfig.type == "coc_gm",
        PromptConfig.status == 1
    ).order_by(PromptConfig.sort_order).all()
    
    print(f"找到 {len(gms)} 条 GM 配置:\n")
    
    for gm in gms:
        print(f"  ID: {gm.config_id}")
        print(f"  名称: {gm.name}")
        print(f"  性别: {gm.gender}")
        print(f"  特质: {gm.traits[:50]}...")
        print()
    
    session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="克苏鲁跑团 GM 配置迁移工具")
    parser.add_argument("--query", action="store_true", help="查询已迁移的配置")
    
    args = parser.parse_args()
    
    if args.query:
        query_coc_gms()
    else:
        migrate_coc_gms()
