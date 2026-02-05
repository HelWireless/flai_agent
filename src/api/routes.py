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
    
    ## 请求参数
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | userId | str | 是 | 用户ID |
    | message | str | 是 | 用户消息内容 |
    | message_count | int | 是 | 期望返回的消息条数 |
    | character_id | str | 否 | 角色ID，默认"default" |
    | voice | bool | 否 | 是否语音模式，默认false |
    | virtualId | str | 否 | 虚拟身份卡ID，默认"0" |
    
    ## virtualId 身份卡说明
    
    | ID | 身份 |
    |----|------|
    | "0" | 用户自己身份（默认） |
    | "1" | 常骁（男，大三学生/外卖员） |
    | "2" | 陆耀阳（男，CEO） |
    | "3" | 贺筱满（女，大学生/视频博主） |
    | "4" | 沈清舟（女，CFO） |
    
    ## 请求示例
    
    ```json
    {
        "userId": "1000001",
        "message": "你好",
        "message_count": 3,
        "character_id": "c1s1c1_0001",
        "voice": false,
        "virtualId": "0"
    }
    ```
    
    ## 响应示例
    
    ```json
    {
        "user_id": "1000001",
        "llm_message": ["你好呀~", "今天心情怎么样？"],
        "emotion_type": 1
    }
    ```
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


# ==================== 副本世界接口 ====================

@router.post("/freak-world/chat")
async def freak_world_chat(
    request: IWChatRequest,
    fw_service: FreakWorldService = Depends(get_freak_world_service)
):
    """
    副本世界对话接口（支持 SSE 流式 / 同步响应）
    
    通过 `stream` 字段控制响应模式：
    - `stream=true`（默认）：SSE 流式响应
    - `stream=false`：同步 JSON 响应
    
    ## 核心机制
    
    1. **GM 由后端分配**：用户不选择 GM，后端自动分配
    2. **用户选择角色**：step=0 时用户选择游戏中的角色
    3. **换人**：换的是游戏角色，不是 GM
    4. **返回格式**：所有阶段都返回 **markdown** 格式文本
    
    ## 请求参数
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | userId | str | 是 | 用户ID |
    | worldId | str | 是 | 世界ID（如 "01"） |
    | sessionId | str | 是 | 会话ID，新游戏传空串 "" |
    | gmId | str | 是 | 后端分配的 GM config_id，首次传 "0" |
    | step | str | 是 | 游戏阶段，初始传 "0" |
    | message | str | 是 | 用户消息，可为空串 |
    | saveId | str | 否 | 存档ID，有值则为读档 |
    | extParam | object | 否 | 扩展参数 |
    | stream | bool | 否 | true=SSE（默认），false=同步JSON |
    
    ## step 游戏阶段说明
    
    | step | 含义 | 说明 |
    |------|------|------|
    | 0 | char_select | 角色选择阶段（GM已由后端分配） |
    | 1 | playing | 游戏进行中 |
    | 2 | ended | 游戏正常结束 |
    | 3 | death | 角色死亡 |
    
    ## 请求示例
    
    ### 1. 开始新游戏（后端分配GM，进入角色选择）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "",
        "gmId": "0",
        "step": "0",
        "message": ""
    }
    ```
    
    ### 2. 选择角色后继续
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "0",
        "message": "我选择扮演那个神秘的旅者"
    }
    ```
    
    ### 3. 游戏进行中对话
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "1",
        "message": "我选择进入那扇神秘的门"
    }
    ```
    
    ### 4. 读取存档
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "",
        "gmId": "0",
        "step": "0",
        "message": "",
        "saveId": "save_abc123"
    }
    ```
    
    ### 5. 同步请求（不使用SSE）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "1",
        "message": "探索房间",
        "stream": false
    }
    ```
    
    ## 响应格式（所有阶段返回 markdown）
    
    ### 同步响应（stream=false）
    ```json
    {
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "1",
        "content": "## 神秘的门后\\n\\n你推开那扇古老的木门，一股潮湿的气息扑面而来...\\n\\n*你听到远处传来微弱的脚步声*",
        "complete": false,
        "saveId": null,
        "extData": null
    }
    ```
    
    ### SSE 响应（stream=true）
    
    #### delta 事件（流式内容）
    ```
    data: {"type": "delta", "content": "## 神秘的门后\\n\\n你推开"}
    data: {"type": "delta", "content": "那扇古老的木门..."}
    ```
    
    #### done 事件（最终结果，流结束）
    ```
    data: {"type": "done", "complete": true, "result": {
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "1",
        "content": "## 神秘的门后\\n\\n你推开那扇古老的木门...",
        "complete": false,
        "saveId": null,
        "extData": null
    }}
    ```
    
    #### error 事件（错误，流结束）
    ```
    data: {"type": "error", "complete": true, "message": "错误信息"}
    ```
    
    > **注意**: SSE 事件中的 `complete: true` 表示流已结束，前端收到后应关闭连接。
    
    ---
    
    ## 前端接收 SSE 示例（JavaScript）
    
    ```javascript
    async function streamChat(requestBody) {
        const response = await fetch('/pillow/freak-world/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
    
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
    
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
    
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\\n\\n');
            buffer = lines.pop();
    
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = JSON.parse(line.slice(6));
                
                if (data.type === 'delta') {
                    // 追加 markdown 内容
                    document.getElementById('content').textContent += data.content;
                } else if (data.type === 'done') {
                    // 渲染最终 markdown
                    renderMarkdown(data.result.content);
                } else if (data.type === 'error') {
                    console.error('错误:', data.message);
                }
                
                // 检查结束标识
                if (data.complete) {
                    console.log('SSE 流已结束');
                    return;
                }
            }
        }
    }
    ```
    
    > **重要提示**：SSE 事件中的 `complete: true` 是流结束标识，前端收到后**必须关闭连接**。
    """
    custom_logger.info(
        f"Freak World request: user_id={request.user_id}, "
        f"session_id={request.session_id}, gm_id={request.gm_id}, "
        f"step={request.step}, stream={request.stream}"
    )
    
    # 根据 stream 字段决定响应模式
    if request.stream:
        # SSE 流式响应
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
    else:
        # 同步 JSON 响应
        return await fw_service.process_request(request)


# ==================== 克苏鲁跑团接口 ====================

@router.post("/coc/chat")
async def coc_chat(
    request: IWChatRequest,
    coc_service: COCService = Depends(get_coc_service)
):
    """
    克苏鲁跑团对话接口（支持 SSE 流式 / 同步响应）
    
    通过 `stream` 字段控制响应模式：
    - `stream=true`（默认）：SSE 流式响应
    - `stream=false`：同步 JSON 响应
    
    ## 核心机制
    
    1. **GM 由后端分配**：用户不选择 GM，后端自动分配
    2. **用户创建角色**：step 0-5 为角色创建流程（属性、职业、背景等）
    3. **playing 阶段返回 markdown**：step=6 时，所有内容为纯 markdown 叙事文本
    4. **换人**：换的是游戏角色，不是 GM
    
    ## 请求参数（与副本世界统一）
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | userId | str | 是 | 用户ID |
    | worldId | str | 是 | 世界ID（COC 固定为 "coc"） |
    | sessionId | str | 是 | 会话ID，新游戏传空串 "" |
    | gmId | str | 是 | 后端分配的 GM config_id，首次传 "0" |
    | step | str | 是 | 游戏阶段，初始传 "0" |
    | message | str | 是 | 用户消息/选择，可为空串 |
    | saveId | str | 否 | 存档ID，有值则为读档 |
    | extParam | object | 否 | 扩展参数（如 selection、action 等） |
    | stream | bool | 否 | true=SSE（默认），false=同步JSON |
    
    ## step 游戏阶段说明（COC 特有）
    
    | step | 含义 | 说明 |
    |------|------|------|
    | 0 | char_create | 角色创建开始（GM由后端分配） |
    | 1 | step1_attributes | 常规属性分配 |
    | 2 | step2_secondary | 次要属性确认 |
    | 3 | step3_profession | 职业选择 |
    | 4 | step4_background | 背景确认 |
    | 5 | step5_summary | 人物卡总结 |
    | 6 | playing | 游戏进行中（**纯 markdown 叙事**） |
    | 7 | ended | 游戏结束 |
    
    ## extParam 扩展参数说明
    
    COC 角色创建阶段需要通过 extParam 传递选择：
    - `selection`: 选择的选项ID（如 "confirm", "reroll", "prof_0"）
    - `action`: 动作类型（如 "start", "confirm", "reroll"）
    
    ## 请求示例
    
    ### 1. 开始新游戏（后端分配GM）
    ```json
    {
        "userId": "1000001",
        "worldId": "coc",
        "sessionId": "",
        "gmId": "0",
        "step": "0",
        "message": "",
        "extParam": {"action": "start"}
    }
    ```
    
    ### 2. 确认属性（角色创建流程）
    ```json
    {
        "userId": "1000001",
        "worldId": "coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "1",
        "message": "",
        "extParam": {"selection": "confirm"}
    }
    ```
    
    ### 3. 选择职业
    ```json
    {
        "userId": "1000001",
        "worldId": "coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "3",
        "message": "",
        "extParam": {"selection": "prof_0"}
    }
    ```
    
    ### 4. 游戏中输入（playing 阶段，纯 markdown）
    ```json
    {
        "userId": "1000001",
        "worldId": "coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "6",
        "message": "我想调查这个房间"
    }
    ```
    
    ### 5. 读取存档
    ```json
    {
        "userId": "1000001",
        "worldId": "coc",
        "sessionId": "",
        "gmId": "0",
        "step": "0",
        "message": "",
        "saveId": "save_abc123"
    }
    ```
    
    ## 响应格式（所有阶段返回 markdown）
    
    ### 角色创建阶段响应示例（step 0-5）
    ```json
    {
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "1",
        "content": "## 第一步：常规属性分配结果\\n\\n（璃微微颔首）以下是你随机分配的8个常规属性值：\\n\\n| 属性 | 值 |\\n|------|-----|\\n| 力量(STR) | 65 |\\n| 体质(CON) | 50 |\\n...\\n\\n---\\n**请选择：**\\n- `confirm`: 确认属性\\n- `reroll`: 重新随机",
        "complete": false,
        "saveId": null,
        "extData": {
            "investigatorCard": null,
            "turn": 0,
            "round": 0
        }
    }
    ```
    
    ### playing 阶段响应示例（step=6，纯 markdown 叙事）
    ```json
    {
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "6",
        "content": "## 调查结果\\n\\n你仔细打量着这个昏暗的房间。墙上的挂钟已经停止了转动，指针永远定格在3点15分...\\n\\n*你注意到书桌抽屉微微开着，里面似乎有什么东西在反光。*\\n\\n> **理智检定：成功**\\n> 你保持了冷静，没有被房间里诡异的氛围所影响。",
        "complete": false,
        "saveId": null,
        "extData": {
            "investigatorCard": {...},
            "turn": 5,
            "round": 2
        }
    }
    ```
    
    ### SSE 响应（stream=true）
    
    与副本世界相同的 delta/done/error 事件格式，内容均为 markdown。
    
    > **重要提示**：SSE 事件中的 `complete: true` 是流结束标识，前端收到后**必须关闭连接**。
    """
    custom_logger.info(
        f"COC chat request: user_id={request.user_id}, "
        f"session_id={request.session_id}, gm_id={request.gm_id}, "
        f"step={request.step}, stream={request.stream}"
    )
    
    # 根据 stream 字段决定响应模式
    if request.stream:
        # SSE 流式响应
        async def generate():
            async for chunk in coc_service.stream_chat(request):
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
    else:
        # 同步 JSON 响应
        return await coc_service.process_request(request)