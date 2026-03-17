"""
副本世界预制数据模型 - 优化版
支持姓 + 名组合，按世界特色分类
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


class WorldSurname(Base):
    """姓氏预制池 - 按世界分类"""
    
    __tablename__ = 't_world_surnames'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='自增 ID')
    world_id = Column(String(64), nullable=False, index=True, comment='世界 ID，如 world_01')
    surname = Column(String(16), nullable=False, comment='姓氏（中文 1-3 字或外文）')
    style = Column(String(32), nullable=True, comment='风格标签：东方/西方/奇幻/神秘等')
    status = Column(Integer, nullable=False, default=1, comment='状态：1=启用，0=禁用')
    sort_order = Column(Integer, default=0, comment='排序权重')
    
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 索引
    __table_args__ = (
        Index('idx_world_surname_status', 'world_id', 'status'),
    )
    
    def __repr__(self):
        return f"<WorldSurname(world_id={self.world_id}, surname={self.surname})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "world_id": self.world_id,
            "surname": self.surname,
            "style": self.style,
            "status": self.status,
            "sort_order": self.sort_order
        }


class WorldGivenName(Base):
    """名字预制池 - 按世界和字数分类"""
    
    __tablename__ = 't_world_given_names'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='自增 ID')
    world_id = Column(String(64), nullable=False, index=True, comment='世界 ID，如 world_01')
    given_name = Column(String(16), nullable=False, comment='名字（不含姓）')
    character_count = Column(Integer, nullable=False, default=1, comment='字数：1 或 2')
    gender_tendency = Column(String(8), nullable=True, comment='性别倾向：男性/女性/中性')
    style = Column(String(32), nullable=True, comment='风格标签：优雅/霸气/温柔等')
    status = Column(Integer, nullable=False, default=1, comment='状态：1=启用，0=禁用')
    sort_order = Column(Integer, default=0, comment='排序权重')
    
    created_at = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    
    # 索引
    __table_args__ = (
        Index('idx_world_given_status', 'world_id', 'status'),
    )
    
    def __repr__(self):
        return f"<WorldGivenName(world_id={self.world_id}, given_name={self.given_name})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "world_id": self.world_id,
            "given_name": self.given_name,
            "character_count": self.character_count,
            "gender_tendency": self.gender_tendency,
            "style": self.style,
            "status": self.status,
            "sort_order": self.sort_order
        }


class WorldPresetDataManager:
    """预制数据管理器 - 优化版"""
    
    GENDER_MAP = {
        'male': '男性',
        'female': '女性',
        '男性': '男性',
        '女性': '女性',
    }
    
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
    
    def get_random_surname(self, world_id: str, count: int = 1) -> list:
        """随机获取姓氏"""
        items = self.db.query(WorldSurname).filter(
            WorldSurname.world_id == world_id,
            WorldSurname.status == 1
        ).all()
        
        if not items:
            return []
        
        # 随机选择
        selected = random.sample(items, min(count, len(items)))
        return [item.surname for item in selected]
    
    def get_random_given_name(self, world_id: str, character_count: int = None, 
                             gender_tendency: str = None, count: int = 1) -> list:
        """
        随机获取名字
        
        Args:
            world_id: 世界 ID
            character_count: 字数（1 或 2），None 表示随机
            gender_tendency: 性别倾向，None 表示随机
            count: 获取数量
        """
        query = self.db.query(WorldGivenName).filter(
            WorldGivenName.world_id == world_id,
            WorldGivenName.status == 1
        )
        
        # 可选过滤条件
        if character_count is not None:
            query = query.filter(WorldGivenName.character_count == character_count)
        
        if gender_tendency is not None:
            query = query.filter(WorldGivenName.gender_tendency == gender_tendency)
        
        items = query.all()
        
        if not items:
            # 如果没有符合条件的，返回所有
            items = self.db.query(WorldGivenName).filter(
                WorldGivenName.world_id == world_id,
                WorldGivenName.status == 1
            ).all()
        
        if not items:
            return []
        
        # 随机选择
        selected = random.sample(items, min(count, len(items)))
        return [item.given_name for item in selected]
    
    def generate_full_name(self, world_id: str, gender: str = None) -> str:
        """
        生成完整姓名（姓 + 名）
        
        Args:
            world_id: 世界 ID
            gender: 性别（用于选择名字倾向）
            
        Returns:
            完整的姓名
        """
        # 获取姓氏
        surnames = self.get_random_surname(world_id, 1)
        if not surnames:
            return None
        
        surname = surnames[0]
        
        # 根据性别决定名字倾向
        gender_tendency = self.GENDER_MAP.get(gender) if gender else None
        
        # 随机决定是 1 字还是 2 字名（70% 概率 2 字，30% 概率 1 字）
        import random
        character_count = 2 if random.random() < 0.7 else 1
        
        # 获取名字
        given_names = self.get_random_given_name(
            world_id, 
            character_count=character_count,
            gender_tendency=gender_tendency,
            count=1
        )
        
        if not given_names:
            return surname  # 如果没找到名字，只返回姓
        
        return surname + given_names[0]
    
    def generate_character_combinations(self, world_id: str, gender: str, count: int = 3) -> list:
        """
        生成角色组合（包含完整姓名）
        返回：[{full_name, race, appearance, gender, personality}, ...]
        gender 参数支持 'male'/'female' 或 '男性'/'女性'
        """
        # 统一性别映射
        db_gender = self.GENDER_MAP.get(gender, gender)
        
        # 获取种族/外貌组合
        race_appearances = self.get_random_race_appearance(world_id, count)
        
        # 获取性别/个性组合
        gender_personalities = self.get_random_gender_personality(world_id, db_gender, count)
        
        if not race_appearances or not gender_personalities:
            return []
        
        # 组合生成角色
        characters = []
        for i in range(min(count, len(race_appearances), len(gender_personalities))):
            # 生成完整姓名
            full_name = self.generate_full_name(world_id, gender)
            
            char = {
                "full_name": full_name,
                "race": race_appearances[i]["race"],
                "appearance": race_appearances[i]["appearance"],
                "gender": gender_personalities[i]["gender"],
                "personality": gender_personalities[i]["personality"]
            }
            characters.append(char)
        
        return characters
