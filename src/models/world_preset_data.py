"""
副本世界预制数据模型
用于存储角色生成的预制组合数据
"""
from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import random

Base = declarative_base()


class WorldRaceAppearance(Base):
    """种族/职业与外貌描述预制组合表"""
    
    __tablename__ = 't_world_race_appearance'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='自增 ID')
    world_id = Column(String(64), nullable=False, index=True, comment='世界 ID，如 world_01')
    race = Column(String(128), nullable=False, comment='种族/职业名称')
    appearance = Column(Text, nullable=False, comment='外貌描述（一句话）')
    status = Column(Integer, nullable=False, default=1, comment='状态：1=启用，0=禁用')
    sort_order = Column(Integer, default=0, comment='排序权重')
    
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 联合索引
    __table_args__ = (
        Index('idx_world_race_status', 'world_id', 'status'),
    )
    
    def __repr__(self):
        return f"<WorldRaceAppearance(world_id={self.world_id}, race={self.race})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "world_id": self.world_id,
            "race": self.race,
            "appearance": self.appearance,
            "status": self.status,
            "sort_order": self.sort_order
        }


class WorldGenderPersonality(Base):
    """性别与个性描述预制组合表"""
    
    __tablename__ = 't_world_gender_personality'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='自增 ID')
    world_id = Column(String(64), nullable=False, index=True, comment='世界 ID，如 world_01')
    gender = Column(String(8), nullable=False, comment='性别：男性/女性')
    personality = Column(Text, nullable=False, comment='个性描述（一句话）')
    status = Column(Integer, nullable=False, default=1, comment='状态：1=启用，0=禁用')
    sort_order = Column(Integer, default=0, comment='排序权重')
    
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 联合索引
    __table_args__ = (
        Index('idx_world_gender_status', 'world_id', 'gender', 'status'),
    )
    
    def __repr__(self):
        return f"<WorldGenderPersonality(world_id={self.world_id}, gender={self.gender})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "world_id": self.world_id,
            "gender": self.gender,
            "personality": self.personality,
            "status": self.status,
            "sort_order": self.sort_order
        }


class WorldCharacterName(Base):
    """角色名字预制池"""
    
    __tablename__ = 't_world_character_names'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='自增 ID')
    world_id = Column(String(64), nullable=False, index=True, comment='世界 ID，如 world_01')
    name = Column(String(32), nullable=False, comment='角色名字')
    gender = Column(String(8), nullable=True, comment='性别倾向：男性/女性/中性（可选）')
    status = Column(Integer, nullable=False, default=1, comment='状态：1=启用，0=禁用')
    sort_order = Column(Integer, default=0, comment='排序权重')
    
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 索引
    __table_args__ = (
        Index('idx_world_name_status', 'world_id', 'status'),
    )
    
    def __repr__(self):
        return f"<WorldCharacterName(world_id={self.world_id}, name={self.name})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "world_id": self.world_id,
            "name": self.name,
            "gender": self.gender,
            "status": self.status,
            "sort_order": self.sort_order
        }


class WorldPresetDataManager:
    """预制数据管理器"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def get_random_race_appearance(self, world_id: str, count: int = 1) -> list:
        """随机获取种族/外貌组合"""
        items = self.db.query(WorldRaceAppearance).filter(
            WorldRaceAppearance.world_id == world_id,
            WorldRaceAppearance.status == 1
        ).all()
        
        if not items:
            return []
        
        # 随机选择
        selected = random.sample(items, min(count, len(items)))
        return [item.to_dict() for item in selected]
    
    def get_random_gender_personality(self, world_id: str, gender: str, count: int = 1) -> list:
        """随机获取性别/个性组合"""
        items = self.db.query(WorldGenderPersonality).filter(
            WorldGenderPersonality.world_id == world_id,
            WorldGenderPersonality.gender == gender,
            WorldGenderPersonality.status == 1
        ).all()
        
        if not items:
            return []
        
        # 随机选择
        selected = random.sample(items, min(count, len(items)))
        return [item.to_dict() for item in selected]
    
    def get_random_name(self, world_id: str, count: int = 1) -> list:
        """随机获取角色名字"""
        items = self.db.query(WorldCharacterName).filter(
            WorldCharacterName.world_id == world_id,
            WorldCharacterName.status == 1
        ).all()
        
        if not items:
            return []
        
        # 随机选择
        selected = random.sample(items, min(count, len(items)))
        return [item.name for item in selected]
    
    def generate_character_combinations(self, world_id: str, gender: str, count: int = 3) -> list:
        """
        生成角色组合（包含名字）
        返回：[{name, race, appearance, gender, personality}, ...]
        """
        # 获取种族/外貌组合
        race_appearances = self.get_random_race_appearance(world_id, count)
        
        # 获取性别/个性组合
        gender_personalities = self.get_random_gender_personality(world_id, gender, count)
        
        # 获取名字池
        names = self.get_random_name(world_id, count)
        
        if not race_appearances or not gender_personalities:
            return []
        
        # 组合生成角色
        characters = []
        for i in range(min(count, len(race_appearances), len(gender_personalities))):
            char = {
                "name": names[i] if i < len(names) else None,  # 名字可能不够，返回 None 让 service 层处理
                "race": race_appearances[i]["race"],
                "appearance": race_appearances[i]["appearance"],
                "gender": gender_personalities[i]["gender"],
                "personality": gender_personalities[i]["personality"]
            }
            characters.append(char)
        
        return characters
