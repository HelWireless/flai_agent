from sqlalchemy import Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import List, Optional

Base = declarative_base()

class UserHistory(Base):
    __tablename__ = "user_history"
    user_id = Column(String, primary_key=True, index=True)
    history = Column(Text)

class Document(BaseModel):
    text: str

class Query(BaseModel):
    user_id: str
    text: str

class ContentCheckRequest(BaseModel):
    text: str

class TextToSpeechRequest(BaseModel):
    text: str
    voice: str

class ChatRequest(BaseModel):
    user_id: str
    message: str
    message_count: int
    character_id: str = "default"  # 新增人物ID字段

class ChatResponse(BaseModel):
    user_id: str
    llm_message: List[str]
    complex_message: Optional[str] = None
    emotion_type: int

class Text2Voice(BaseModel):
    user_id: int
    text_id: int
    text: str

class Text2VoiceResponse(BaseModel):
    user_id: int
    text_id: int
    url: str


class GenerateOpenerRequest(BaseModel):
    character_id: str  # 对应输入的characterId
    opener_index: int  # 对应输入的openerIndex

    class Config:
        # 允许使用字段别名接收JSON数据
        allow_population_by_field_name = True
        fields = {
            "character_id": {"alias": "characterId"},
            "opener_index": {"alias": "openerIndex"}
        }

class GenerateOpenerResponse(BaseModel):
    opener: str

