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
    virtual_id: str = Field(default="0", alias="virtualId")  # 虚拟身份卡ID，"0"表示用户自己
    
    model_config = ConfigDict(
        populate_by_name=True  # 支持通过别名访问字段
    )
    
    @field_validator('user_id')
    def convert_user_id(cls, v) -> str:
        """确保 user_id 是字符串类型"""
        return str(v)
    
    @field_validator('virtual_id')
    def convert_virtual_id(cls, v) -> str:
        """确保 virtual_id 是字符串类型"""
        return str(v) if v is not None else "0"

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
    """副本世界对话请求（文字副本 + 跑团通用）"""
    user_id: str = Field(alias="userId")                              # 必填
    world_id: str = Field(alias="worldId")                            # 必填
    session_id: str = Field(default="", alias="sessionId")            # 必填，新游戏传空串
    gm_id: str = Field(default="0", alias="gmId")                     # 后端分配的GM（config_id），首次可传"0"
    step: str = Field(default="0")                                    # 必填，游戏阶段，初始 "0"
    message: str = ""                                                 # 必填，可为空串
    save_id: Optional[str] = Field(default=None, alias="saveId")      # 选填，有值=读档
    ext_param: Optional[Dict[str, Any]] = Field(default=None, alias="extParam")  # 扩展参数
    stream: bool = Field(default=True)                                # true=SSE, false=同步
    
    model_config = ConfigDict(
        populate_by_name=True
    )
    
    @field_validator('user_id', mode='before')
    def convert_user_id(cls, v) -> str:
        """确保 user_id 是字符串类型（前端可能传入数字）"""
        return str(v) if v is not None else ""
    
    @field_validator('world_id', mode='before')
    def convert_world_id(cls, v) -> str:
        return str(v) if v is not None else ""
    
    @field_validator('session_id', mode='before')
    def convert_session_id(cls, v) -> str:
        return str(v) if v is not None else ""
    
    @field_validator('gm_id', mode='before')
    def convert_gm_id(cls, v) -> str:
        return str(v) if v is not None else "0"
    
    @field_validator('save_id', mode='before')
    def convert_save_id(cls, v) -> Optional[str]:
        """确保 save_id 是字符串类型（前端可能传入数字）"""
        return str(v) if v is not None else None


class IWChatResponse(BaseModel):
    """副本世界对话响应"""
    session_id: str = Field(alias="sessionId")
    gm_id: str = Field(alias="gmId")                                  # 后端分配的GM（config_id）
    step: str                                                         # 当前游戏阶段
    content: Any                                                      # 选择阶段: JSON对象, playing阶段: markdown字符串
    complete: bool = False                                            # 是否结束
    save_id: Optional[str] = Field(default=None, alias="saveId")      # 存档时返回
    ext_data: Optional[Dict[str, Any]] = Field(default=None, alias="extData")  # 扩展数据
    
    model_config = ConfigDict(
        populate_by_name=True
    )


# 保留旧的类用于兼容（可选，后续移除）
class IWSelection(BaseModel):
    """副本世界选项（已废弃，保留兼容）"""
    id: str
    text: str


class IWGameState(BaseModel):
    """异世界游戏状态（已废弃，保留兼容）"""
    session_id: str = Field(alias="sessionId")
    world_id: str = Field(alias="worldId")
    gm_id: str = Field(alias="gmId")
    game_status: str = Field(alias="gameStatus")
    current_character_id: Optional[str] = Field(default=None, alias="currentCharacterId")
    
    model_config = ConfigDict(
        populate_by_name=True
    )


class IWSession(BaseModel):
    """副本世界会话（内存存储用）"""
    session_id: str
    user_id: str
    world_id: str
    gm_id: str
    step: str = "0"                                     # 游戏阶段: 0=gm_select, 1=playing, 2=ended, 3=death
    current_character_id: Optional[str] = None          # 当前选择的角色ID
    random_seed: Optional[int] = None
    characters: List[Dict[str, Any]] = []
    dialogue_history: List[Dict[str, str]] = []
    save_id: Optional[str] = None
    save_data: Optional[Dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""