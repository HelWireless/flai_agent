"""
异世界 Prompt 配置
支持从数据库加载，文件配置作为 fallback
"""
import os
import json
from typing import Dict, Optional, List
from functools import lru_cache

# 配置文件目录
_CONFIG_DIR = None

# 数据库加载开关（可通过环境变量控制）
USE_DATABASE = os.environ.get("PROMPT_CONFIG_USE_DB", "true").lower() == "true"


def _get_config_dir() -> str:
    """获取配置目录路径"""
    global _CONFIG_DIR
    if _CONFIG_DIR is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        _CONFIG_DIR = os.path.join(project_root, "config", "instance_world")
    return _CONFIG_DIR


def _load_json(filepath: str) -> dict:
    """加载 JSON 文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


# ==================== 数据库加载支持 ====================

def _get_db_session():
    """获取数据库会话（懒加载）"""
    try:
        from ..database import SessionLocal
        if SessionLocal is None:
            return None
        return SessionLocal()
    except Exception:
        return None


def _query_config_by_id(config_id: str):
    """从数据库查询单个配置"""
    if not USE_DATABASE:
        return None
    
    session = _get_db_session()
    if session is None:
        return None
    
    try:
        from ..models.prompt_config import PromptConfig
        result = session.query(PromptConfig).filter(
            PromptConfig.config_id == config_id,
            PromptConfig.status == 1
        ).first()
        return result
    except Exception:
        return None
    finally:
        session.close()


def _query_configs_by_type(config_type: str) -> List:
    """从数据库查询某类型的所有配置"""
    if not USE_DATABASE:
        return []
    
    session = _get_db_session()
    if session is None:
        return []
    
    try:
        from ..models.prompt_config import PromptConfig
        results = session.query(PromptConfig).filter(
            PromptConfig.type == config_type,
            PromptConfig.status == 1
        ).order_by(PromptConfig.sort_order).all()
        return results
    except Exception:
        return []
    finally:
        session.close()


# ==================== 核心 Prompts 加载 ====================

@lru_cache(maxsize=1)
def _load_prompts_config() -> dict:
    """加载核心 prompts 配置（带缓存）"""
    config_dir = _get_config_dir()
    return _load_json(os.path.join(config_dir, "prompts.json"))


def get_style_guide() -> str:
    """获取通用文风指南"""
    return _load_prompts_config().get("style_guide", "")


def get_iw_prompt_op() -> str:
    """获取主流程 prompt"""
    return _load_prompts_config().get("iw_prompt_op", "")


def get_iw_prompt_loading() -> str:
    """获取加载存档 prompt"""
    return _load_prompts_config().get("iw_prompt_loading", "")


def get_iw_prompt_saving() -> str:
    """获取存档格式 prompt"""
    return _load_prompts_config().get("iw_prompt_saving", "")


def get_json_format_instruction() -> str:
    """获取 JSON 格式指令"""
    return _load_prompts_config().get("json_format_instruction", "")


# ==================== GM 配置加载 ====================

def get_gm_config(gm_id: str) -> dict:
    """获取 GM 配置（优先数据库，fallback 文件）
    
    Args:
        gm_id: GM 的 config_id，如 "gm_01"
    """
    # 直接用 config_id 查询数据库
    db_config = _query_config_by_id(gm_id)
    if db_config:
        return db_config.to_gm_dict()
    
    # Fallback 到文件（兼容旧格式，去掉 gm_ 前缀）
    file_id = gm_id.replace("gm_", "") if gm_id.startswith("gm_") else gm_id
    return _load_gm_detail_from_file(file_id)


def _load_gm_detail_from_file(gm_id: str) -> dict:
    """从文件加载单个 GM 详细配置"""
    index = _load_gm_index_from_file()
    if gm_id not in index:
        # 返回默认 GM
        for default_id in index:
            if index[default_id].get("enabled", True):
                return _load_gm_file(default_id, index[default_id])
        return {}
    
    gm_info = index[gm_id]
    if not gm_info.get("enabled", True):
        return {}
    
    return _load_gm_file(gm_id, gm_info)


def _load_gm_file(gm_id: str, gm_info: dict) -> dict:
    """从文件加载 GM"""
    config_dir = _get_config_dir()
    filepath = os.path.join(config_dir, "gm", gm_info.get("file", ""))
    return _load_json(filepath)


@lru_cache(maxsize=1)
def _load_gm_index_from_file() -> dict:
    """从文件加载 GM 索引"""
    config_dir = _get_config_dir()
    return _load_json(os.path.join(config_dir, "gm", "index.json"))


def get_enabled_gms() -> List[dict]:
    """获取所有启用的 GM 列表"""
    # 尝试从数据库加载
    db_configs = _query_configs_by_type('gm')
    if db_configs:
        return [
            {
                "id": c.config_id,  # 直接返回完整 config_id
                "name": c.name,
                "gender": c.gender,
                "traits": c.traits
            }
            for c in db_configs
        ]
    
    # Fallback 到文件
    index = _load_gm_index_from_file()
    gms = []
    for gm_id, info in index.items():
        if info.get("enabled", True):
            detail = _load_gm_file(gm_id, info)
            if detail:
                gms.append({
                    "id": f"gm_{gm_id}",  # 文件模式加前缀保持一致
                    "name": info.get("name", detail.get("name", "")),
                    "gender": info.get("gender", detail.get("gender", "")),
                    "traits": detail.get("traits", "")
                })
    return gms


def get_gm_ids() -> List[str]:
    """获取所有启用的 GM ID 列表（返回完整 config_id）"""
    # 尝试从数据库加载
    db_configs = _query_configs_by_type('gm')
    if db_configs:
        return [c.config_id for c in db_configs]  # 直接返回完整 config_id
    
    # Fallback 到文件
    index = _load_gm_index_from_file()
    return [f"gm_{gm_id}" for gm_id, info in index.items() if info.get("enabled", True)]


# ==================== 世界配置加载 ====================

def get_world_config(world_id: str) -> dict:
    """获取世界基础配置（优先数据库，fallback 文件）
    
    Args:
        world_id: 世界的 config_id，如 "world_01"
    """
    # 直接用 config_id 查询数据库
    db_config = _query_config_by_id(world_id)
    if db_config:
        return db_config.to_world_dict()
    
    # Fallback 到文件（兼容旧格式，去掉 world_ 前缀）
    file_id = world_id.replace("world_", "") if world_id.startswith("world_") else world_id
    return _load_world_detail_from_file(file_id)


def _load_world_detail_from_file(world_id: str) -> dict:
    """从文件加载单个世界详细配置（world_id 为不带前缀的ID）"""
    index = _load_world_index_from_file()
    if world_id not in index:
        # 返回默认世界
        for default_id in index:
            if index[default_id].get("enabled", True):
                return _load_world_file(default_id, index[default_id])
        return {}
    
    world_info = index[world_id]
    if not world_info.get("enabled", True):
        return {}
    
    return _load_world_file(world_id, world_info)


def _load_world_file(world_id: str, world_info: dict) -> dict:
    """从文件加载世界配置"""
    config_dir = _get_config_dir()
    filepath = os.path.join(config_dir, "world", world_info.get("file", ""))
    return _load_json(filepath)


@lru_cache(maxsize=1)
def _load_world_index_from_file() -> dict:
    """从文件加载世界索引"""
    config_dir = _get_config_dir()
    return _load_json(os.path.join(config_dir, "world", "index.json"))


def get_enabled_worlds() -> List[dict]:
    """获取所有启用的世界列表"""
    # 尝试从数据库加载
    db_configs = _query_configs_by_type('world')
    if db_configs:
        return [
            {
                "id": c.config_id,  # 直接返回完整 config_id
                "name": c.name,
                "theme": (c.config or {}).get("theme", c.traits),
                "description": (c.config or {}).get("description", "")
            }
            for c in db_configs
        ]
    
    # Fallback 到文件
    index = _load_world_index_from_file()
    worlds = []
    for world_id, info in index.items():
        if info.get("enabled", True):
            detail = _load_world_file(world_id, info)
            if detail:
                worlds.append({
                    "id": f"world_{world_id}",  # 文件模式加前缀保持一致
                    "name": info.get("name", detail.get("name", "")),
                    "theme": info.get("theme", detail.get("theme", "")),
                    "description": detail.get("description", "")
                })
    return worlds


def get_world_ids() -> List[str]:
    """获取所有启用的世界 ID 列表（返回完整 config_id）"""
    # 尝试从数据库加载
    db_configs = _query_configs_by_type('world')
    if db_configs:
        return [c.config_id for c in db_configs]  # 直接返回完整 config_id
    
    # Fallback 到文件
    index = _load_world_index_from_file()
    return [f"world_{world_id}" for world_id, info in index.items() if info.get("enabled", True)]


def load_world_setting(world_id: str, base_path: str = "") -> str:
    """加载世界完整设定（优先数据库，fallback 文件）
    
    Args:
        world_id: 世界的 config_id，如 "world_01"
    """
    # 直接用 config_id 查询数据库
    db_config = _query_config_by_id(world_id)
    if db_config and db_config.prompt:
        return db_config.prompt
    
    # Fallback 到文件（兼容旧格式，去掉 world_ 前缀）
    file_id = world_id.replace("world_", "") if world_id.startswith("world_") else world_id
    config = _load_world_detail_from_file(file_id)
    if not config:
        return f"世界 {world_id} 配置不存在"
    
    setting_file = config.get("setting_file", "")
    if not setting_file:
        return f"世界 {world_id} 未配置设定文件"
    
    if base_path:
        filepath = os.path.join(base_path, setting_file)
    else:
        config_dir = _get_config_dir()
        project_root = os.path.dirname(os.path.dirname(config_dir))
        filepath = os.path.join(project_root, setting_file)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"世界 {world_id} 配置文件不存在: {filepath}"
    except Exception as e:
        return f"加载世界 {world_id} 配置失败: {str(e)}"


# ==================== 第三方人物配置加载 ====================

def get_character_config(char_id: str) -> Optional[dict]:
    """获取第三方人物配置"""
    # 尝试从数据库加载（人物 ID 直接使用，不加前缀）
    db_config = _query_config_by_id(char_id)
    if db_config:
        return db_config.to_character_dict()
    
    # Fallback: 从 characters.json 加载（未实现，因为主要使用数据库）
    return None


def get_enabled_characters() -> List[dict]:
    """获取所有启用的第三方人物列表"""
    db_configs = _query_configs_by_type('character')
    if db_configs:
        return [
            {
                "id": c.config_id,  # 人物 ID 保持原始格式
                "name": c.name,
                "traits": c.traits.split(',') if c.traits else [],
                "occupation": (c.config or {}).get("occupation", ""),
                "age": (c.config or {}).get("age")
            }
            for c in db_configs
        ]
    return []


def get_character_ids() -> List[str]:
    """获取所有启用的人物 ID 列表"""
    db_configs = _query_configs_by_type('character')
    if db_configs:
        return [c.config_id for c in db_configs]  # 人物 ID 保持原始格式
    return []


# ==================== 工具函数 ====================

def build_system_prompt(
    gm_id: str,
    world_id: str,
    is_loading: bool = False,
    world_setting: str = "",
    base_path: str = "",
    include_json_instruction: bool = False
) -> str:
    """
    构建系统提示词
    
    Args:
        gm_id: GM ID
        world_id: 世界 ID
        is_loading: 是否为加载存档模式
        world_setting: 预加载的世界设定（可选）
        base_path: 项目根目录路径
        include_json_instruction: 是否包含 JSON 格式指令（默认 False，仅在需要 JSON 响应时开启）
    
    Returns:
        组装好的系统提示词
    """
    parts = []
    
    # 1. 通用文风指南
    parts.append(get_style_guide())
    
    # 2. 主流程 prompt（新游戏 vs 加载存档）
    if is_loading:
        parts.append(get_iw_prompt_loading())
    else:
        parts.append(get_iw_prompt_op())
    
    # 3. 存档格式说明
    parts.append(get_iw_prompt_saving())
    
    # 4. GM 配置
    gm_config = get_gm_config(gm_id)
    if gm_config:
        parts.append(f"### GM 引导者设定 ###\n{gm_config.get('prompt', '')}")
    
    # 5. 世界设定
    if world_setting:
        parts.append(f"### 副本世界信息 ###\n{world_setting}")
    else:
        loaded_setting = load_world_setting(world_id, base_path)
        parts.append(f"### 副本世界信息 ###\n{loaded_setting}")
    
    # 6. JSON 格式指令（仅在明确需要时才加入，避免 markdown 步骤被迫返回 JSON）
    if include_json_instruction:
        parts.append(get_json_format_instruction())
    
    return "\n\n---\n\n".join(parts)


def reload_configs():
    """重新加载所有配置（清除缓存）"""
    _load_prompts_config.cache_clear()
    _load_gm_index_from_file.cache_clear()
    _load_world_index_from_file.cache_clear()
