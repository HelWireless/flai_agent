"""
身份卡服务 - 加载和管理虚拟身份卡配置
从 t_prompt_config 表加载 type='identity_card' 的配置
"""
from typing import Dict, Optional, List
from functools import lru_cache

from ..custom_logger import custom_logger


# 数据库加载开关
USE_DATABASE = True


def _get_db_session():
    """获取数据库会话（懒加载）"""
    try:
        from ..database import SessionLocal
        if SessionLocal is None:
            return None
        return SessionLocal()
    except Exception:
        return None


def _query_identity_card_by_id(virtual_id: int) -> Optional[Dict]:
    """
    从数据库查询单个身份卡配置
    
    Args:
        virtual_id: 虚拟身份卡ID（1, 2, 3, 4...）
    
    Returns:
        身份卡配置字典，包含 name, gender, prompt 等
    """
    if not USE_DATABASE or virtual_id <= 0:
        return None
    
    session = _get_db_session()
    if session is None:
        return None
    
    try:
        from ..models.prompt_config import PromptConfig
        config_id = f"identity_{virtual_id}"
        result = session.query(PromptConfig).filter(
            PromptConfig.config_id == config_id,
            PromptConfig.type == 'identity_card',
            PromptConfig.status == 1
        ).first()
        
        if result:
            return {
                "id": virtual_id,
                "config_id": result.config_id,
                "name": result.name,
                "gender": result.gender,
                "prompt": result.prompt,
                "traits": result.traits
            }
        return None
    except Exception as e:
        custom_logger.error(f"Error querying identity card {virtual_id}: {e}")
        return None
    finally:
        session.close()


def _query_all_identity_cards() -> List[Dict]:
    """从数据库查询所有启用的身份卡"""
    if not USE_DATABASE:
        return []
    
    session = _get_db_session()
    if session is None:
        return []
    
    try:
        from ..models.prompt_config import PromptConfig
        results = session.query(PromptConfig).filter(
            PromptConfig.type == 'identity_card',
            PromptConfig.status == 1
        ).order_by(PromptConfig.sort_order).all()
        
        cards = []
        for r in results:
            # 从 config_id 提取 virtual_id
            try:
                vid = int(r.config_id.replace("identity_", ""))
            except ValueError:
                vid = 0
            
            cards.append({
                "id": vid,
                "config_id": r.config_id,
                "name": r.name,
                "gender": r.gender,
                "prompt": r.prompt,
                "traits": r.traits
            })
        return cards
    except Exception as e:
        custom_logger.error(f"Error querying all identity cards: {e}")
        return []
    finally:
        session.close()


def get_identity_card(virtual_id: int) -> Optional[Dict]:
    """
    获取身份卡配置
    
    Args:
        virtual_id: 虚拟身份卡ID
            - 0 或负数：返回 None（表示用户自己）
            - 正整数：返回对应身份卡配置
    
    Returns:
        身份卡配置字典或 None
    """
    if virtual_id <= 0:
        return None
    
    return _query_identity_card_by_id(virtual_id)


def get_all_identity_cards() -> List[Dict]:
    """获取所有启用的身份卡列表"""
    return _query_all_identity_cards()


def get_identity_card_ids() -> List[int]:
    """获取所有启用的身份卡 ID 列表"""
    cards = _query_all_identity_cards()
    return [c["id"] for c in cards if c["id"] > 0]


def build_identity_prompt(virtual_id: int) -> str:
    """
    构建身份卡提示词片段
    
    Args:
        virtual_id: 虚拟身份卡ID
    
    Returns:
        用于注入到 system_prompt 的身份背景描述
        如果 virtual_id <= 0，返回空字符串
    """
    if virtual_id <= 0:
        return ""
    
    card = get_identity_card(virtual_id)
    if not card:
        custom_logger.warning(f"Identity card {virtual_id} not found")
        return ""
    
    # 构建身份背景提示词
    prompt_parts = [
        "\n\n【用户扮演角色】",
        card.get("prompt", ""),
        "\n请注意：用户现在扮演上述角色与你对话，请根据这个身份背景进行互动，角色扮演时要考虑用户所扮演角色的身份、性格和背景。"
    ]
    
    return "\n".join(prompt_parts)
