"""
配置加载器 - 支持JSON配置的加载和热更新
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache
import time


class ConfigLoader:
    """配置加载器，支持缓存和热更新"""
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            # 默认配置目录
            config_dir = Path(__file__).parent.parent.parent / "config" / "prompts"
        self.config_dir = Path(config_dir)
        self._cache = {}
        self._file_mtimes = {}
    
    def _load_json(self, filename: str) -> Dict[str, Any]:
        """加载JSON文件"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _check_file_modified(self, filename: str) -> bool:
        """检查文件是否被修改"""
        filepath = self.config_dir / filename
        current_mtime = filepath.stat().st_mtime
        
        if filename not in self._file_mtimes:
            self._file_mtimes[filename] = current_mtime
            return True
        
        if current_mtime > self._file_mtimes[filename]:
            self._file_mtimes[filename] = current_mtime
            return True
        
        return False
    
    def get(self, config_name: str, reload: bool = False) -> Dict[str, Any]:
        """
        获取配置
        
        Args:
            config_name: 配置名称 (不含.json后缀)
            reload: 是否强制重新加载
        
        Returns:
            配置字典
        """
        filename = f"{config_name}.json"
        
        # 检查是否需要重新加载
        if reload or config_name not in self._cache or self._check_file_modified(filename):
            self._cache[config_name] = self._load_json(filename)
        
        return self._cache[config_name]
    
    def get_characters(self, reload: bool = False) -> Dict[str, Any]:
        """获取角色配置"""
        return self.get('characters', reload)
    
    def get_character_openers(self, reload: bool = False) -> Dict[str, list]:
        """获取角色开场白配置"""
        return self.get('character_openers', reload)
    
    def get_emotions(self, reload: bool = False) -> Dict[str, Any]:
        """获取情绪配置"""
        return self.get('emotions', reload)
    
    def get_responses(self, reload: bool = False) -> Dict[str, list]:
        """获取回复配置"""
        return self.get('responses', reload)
    
    def get_constants(self, reload: bool = False) -> Dict[str, Any]:
        """获取常量配置"""
        return self.get('constants', reload)
    
    def reload_all(self):
        """重新加载所有配置"""
        self._cache.clear()
        self._file_mtimes.clear()


# 全局配置加载器实例
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """获取全局配置加载器实例"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


# 便捷函数
def get_character_config(character_id: str, reload: bool = False) -> Dict[str, Any]:
    """获取指定角色的配置"""
    loader = get_config_loader()
    characters = loader.get_characters(reload)
    return characters.get('characters', {}).get(character_id, {})


def get_character_opener(character_id: str, reload: bool = False) -> list:
    """获取指定角色的开场白"""
    loader = get_config_loader()
    openers = loader.get_character_openers(reload)
    return openers.get(character_id, [])


def get_world_background(reload: bool = False) -> str:
    """获取世界背景"""
    loader = get_config_loader()
    characters = loader.get_characters(reload)
    return characters.get('world_background', '')


def get_guidance(reload: bool = False) -> str:
    """获取引导提示"""
    loader = get_config_loader()
    characters = loader.get_characters(reload)
    return characters.get('guidance', '')

