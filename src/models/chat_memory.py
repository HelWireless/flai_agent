"""
聊天记忆数据模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class ChatMemory(Base):
    """聊天记忆表模型"""
    
    __tablename__ = 'chat_memory'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True, comment='用户ID')
    robot_id = Column(String(255), nullable=False, index=True, comment='机器人ID/角色ID')
    short_term_memory = Column(Text, comment='短期记忆(文字短)')
    long_term_memory = Column(Text, comment='长期记忆(文字多)')
    conversation_count = Column(Integer, default=0, comment='对话轮次计数(每10轮更新短期记忆)')
    last_daily_update = Column(DateTime, default=datetime(1970, 1, 1), comment='上次每日更新时间')
    created_at = Column(DateTime, default=func.now(), comment='记录创建时间')
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment='记录更新时间')
    
    def __repr__(self):
        return f"<ChatMemory(user_id={self.user_id}, robot_id={self.robot_id})>"

