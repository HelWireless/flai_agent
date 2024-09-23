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

class ChatResponse(BaseModel):
    user_id: str
    llm_message: List[str]
    complex_message: Optional[str] = None
    emotion_type: int
