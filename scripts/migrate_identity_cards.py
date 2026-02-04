#!/usr/bin/env python3
"""
身份卡数据迁移脚本
将 data/身份卡 目录下的身份卡文件导入到 t_prompt_config 表
"""
import os
import sys
import re
import yaml
import urllib.parse

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def load_config():
    """加载数据库配置"""
    config_path = os.path.join(project_root, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_db_session():
    """获取数据库会话"""
    config = load_config()
    db_config = config["database"]
    
    encoded_password = urllib.parse.quote(db_config["password"])
    DATABASE_URI = (
        f'mysql+pymysql://{db_config["username"]}:{encoded_password}'
        f'@{db_config["host"]}/{db_config["database_name"]}'
    )
    
    engine = create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def parse_identity_card(file_path: str) -> dict:
    """
    解析身份卡文件
    
    Returns:
        {
            "name": 姓名,
            "gender": 性别,
            "identity": 身份,
            "prompt": 完整内容
        }
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    
    # 提取姓名
    name_match = re.search(r'姓名[：:]\s*(\S+)', content)
    name = name_match.group(1) if name_match else "未知"
    
    # 提取性别
    gender_match = re.search(r'性别[：:]\s*(\S+)', content)
    gender = gender_match.group(1) if gender_match else None
    
    # 提取身份
    identity_match = re.search(r'身份[：:]\s*(.+?)(?:\n|$)', content)
    identity = identity_match.group(1).strip() if identity_match else None
    
    return {
        "name": name,
        "gender": gender,
        "identity": identity,
        "prompt": content
    }


def migrate_identity_cards():
    """迁移身份卡数据到数据库"""
    identity_cards_dir = os.path.join(project_root, "data", "身份卡")
    
    if not os.path.exists(identity_cards_dir):
        print(f"错误：目录不存在 {identity_cards_dir}")
        return
    
    session = get_db_session()
    
    try:
        # 获取所有 txt 文件
        files = sorted([f for f in os.listdir(identity_cards_dir) if f.endswith('.txt')])
        
        print(f"找到 {len(files)} 个身份卡文件")
        
        for filename in files:
            # 从文件名提取 virtual_id
            virtual_id = int(filename.replace('.txt', ''))
            config_id = f"identity_{virtual_id}"
            
            file_path = os.path.join(identity_cards_dir, filename)
            card_data = parse_identity_card(file_path)
            
            print(f"\n处理: {filename}")
            print(f"  - config_id: {config_id}")
            print(f"  - 姓名: {card_data['name']}")
            print(f"  - 性别: {card_data['gender']}")
            print(f"  - 身份: {card_data['identity']}")
            
            # 检查是否已存在
            result = session.execute(
                text("SELECT id FROM t_prompt_config WHERE config_id = :config_id"),
                {"config_id": config_id}
            )
            existing = result.fetchone()
            
            if existing:
                # 更新已存在的记录
                session.execute(
                    text("""
                        UPDATE t_prompt_config 
                        SET name = :name, 
                            gender = :gender, 
                            traits = :traits,
                            prompt = :prompt,
                            updated_at = NOW()
                        WHERE config_id = :config_id
                    """),
                    {
                        "config_id": config_id,
                        "name": card_data["name"],
                        "gender": card_data["gender"],
                        "traits": card_data["identity"],
                        "prompt": card_data["prompt"]
                    }
                )
                print(f"  -> 更新成功")
            else:
                # 插入新记录
                session.execute(
                    text("""
                        INSERT INTO t_prompt_config 
                        (config_id, type, name, gender, traits, prompt, status, sort_order, created_at, updated_at)
                        VALUES 
                        (:config_id, 'identity_card', :name, :gender, :traits, :prompt, 1, :sort_order, NOW(), NOW())
                    """),
                    {
                        "config_id": config_id,
                        "name": card_data["name"],
                        "gender": card_data["gender"],
                        "traits": card_data["identity"],
                        "prompt": card_data["prompt"],
                        "sort_order": virtual_id
                    }
                )
                print(f"  -> 插入成功")
        
        session.commit()
        print(f"\n迁移完成！共处理 {len(files)} 个身份卡")
        
        # 验证结果
        result = session.execute(
            text("SELECT config_id, name, gender FROM t_prompt_config WHERE type = 'identity_card' ORDER BY sort_order")
        )
        rows = result.fetchall()
        print(f"\n数据库中的身份卡 ({len(rows)} 条):")
        for row in rows:
            print(f"  - {row[0]}: {row[1]} ({row[2]})")
        
    except Exception as e:
        session.rollback()
        print(f"迁移失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate_identity_cards()
