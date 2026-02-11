#!/usr/bin/env python3
"""
COC 规则迁移脚本
将 COC 规则文件从本地 data/tmp_prompt/克苏鲁 目录迁移到数据库 t_prompt_config 表
"""
import os
import sys
import yaml
import urllib.parse

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.prompt_config import PromptConfig, Base


# COC 规则文件映射
# key: 规则键名（与 coc_service.py 中保持一致）
# value: (文件名, 规则名称, 描述, 排序权重)
COC_RULES_FILES = {
    "gm_rules": ("00-GM全局规则-Op.txt", "GM全局规则-Op", "COC开局用GM规则", 1),
    "gm_rules_load": ("00-GM全局规则 - Load.txt", "GM全局规则-Load", "COC读档用GM规则", 2),
    "gm_list": ("00-GM列表.txt", "GM列表", "可选GM角色列表", 3),
    "investigator_create": ("01-调查员创建.txt", "调查员创建规则", "调查员角色创建流程", 4),
    "investigator_profession": ("01-调查员职业与技能.txt", "调查员职业与技能", "职业和技能列表", 5),
    "system_rules": ("02 - 系统规则.txt", "系统规则", "技能检定、理智、战斗等核心系统", 6),
    "process_rules": ("03-进程规则.txt", "进程规则", "游戏进程推进规则", 7),
    "save_template": ("04-总结存档模板.txt", "存档模板", "总结存档格式模板", 8),
}


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


def load_text_file(filepath: str) -> str:
    """加载文本文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"  [警告] 文件不存在: {filepath}")
        return ""
    except Exception as e:
        print(f"  [错误] 读取文件失败: {filepath} - {e}")
        return ""


def migrate_coc_rules(session, rules_dir: str):
    """迁移 COC 规则到数据库"""
    print("\n=== 迁移 COC 规则 ===")
    print(f"规则目录: {rules_dir}")
    
    count = 0
    skipped = 0
    
    for rule_key, (filename, name, description, sort_order) in COC_RULES_FILES.items():
        # 检查是否已存在
        config_id = f"trpg_01_{rule_key}"
        existing = session.query(PromptConfig).filter(PromptConfig.config_id == config_id).first()
        
        if existing:
            print(f"  [跳过] {config_id} ({name}) 已存在")
            skipped += 1
            continue
        
        # 读取规则文件内容
        filepath = os.path.join(rules_dir, filename)
        content = load_text_file(filepath)
        
        if not content:
            print(f"  [警告] {filename} 内容为空或读取失败，跳过")
            continue
        
        # 创建 COC 规则配置
        rule = PromptConfig.create_coc_rule(
            rule_key=rule_key,
            name=name,
            content=content,
            description=description,
            sort_order=sort_order
        )
        session.add(rule)
        count += 1
        print(f"  [添加] {config_id}: {name} ({len(content)} 字符)")
    
    session.commit()
    print(f"\n  共迁移 {count} 个规则, 跳过 {skipped} 个已存在")
    return count


def list_coc_rules(session):
    """列出数据库中所有 COC 规则"""
    print("\n=== 数据库中的 COC 规则 ===")
    
    rules = session.query(PromptConfig).filter(
        PromptConfig.type == PromptConfig.TYPE_COC_RULE
    ).order_by(PromptConfig.sort_order).all()
    
    if not rules:
        print("  未找到 COC 规则")
        return
    
    for rule in rules:
        content_len = len(rule.prompt) if rule.prompt else 0
        print(f"  - {rule.config_id}: {rule.name} ({content_len} 字符)")


def main():
    """主函数"""
    print("=" * 60)
    print("COC 规则迁移脚本")
    print("=" * 60)
    
    rules_dir = os.path.join(project_root, "data", "tmp_prompt", "克苏鲁")
    
    print(f"项目根目录: {project_root}")
    print(f"规则目录: {rules_dir}")
    
    # 检查规则目录是否存在
    if not os.path.exists(rules_dir):
        print(f"[错误] 规则目录不存在: {rules_dir}")
        return
    
    # 获取数据库会话
    session = get_database_session()
    
    try:
        # 迁移 COC 规则
        count = migrate_coc_rules(session, rules_dir)
        
        # 列出所有 COC 规则
        list_coc_rules(session)
        
        print("\n" + "=" * 60)
        print(f"迁移完成! 共导入 {count} 条 COC 规则")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[错误] 迁移失败: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
