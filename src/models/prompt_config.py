"""
Prompt 配置数据模型
统一存储 GM、第三方人物、世界配置
"""
from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, JSON, SmallInteger
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from typing import Dict, List, Optional, Any

Base = declarative_base()


class PromptConfig(Base):
    """Prompt 配置统一表模型"""
    
    __tablename__ = 't_prompt_config'
    
    # 类型常量
    TYPE_GM = 'gm'
    TYPE_CHARACTER = 'character'
    TYPE_WORLD = 'world'
    TYPE_COC_RULE = 'coc_rule'  # COC 规则类型
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='自增ID')
    config_id = Column(String(64), nullable=False, unique=True, index=True, comment='配置ID')
    type = Column(String(16), nullable=False, index=True, comment='类型: gm/character/world')
    name = Column(String(128), nullable=False, comment='名称')
    gender = Column(String(8), nullable=True, comment='性别')
    traits = Column(String(1024), nullable=True, comment='特质描述')
    prompt = Column(Text, nullable=True, comment='主 prompt 内容')
    config = Column(JSON, nullable=True, comment='类型特有配置 JSON')
    status = Column(SmallInteger, nullable=False, default=1, index=True, comment='状态: 1=启用, 0=禁用')
    sort_order = Column(Integer, default=0, comment='排序权重')
    
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    def __repr__(self):
        return f"<PromptConfig(config_id={self.config_id}, type={self.type}, name={self.name})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "config_id": self.config_id,
            "type": self.type,
            "name": self.name,
            "gender": self.gender,
            "traits": self.traits,
            "prompt": self.prompt,
            "config": self.config or {},
            "status": self.status,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_gm_dict(self) -> dict:
        """转换为 GM 配置格式（兼容现有代码）"""
        return {
            "id": self.config_id.replace("gm_", ""),
            "name": self.name,
            "gender": self.gender,
            "traits": self.traits,
            "prompt": self.prompt
        }
    
    def to_character_dict(self) -> dict:
        """转换为第三方人物配置格式（兼容现有代码）"""
        config = self.config or {}
        # traits 存储为逗号分隔的字符串，转换为数组
        traits_list = self.traits.split(',') if self.traits else []
        
        return {
            "id": self.config_id,  # 人物 ID 保持原始格式
            "name": self.name,
            "traits": traits_list,
            "traits_detail": self.prompt,
            "age": config.get("age"),
            "character_occupation": config.get("occupation"),
            "appearance_scene": config.get("appearance_scene"),
            "summary": config.get("summary"),
            "rules": config.get("rules"),
            "world_background": config.get("world_background"),
            "first_interaction": config.get("first_interaction"),
            "image_prompt": config.get("image_prompt"),
            "user_prompt": config.get("user_prompt"),
            "guest_prompt": config.get("guest_prompt")
        }
    
    def to_world_dict(self) -> dict:
        """转换为世界配置格式（兼容现有代码）"""
        config = self.config or {}
        return {
            "id": self.config_id.replace("world_", ""),
            "name": self.name,
            "theme": config.get("theme", self.traits),
            "description": config.get("description", ""),
            "setting": self.prompt,  # 世界设定内容
            "setting_file": config.get("setting_file")
        }
    
    @classmethod
    def create_gm(
        cls,
        gm_id: str,
        name: str,
        gender: str,
        traits: str,
        prompt: str,
        sort_order: int = 0
    ) -> 'PromptConfig':
        """创建 GM 配置实例"""
        return cls(
            config_id=f"gm_{gm_id}",
            type=cls.TYPE_GM,
            name=name,
            gender=gender,
            traits=traits,
            prompt=prompt,
            config={},
            status=1,
            sort_order=sort_order
        )
    
    @classmethod
    def create_character(
        cls,
        char_id: str,
        name: str,
        traits: List[str],
        traits_detail: str,
        age: Optional[int] = None,
        occupation: Optional[str] = None,
        appearance_scene: Optional[str] = None,
        summary: Optional[str] = None,
        rules: Optional[str] = None,
        world_background: Optional[str] = None,
        first_interaction: Optional[str] = None,
        image_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        guest_prompt: Optional[str] = None,
        sort_order: int = 0
    ) -> 'PromptConfig':
        """创建第三方人物配置实例"""
        config = {
            "age": age,
            "occupation": occupation,
            "appearance_scene": appearance_scene,
            "summary": summary,
            "rules": rules,
            "world_background": world_background,
            "first_interaction": first_interaction,
            "image_prompt": image_prompt,
            "user_prompt": user_prompt,
            "guest_prompt": guest_prompt
        }
        # 移除 None 值
        config = {k: v for k, v in config.items() if v is not None}
        
        return cls(
            config_id=char_id,  # 人物 ID 保持原始格式，不加前缀
            type=cls.TYPE_CHARACTER,
            name=name,
            gender=None,  # 第三方人物性别从配置推断
            traits=','.join(traits) if traits else None,
            prompt=traits_detail,
            config=config,
            status=1,
            sort_order=sort_order
        )
    
    @classmethod
    def create_world(
        cls,
        world_id: str,
        name: str,
        theme: str,
        setting: str,
        description: Optional[str] = None,
        setting_file: Optional[str] = None,
        sort_order: int = 0
    ) -> 'PromptConfig':
        """创建世界配置实例"""
        config = {
            "theme": theme,
            "description": description,
            "setting_file": setting_file
        }
        config = {k: v for k, v in config.items() if v is not None}
        
        return cls(
            config_id=f"world_{world_id}",
            type=cls.TYPE_WORLD,
            name=name,
            gender=None,
            traits=theme,  # 将 theme 存入 traits 便于查询
            prompt=setting,
            config=config,
            status=1,
            sort_order=sort_order
        )
    
    @classmethod
    def create_coc_rule(
        cls,
        rule_key: str,
        name: str,
        content: str,
        description: Optional[str] = None,
        sort_order: int = 0
    ) -> 'PromptConfig':
        """创建 COC 规则配置实例
        
        Args:
            rule_key: 规则键名，如 gm_rules, system_rules 等
            name: 规则名称，如 "GM全局规则-Op"
            content: 规则内容（prompt 字段存储）
            description: 规则描述
            sort_order: 排序权重
        """
        config = {
            "description": description
        } if description else {}
        
        return cls(
            config_id=f"trpg_01_{rule_key}",  # 使用 trpg_01_ 前缀
            type=cls.TYPE_COC_RULE,
            name=name,
            gender=None,
            traits=rule_key,  # 存储规则键名便于查询
            prompt=content,
            config=config,
            status=1,
            sort_order=sort_order
        )
    
    def to_coc_rule_dict(self) -> dict:
        """转换为 COC 规则格式"""
        return {
            "key": self.traits,  # 规则键名
            "name": self.name,
            "content": self.prompt,
            "description": (self.config or {}).get("description")
        }
