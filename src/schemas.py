from sqlalchemy import Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any, Union
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
    user_id: Union[str, int] = Field(alias="userId")  # 支持userId别名
    message: str
    message_count: int
    character_id: str = "default"  # 新增人物ID字段
    voice: bool = False
    virtual_id: int = Field(default=0, alias="virtualId")  # 虚拟身份卡ID，0或None表示用户自己
    
    model_config = ConfigDict(
        populate_by_name=True  # 支持通过别名访问字段
    )
    
    @field_validator('user_id')
    def convert_user_id(cls, v) -> str:
        """确保 user_id 是字符串类型"""
        return str(v)

class ChatResponse(BaseModel):
    user_id: str
    llm_message: List[str]
    complex_message: Optional[str] = None
    emotion_type: int

class Text2Voice(BaseModel):
    user_id: str
    text_id: str
    text: str

class Text2VoiceResponse(BaseModel):
    user_id: str
    text_id: str
    url: str


class GenerateOpenerRequest(BaseModel):
    character_id: str = Field(alias="characterId")  # 使用Field直接定义别名
    opener_index: int = Field(default=0, alias="openerIndex")
    user_id: Union[str, int] = Field(default='guest', alias="userId")
    history: bool = False

    model_config = ConfigDict(
        populate_by_name=True  # 替代原来的allow_population_by_field_name
    )
    
    @field_validator('user_id')
    def convert_user_id(cls, v) -> str:
        """确保 user_id 是字符串类型"""
        return str(v)

class GenerateOpenerResponse(BaseModel):
    opener: str

# 在 src/schemas.py 中添加或修改 DrawCardRequest
class DrawCardRequest(BaseModel):
    user_id: Union[str, int] = Field(alias="userId")
    totalSummary: Optional[Dict[str, Any]] = None  # 修改为字典类型
    
    model_config = ConfigDict(
        populate_by_name=True,
        # 添加额外配置确保在不同部署环境下的一致性
        from_attributes=True,
        extra="forbid"
    )
    
    @field_validator('user_id')
    def convert_user_id(cls, v) -> str:
        """确保 user_id 是字符串类型"""
        return str(v)


class DrawCardResponse(BaseModel):
    brief: str
    luckNum: float
    luck: str
    luckBrief: str
    number: int
    numberBrief: str
    color: str
    hex: str
    colorBrief: str
    action: str
    actionBrief: str
    refreshment: str
    refreshmentBrief: str


# ==================== 副本世界 (Instance World) ====================

class IWChatRequest(BaseModel):
    """副本世界对话请求"""
    user_id: Union[str, int] = Field(alias="userId")
    session_id: Optional[str] = Field(default=None, alias="sessionId")  # 新游戏时不传
    world_id: str = Field(alias="worldId")
    gm_id: Optional[str] = Field(default=None, alias="gmId")  # 切换GM时传入
    message: str = ""
    action: str = "chat"  # chat | save | load
    save_id: Optional[str] = Field(default=None, alias="saveId")  # action=load 时必传
    
    model_config = ConfigDict(
        populate_by_name=True
    )
    
    @field_validator('user_id')
    def convert_user_id(cls, v) -> str:
        return str(v)


class IWSelection(BaseModel):
    """副本世界选项"""
    id: str
    text: str


class IWGameState(BaseModel):
    """异世界游戏状态"""
    session_id: str = Field(alias="sessionId")
    world_id: str = Field(alias="worldId")
    gm_id: str = Field(alias="gmId")
    game_status: str = Field(alias="gameStatus")  # gm_intro | world_intro | character_select | playing | ended | death
    current_character_id: Optional[str] = Field(default=None, alias="currentCharacterId")
    
    model_config = ConfigDict(
        populate_by_name=True
    )


class IWChatResponse(BaseModel):
    """副本世界对话响应（SSE 最终结果）"""
    session_id: str = Field(alias="sessionId")
    content: str  # markdown 内容
    selection_type: str = Field(alias="selectionType")  # choice | input | none
    selections: List[IWSelection] = []
    game_state: IWGameState = Field(alias="gameState")
    save_id: Optional[str] = Field(default=None, alias="saveId")  # 存档时返回
    
    model_config = ConfigDict(
        populate_by_name=True
    )


class IWSession(BaseModel):
    """副本世界会话（内存存储用）"""
    session_id: str
    user_id: str
    world_id: str
    gm_id: str
    game_phase: str = "gm_intro"  # gm_intro | world_intro | character_select | playing | ended
    game_state: str = "playing"  # playing | ended | death
    gender_preference: Optional[str] = None
    current_character_id: Optional[str] = None
    random_seed: Optional[int] = None
    characters: List[Dict[str, Any]] = []
    dialogue_history: List[Dict[str, str]] = []
    save_id: Optional[str] = None
    save_data: Optional[Dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""