"""
API 路由定义
纯路由层，只负责接收请求和返回响应，业务逻辑在服务层
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from src.schemas import (
    ChatRequest, ChatResponse,
    Text2Voice, Text2VoiceResponse,
    GenerateOpenerRequest, GenerateOpenerResponse,
    DrawCardRequest, DrawCardResponse,
    IWChatRequest, IWChatResponse
)
from src.database import get_db
from src.services.chat_service import ChatService
from src.services.fortune_service import FortuneService
from src.services.voice_service import VoiceService
from src.services.llm_service import LLMService
from src.services.memory_service import MemoryService
from src.services.instance_world_service import FreakWorldService
from src.services.coc_service import COCService
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


def get_freak_world_service(
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
) -> FreakWorldService:
    """获取异世界服务实例"""
    return FreakWorldService(llm_service, db, app_config)


def get_coc_service(
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service)
) -> COCService:
    """获取克苏鲁跑团服务实例"""
    return COCService(llm_service, db, app_config)


# ==================== API 路由 ====================

@router.post("/chat-pillow", response_model=ChatResponse)
async def chat_pillow(
    chat_request: ChatRequest,
    request: Request,  # 添加Request参数用于记录
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    对话接口
    
    与AI角色进行对话，支持多角色和虚拟身份卡功能。
    
    **请求参数**:
    - `userId`: 用户ID
    - `message`: 用户消息内容
    - `message_count`: 期望返回的消息条数
    - `character_id`: 角色ID，默认"default"，第三方角色如"c1s1c1_0001"
    - `voice`: 是否语音模式
    - `virtualId`: 虚拟身份卡ID（可选）
        - 0: 用户自己身份（默认）
        - 1: 常骁（男，大三学生/外卖员）
        - 2: 陆耀阳（男，CEO）
        - 3: 贺筱满（女，大学生/视频博主）
        - 4: 沈清舟（女，CFO）
    
    **功能**:
    - 敏感内容过滤
    - 获取短期和长期记忆
    - 情绪分析
    - 生成AI回复
    - 保存对话到记忆
    """
    # 记录请求内容
    custom_logger.info(f"Processing chat request: user_id={chat_request.user_id}, "
                      f"message='{chat_request.message}', message_count={chat_request.message_count}, "
                      f"character_id={chat_request.character_id}, voice={chat_request.voice}")
    
    return await chat_service.process_chat(chat_request)


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


# ==================== 异世界接口 ====================

@router.post("/freak-world/chat")
async def freak_world_chat(
    request: IWChatRequest,
    fw_service: FreakWorldService = Depends(get_freak_world_service)
):
    """
    副本世界对话接口（SSE 流式响应）
    
    ## 请求参数
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | userId | string/int | 是 | 用户ID |
    | worldId | string | 是 | 世界ID（如 "01"） |
    | sessionId | string | 否 | 会话ID，新游戏不传 |
    | gmId | string | 否 | GM ID，切换GM时传入 |
    | message | string | 否 | 用户消息 |
    | action | string | 否 | 动作类型，默认 "chat" |
    | saveId | string | 否 | 存档ID，action=load 时必传 |
    
    ### action 类型说明
    - `chat`: 对话（默认）
    - `save`: 保存游戏
    - `load`: 加载存档
    
    ## 请求示例
    
    ### 1. 开始新游戏
    ```json
    {
        "userId": "1000001",
        "worldId": "01"
    }
    ```
    
    ### 2. 指定GM开始新游戏
    ```json
    {
        "userId": "1000001",
        "worldId": "01",
        "gmId": "yan"
    }
    ```
    
    ### 3. 继续对话
    ```json
    {
        "userId": "1000001",
        "worldId": "01",
        "sessionId": "fw_abc123def456",
        "message": "我选择进入那扇神秘的门"
    }
    ```
    
    ### 4. 切换GM
    ```json
    {
        "userId": "1000001",
        "worldId": "01",
        "sessionId": "fw_abc123def456",
        "gmId": "li",
        "message": "继续"
    }
    ```
    
    ### 5. 保存游戏
    ```json
    {
        "userId": "1000001",
        "worldId": "01",
        "sessionId": "fw_abc123def456",
        "action": "save"
    }
    ```
    
    ### 6. 加载存档
    ```json
    {
        "userId": "1000001",
        "worldId": "01",
        "action": "load",
        "saveId": "save_abc123"
    }
    ```
    
    ## 响应格式（SSE）
    
    响应为 Server-Sent Events 流，包含以下事件类型：
    
    ### delta 事件（流式内容）
    ```
    data: {"type": "delta", "content": "欢迎来到"}
    data: {"type": "delta", "content": "异世界..."}
    ```
    
    ### done 事件（最终结果）
    ```
    data: {"type": "done", "result": {
        "session_id": "fw_abc123def456",
        "content": "欢迎来到异世界...",
        "selection_type": "choice",
        "selections": [
            {"id": "1", "text": "进入森林"},
            {"id": "2", "text": "前往城镇"}
        ],
        "game_state": {
            "session_id": "fw_abc123def456",
            "world_id": "01",
            "gm_id": "yan",
            "game_status": "playing",
            "current_character_id": null
        },
        "save_id": null
    }}
    ```
    
    ### error 事件（错误）
    ```
    data: {"type": "error", "message": "错误信息"}
    ```
    
    ## game_status 状态说明
    
    | 状态 | 说明 |
    |------|------|
    | gm_intro | GM自我介绍阶段 |
    | world_intro | 世界介绍阶段 |
    | character_select | 角色选择阶段 |
    | playing | 游戏进行中 |
    | ended | 游戏正常结束 |
    | death | 角色死亡 |
    
    ## selection_type 说明
    
    | 类型 | 说明 |
    |------|------|
    | choice | 选择题，从 selections 中选择 |
    | input | 自由输入 |
    | none | 无需输入（游戏结束等） |
    """
    custom_logger.info(
        f"Freak World request: user_id={request.user_id}, "
        f"session_id={request.session_id}, action={request.action}, "
        f"world_id={request.world_id}"
    )
    
    async def generate():
        async for chunk in fw_service.stream_chat(request):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/freak-world/chat-sync", response_model=IWChatResponse)
async def freak_world_chat_sync(
    request: IWChatRequest,
    fw_service: FreakWorldService = Depends(get_freak_world_service)
):
    """
    副本世界对话接口（同步响应，用于测试）
    
    与 SSE 接口功能相同，但返回完整 JSON 响应而非流式。
    
    ## 请求示例
    
    ```json
    {
        "userId": "1000001",
        "worldId": "01",
        "sessionId": "fw_abc123def456",
        "message": "我选择进入那扇神秘的门"
    }
    ```
    
    ## 响应示例
    
    ```json
    {
        "sessionId": "fw_abc123def456",
        "content": "你推开那扇古老的木门，一股潮湿的气息扑面而来...",
        "selectionType": "choice",
        "selections": [
            {"id": "1", "text": "点燃火把照亮四周"},
            {"id": "2", "text": "小心翼翼地摸黑前进"}
        ],
        "gameState": {
            "sessionId": "fw_abc123def456",
            "worldId": "01",
            "gmId": "yan",
            "gameStatus": "playing",
            "currentCharacterId": null
        },
        "saveId": null
    }
    ```
    """
    custom_logger.info(
        f"Freak World sync request: user_id={request.user_id}, "
        f"session_id={request.session_id}, action={request.action}"
    )
    
    return await fw_service.process_request(request)


# ==================== 克苏鲁跑团接口 ====================

@router.post("/coc/chat")
async def coc_chat(
    request: Request,
    coc_service: COCService = Depends(get_coc_service)
):
    """
    克苏鲁跑团对话接口（同步响应）
    
    ## 游戏流程
    
    ```
    gm_select → step1_attributes → step2_secondary → step3_profession → step4_background → step5_summary → playing
    ```
    
    ## 请求参数
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | accountId | int | 是 | 用户ID |
    | sessionId | string | 否 | 会话ID，新游戏不传 |
    | action | string | 否 | 动作类型，默认 "input" |
    | selection | string | 否 | 选择的选项ID |
    | message | string | 否 | 玩家输入内容（playing 阶段使用） |
    | saveData | object | 否 | 存档数据（action=load 时使用） |
    
    ### action 类型说明
    - `start`: 开始新游戏
    - `confirm`: 确认当前选择
    - `reroll`: 重新随机
    - `select`: 无需单独传，直接传 selection 即可
    - `input`: 自由输入（playing 阶段）
    - `load`: 读取存档
    
    ## 请求示例
    
    ### 1. 开始新游戏
    ```json
    {
        "accountId": 1000001,
        "action": "start"
    }
    ```
    
    ### 2. 选择GM性别
    ```json
    {
        "sessionId": "coc_abc123def456",
        "accountId": 1000001,
        "selection": "female"
    }
    ```
    
    ### 3. 确认属性
    ```json
    {
        "sessionId": "coc_abc123def456",
        "accountId": 1000001,
        "selection": "confirm"
    }
    ```
    
    ### 4. 重新随机属性
    ```json
    {
        "sessionId": "coc_abc123def456",
        "accountId": 1000001,
        "selection": "reroll"
    }
    ```
    
    ### 5. 选择职业（选第1个）
    ```json
    {
        "sessionId": "coc_abc123def456",
        "accountId": 1000001,
        "selection": "prof_0"
    }
    ```
    
    ### 6. 开始游戏
    ```json
    {
        "sessionId": "coc_abc123def456",
        "accountId": 1000001,
        "selection": "start_game"
    }
    ```
    
    ### 7. 游戏中输入
    ```json
    {
        "sessionId": "coc_abc123def456",
        "accountId": 1000001,
        "message": "我想调查这个房间"
    }
    ```
    
    ### 8. 读取存档
    ```json
    {
        "accountId": 1000001,
        "action": "load",
        "saveData": { ... }
    }
    ```
    
    ## 响应示例
    
    ```json
    {
        "sessionId": "coc_abc123def456",
        "gameStatus": "step1_attributes",
        "content": "（璃微微颔首）...以下是你随机分配的8个常规属性值：",
        "structuredData": {
            "title": "第一步：常规属性分配结果",
            "attributes": [
                {"name": "力量", "abbr": "STR", "value": 65, "display": "力量(STR): 65"},
                {"name": "体质", "abbr": "CON", "value": 50, "display": "体质(CON): 50"}
            ]
        },
        "selections": [
            {"id": "confirm", "text": "确认属性"},
            {"id": "reroll", "text": "重新随机"}
        ],
        "investigatorCard": null,
        "turn": 0,
        "round": 0
    }
    ```
    
    ## 游戏状态说明
    
    | gameStatus | 说明 | 可用 selection |
    |------------|------|----------------|
    | gm_select | 选择GM性别 | female, male |
    | step1_attributes | 常规属性分配 | confirm, reroll |
    | step2_secondary | 次要属性确认 | confirm, back |
    | step3_profession | 职业选择 | prof_0, prof_1, prof_2, reroll |
    | step4_background | 背景确认 | confirm, regenerate |
    | step5_summary | 人物卡总结 | start_game, back |
    | playing | 游戏进行中 | 自由输入 message |
    | ended | 游戏结束 | new_game |
    """
    body = await request.json()
    
    custom_logger.info(
        f"COC chat request: account_id={body.get('accountId')}, "
        f"session_id={body.get('sessionId')}, action={body.get('action')}"
    )
    
    return await coc_service.chat(body)