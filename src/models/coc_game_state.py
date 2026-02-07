"""
克苏鲁跑团(COC)游戏状态数据模型
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, SmallInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from typing import Dict, Any, Optional

Base = declarative_base()


class COCGameState(Base):
    """克苏鲁跑团游戏状态表模型"""
    
    __tablename__ = 't_coc_game_state'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键')
    account_id = Column(Integer, nullable=False, index=True, comment='用户id')
    session_id = Column(String(16), nullable=False, unique=True, comment='会话id')
    
    # GM相关
    gm_id = Column(String(16), nullable=True, comment='GM ID')
    gm_gender = Column(String(8), nullable=True, comment='GM性别偏好: male/female')
    
    # 游戏状态
    game_status = Column(
        String(32), 
        nullable=False, 
        default='gm_select',
        comment='游戏状态: gm_select/step1_attributes/step2_secondary/step3_profession/step4_background/step5_summary/playing/ended'
    )
    
    # 调查员人物卡JSON
    investigator_card = Column(JSON, nullable=True, comment='调查员人物卡JSON')
    
    # 游戏进度
    round_number = Column(Integer, nullable=False, default=1, comment='回合数(天数)')
    turn_number = Column(Integer, nullable=False, default=0, comment='对话/行动轮数')
    save_count = Column(Integer, nullable=False, default=0, comment='存档计数')
    
    # 临时数据 (用于步骤间传递)
    temp_data = Column(JSON, nullable=True, comment='临时数据JSON')
    
    create_time = Column(DateTime, nullable=False, default=func.now(), comment='创建时间')
    update_time = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment='更新时间')
    del_ = Column('del', SmallInteger, nullable=False, default=0, comment='是否删除')
    
    def __repr__(self):
        return f"<COCGameState(session_id={self.session_id}, game_status={self.game_status})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "session_id": self.session_id,
            "gm_id": self.gm_id,
            "gm_gender": self.gm_gender,
            "game_status": self.game_status,
            "investigator_card": self.investigator_card or {},
            "round_number": self.round_number,
            "turn_number": self.turn_number,
            "save_count": self.save_count,
            "temp_data": self.temp_data or {},
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
    
    def get_investigator_card(self) -> Dict[str, Any]:
        """获取调查员人物卡"""
        return self.investigator_card or {}
    
    def set_investigator_card(self, card: Dict[str, Any]):
        """设置调查员人物卡"""
        self.investigator_card = card
    
    def get_temp_data(self) -> Dict[str, Any]:
        """获取临时数据"""
        return self.temp_data or {}
    
    def set_temp_data(self, data: Dict[str, Any]):
        """设置临时数据"""
        self.temp_data = data
    
    def update_temp_data(self, key: str, value: Any):
        """更新临时数据中的某个字段"""
        temp = self.get_temp_data()
        temp[key] = value
        self.temp_data = temp
    
    def increment_turn(self):
        """增加轮数"""
        self.turn_number += 1
    
    def increment_round(self):
        """增加回合数(新的一天)"""
        self.round_number += 1
    
    def increment_save_count(self) -> int:
        """增加存档计数并返回新的存档编号"""
        self.save_count += 1
        return self.save_count
