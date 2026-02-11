"""
克苏鲁跑团(COC)存档槽数据模型
一个 session 可以有多个存档
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, SmallInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from typing import Dict, Any

Base = declarative_base()


class COCSaveSlot(Base):
    """克苏鲁跑团存档槽表模型"""

    __tablename__ = 't_coc_save_slot'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    save_id = Column(String(32), nullable=False, unique=True, comment='存档ID')
    session_id = Column(String(16), nullable=False, index=True, comment='关联会话ID')
    user_id = Column(Integer, nullable=False, index=True, comment='用户ID')
    gm_id = Column(String(16), nullable=True, comment='GM ID')
    game_status = Column(String(32), nullable=False, comment='存档时的游戏状态')
    investigator_card = Column(JSON, nullable=True, comment='人物卡快照')
    round_number = Column(Integer, nullable=False, default=1, comment='回合数')
    turn_number = Column(Integer, nullable=False, default=0, comment='轮数')
    temp_data = Column(JSON, nullable=True, comment='GM信息等临时数据')
    create_time = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    del_ = Column('del', SmallInteger, nullable=False, default=0, comment='是否删除')

    def __repr__(self):
        return f"<COCSaveSlot(save_id={self.save_id}, session_id={self.session_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "save_id": self.save_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "gm_id": self.gm_id,
            "game_status": self.game_status,
            "investigator_card": self.investigator_card or {},
            "round_number": self.round_number,
            "turn_number": self.turn_number,
            "temp_data": self.temp_data or {},
            "create_time": self.create_time.isoformat() if self.create_time else None,
        }
