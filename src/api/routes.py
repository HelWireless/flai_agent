"""
API 路由定义
纯路由层，只负责接收请求和返回响应，业务逻辑在服务层
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.schemas import (
    ChatRequest, ChatResponse,
    Text2Voice, Text2VoiceResponse,
    GenerateOpenerRequest, GenerateOpenerResponse,
    DrawCardRequest, DrawCardResponse
)
from src.database import get_db
from src.services.chat_service import ChatService
from src.services.fortune_service import FortuneService
from src.services.voice_service import VoiceService
from src.services.llm_service import LLMService
from src.services.memory_service import MemoryService
from src.core.content_filter import ContentFilter
from src.core.config_loader import get_config_loader
from src.custom_logger import custom_logger

import yaml
import os

# 创建路由器
router = APIRouter(
    prefix="/pillow",
    tags=["Chat"],
    responses={404: {"description": "Not found"}}
)

# 加载应用配置
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "config", "config.yaml")

with open(config_path, "r", encoding="utf-8") as config_file:
    app_config = yaml.safe_load(config_file)

# 初始化配置加载器
config_loader = get_config_loader()

# 初始化内容过滤器
constants = config_loader.get_constants()
key_words = constants.get('key_words', [])
content_filter = ContentFilter(additional_keywords=key_words)


# ==================== 依赖注入 ====================

def get_llm_service() -> LLMService:
    """获取 LLM 服务实例"""
    return LLMService(app_config)


def get_memory_service(
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
) -> MemoryService:
    """获取记忆服务实例"""
    # 1. 向量数据库配置（额外记忆 - 语义检索）
    vector_config = app_config.get('vector_db', None)
    if vector_config:
        vector_config['enabled'] = vector_config.get('enabled', False)
    
    # 2. 持久化记忆配置（chat_memory 表 - 短期/长期记忆）
    persistent_memory_config = app_config.get('persistent_memory', {
        'enabled': True,  # 默认启用
        'short_term_update_interval': 10,  # 每10轮更新短期记忆
        'enabled_characters': []  # 空列表表示所有角色都启用，也可以指定 ['default', 'c1s1c1_0001']
    })
    
    return MemoryService(
        db=db,
        llm_service=llm_service,
        vector_config=vector_config,
        persistent_memory_config=persistent_memory_config
    )


def get_chat_service(
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
    memory_service: MemoryService = Depends(get_memory_service)
) -> ChatService:
    """获取对话服务实例"""
    return ChatService(llm_service, memory_service, content_filter, config_loader)


def get_fortune_service(
    llm_service: LLMService = Depends(get_llm_service)
) -> FortuneService:
    """获取占卜服务实例"""
    return FortuneService(llm_service, app_config, config_loader)


def get_voice_service() -> VoiceService:
    """获取语音服务实例"""
    return VoiceService(app_config)


# ==================== API 路由 ====================

@router.post("/chat-pillow", response_model=ChatResponse)
async def chat_pillow(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    对话接口
    
    功能：
    - 敏感内容过滤
    - 获取短期和长期记忆
    - 情绪分析
    - 生成AI回复
    - 保存对话到记忆
    """
    return await chat_service.process_chat(request)


@router.post("/text2voice", response_model=Text2VoiceResponse)
async def text_to_voice(
    request: Text2Voice,
    voice_service: VoiceService = Depends(get_voice_service)
):
    """
    文字转语音接口
    
    功能：
    - 调用语音合成API
    - 上传到OSS
    - 返回音频URL
    """
    return await voice_service.text_to_voice(request)


@router.post("/character_opener", response_model=GenerateOpenerResponse)
async def generate_character_opener(
    request: GenerateOpenerRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    获取角色开场白
    
    功能：
    - 返回预设开场白
    - 或基于历史生成新开场白
    """
    try:
        return await chat_service.generate_opener(request)
    except Exception as e:
        custom_logger.error(f"Error in generate_character_opener: {str(e)}")
        raise


@router.post("/draw-card", response_model=DrawCardResponse)
async def draw_card(
    request: DrawCardRequest,
    fortune_service: FortuneService = Depends(get_fortune_service)
):
    """
    占卜抽卡接口
    
    功能：
    - 生成占卜卡片
    - 支持摘要和详细两种模式
    """
    return await fortune_service.generate_card(request)


# ==================== 记忆管理接口（新增）====================

@router.get("/memory/{user_id}/profile")
async def get_user_profile(
    user_id: str,
    character_id: str = "default",
    memory_service: MemoryService = Depends(get_memory_service)
):
    """
    获取用户画像
    
    基于持久化记忆显示用户的短期事件和长期特征
    """
    return await memory_service.get_user_profile(user_id, character_id)


@router.get("/memory/{user_id}/stats")
async def get_memory_stats(
    user_id: str,
    character_id: str = "default",
    memory_service: MemoryService = Depends(get_memory_service)
):
    """
    获取记忆统计信息
    
    显示对话计数、记忆长度、待更新数量等
    """
    return await memory_service.get_memory_stats(user_id, character_id)


@router.delete("/memory/{user_id}")
async def clear_user_memory(
    user_id: str,
    character_id: str = "default",
    memory_service: MemoryService = Depends(get_memory_service)
):
    """
    清除用户记忆
    
    删除持久化记忆和向量记忆
    """
    success = await memory_service.clear_memory(user_id, character_id)
    return {"success": success, "message": "记忆已清除" if success else "清除失败"}
