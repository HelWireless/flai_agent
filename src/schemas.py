from sqlalchemy import Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import List, Optional
from pydantic import ConfigDict, Field

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
    character_id: str = Field(alias="characterId")  # 使用Field直接定义别名
    opener_index: int = Field(alias="openerIndex")

    model_config = ConfigDict(
        populate_by_name=True  # 替代原来的allow_population_by_field_name
    )

class GenerateOpenerResponse(BaseModel):
    opener: str

