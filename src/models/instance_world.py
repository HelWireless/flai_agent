"""
异世界数据模型
"""
from sqlalchemy import Column, BigInteger, Integer, String, Text, DateTime, JSON, SmallInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class FreakWorldGameState(Base):
    """异世界游戏状态表模型"""
    
    __tablename__ = 't_freak_world_game_state'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    freak_world_id = Column(Integer, nullable=False, index=True, comment='异世界id')
    account_id = Column(Integer, nullable=False, index=True, comment='用户id')
    session_id = Column(String(16), nullable=False, unique=True, comment='会话id')
    
    # 游戏状态字段
    gm_id = Column(String(16), nullable=False, default='01', comment='引导者ID')
    game_status = Column(String(32), nullable=False, default='gm_intro', comment='游戏状态: gm_intro/world_intro/character_select/playing/ended/death')
    gender_preference = Column(String(8), nullable=True, comment='原住民性别偏好')
    current_character_id = Column(String(64), nullable=True, comment='当前交谈角色ID')
    random_seed = Column(BigInteger, nullable=True, comment='随机种子')
    characters = Column(JSON, nullable=True, comment='已生成的角色列表JSON')
    
    create_time = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    del_ = Column('del', SmallInteger, nullable=False, default=0, comment='是否删除')
    
    def __repr__(self):
        return f"<FreakWorldGameState(session_id={self.session_id}, account_id={self.account_id})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "freak_world_id": self.freak_world_id,
            "account_id": self.account_id,
            "session_id": self.session_id,
            "gm_id": self.gm_id,
            "game_status": self.game_status,
            "gender_preference": self.gender_preference,
            "current_character_id": self.current_character_id,
            "random_seed": self.random_seed,
            "characters": self.characters or [],
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "del": self.del_
        }


class FreakWorldDialogue(Base):
    """异世界对话表模型 (只读，适配 t_freak_world_dialogue)"""
    
    __tablename__ = 't_freak_world_dialogue'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    account_id = Column(Integer, nullable=False, index=True, comment='用户id')
    freak_world_id = Column(Integer, nullable=False, index=True, comment='异世界id')
    session_id = Column(Integer, nullable=False, index=True, comment='对话id')
    message = Column(Text, nullable=True, comment='发送内容')
    text = Column(Text, nullable=True, comment='返回内容')
    step = Column(Integer, nullable=True, comment='初始加载步骤')
    ext_param1 = Column(Text, nullable=True, comment='扩展参数1')
    ext_param2 = Column(Text, nullable=True, comment='扩展参数2')
    ext_param3 = Column(Text, nullable=True, comment='扩展参数3')
    create_time = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    del_ = Column('del', SmallInteger, nullable=False, default=0, comment='是否删除')
    
    def __repr__(self):
        return f"<FreakWorldDialogue(session_id={self.session_id}, account_id={self.account_id})>"
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "freak_world_id": self.freak_world_id,
            "session_id": self.session_id,
            "message": self.message,
            "text": self.text,
            "step": self.step,
            "ext_param1": self.ext_param1,
            "ext_param2": self.ext_param2,
            "ext_param3": self.ext_param3,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "del": self.del_
        }
    
    def to_messages(self) -> list:
        """转换为 LLM 消息格式列表 (一条记录转为两条消息)"""
        messages = []
        if self.message:
            messages.append({"role": "user", "content": self.message})
        if self.text:
            messages.append({"role": "assistant", "content": self.text})
        return messages
