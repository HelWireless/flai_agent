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
    
    1. **Java 层创建会话**：Java 层先调用独立接口创建 sessionId
    2. **用户选择 GM（前置）**：用户在调用本接口前已选好 GM，通过 `gmId` 传入
    3. **用户选择角色**：step=0 时用户选择游戏中要扮演的角色
    4. **换人**：换的是游戏角色，不是 GM
    5. **返回格式**：选择阶段返回 JSON，游戏阶段返回 markdown
    
    > **说明**：Python 端收到 sessionId 后，如本地无记录则自动创建新会话
    
    ## 请求参数
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | userId | str | 是 | 用户ID |
    | worldId | str | 是 | 世界 config_id（如 "world_01"） |
    | sessionId | str | 是 | 会话ID（Java 层创建，测试可传空串） |
    | gmId | str | 是 | 用户选择的 GM config_id（如 "gm_01"） |
    | step | str | 是 | 游戏阶段，初始传 "0" |
    | message | str | 是 | 用户消息，可为空串 |
    | saveId | str | 否 | 存档ID，读档时必填 |
    | extParam | object | 否 | 扩展参数（见下方说明） |
    | stream | bool | 否 | true=SSE（默认），false=同步JSON |
    
    ## extParam 扩展参数说明
    
    | 字段 | 类型 | 说明 |
    |------|------|------|
    | action | str | 操作类型：`"save"` 存档、`"load"` 读档 |
    | save_data | object | 读档时传入的存档数据（由 Java 层提供） |
    
    ## step 游戏阶段说明
    
    | step | 含义 | 响应格式 | 说明 |
    |------|------|----------|------|
    | 0 | char_select | **JSON** | 角色选择阶段（结构化数据） |
    | 1 | playing | **markdown** | 游戏进行中（纯文本叙事） |
    | 2 | ended | **markdown** | 游戏正常结束 |
    | 3 | death | **markdown** | 角色死亡 |
    
    ## 请求示例
    
    > **ID 格式说明**：gmId 和 worldId 直接传完整的 config_id
    > - GM: `"gm_01"`、`"gm_02"` 等
    > - 世界: `"world_01"`、`"world_02"` 等
    
    ### 1. 开始新游戏
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
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
    
    ### 4. 存档
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "1",
        "message": "",
        "extParam": {"action": "save"}
    }
    ```
    
    ### 5. 读档
    ```json
    {
        "userId": "1000001",
        "worldId": "world_01",
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "0",
        "message": "",
        "saveId": "save_abc123",
        "extParam": {"action": "load"}
    }
    ```
    
    ### 6. 同步请求（不使用SSE）
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
    
    ## 响应格式
    
    ### 角色选择阶段响应（step=0，JSON 结构化数据）
    ```json
    {
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "0",
        "content": {
            "title": "选择你的角色",
            "description": "在这个神秘的世界中，你可以扮演以下角色之一：",
            "selections": [
                {"id": "warrior", "text": "勇敢的战士", "desc": "擅长近战，生命值高"},
                {"id": "mage", "text": "神秘的法师", "desc": "擅长魔法，智力高"},
                {"id": "rogue", "text": "敏捷的盗贼", "desc": "擅长潜行，敏捷高"}
            ]
        },
        "complete": false,
        "saveId": null,
        "extData": null
    }
    ```
    
    ### 游戏进行中响应（step=1，markdown 纯文本）
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
    
    ### 存档响应（action: "save"）
    ```json
    {
        "sessionId": "fw_abc123",
        "gmId": "gm_01",
        "step": "1",
        "content": "## 存档成功\\n\\n你的冒险进度已保存...",
        "complete": false,
        "saveId": "save_abc123",
        "extData": {
            "save_data": {
                "save_id": "save_abc123",
                "session_id": "fw_abc123",
                "gm_id": "gm_01",
                "world_id": "world_01"
            }
        }
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
    
    ## 前端接收 SSE 示例
    
    ### iOS (Swift)
    ```swift
    func streamChat(requestBody: [String: Any]) {
        guard let url = URL(string: "https://api.example.com/pillow/freak-world/chat"),
              let jsonData = try? JSONSerialization.data(withJSONObject: requestBody) else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = jsonData
        
        let session = URLSession(configuration: .default)
        let task = session.dataTask(with: request) { data, response, error in
            guard let data = data, let text = String(data: data, encoding: .utf8) else { return }
            
            for line in text.components(separatedBy: "\\n\\n") {
                guard line.hasPrefix("data: "),
                      let jsonData = line.dropFirst(6).data(using: .utf8),
                      let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any] else { continue }
                
                if let type = json["type"] as? String {
                    switch type {
                    case "delta":
                        if let content = json["content"] as? String {
                            // 追加 markdown 内容
                            DispatchQueue.main.async { self.appendContent(content) }
                        }
                    case "done":
                        if let result = json["result"] as? [String: Any] {
                            DispatchQueue.main.async { self.renderResult(result) }
                        }
                    case "error":
                        if let message = json["message"] as? String {
                            print("错误: \\(message)")
                        }
                    default: break
                    }
                }
                
                // 检查结束标识
                if json["complete"] as? Bool == true {
                    print("SSE 流已结束")
                    return
                }
            }
        }
        task.resume()
    }
    ```
    
    ### Flutter (Dart)
    ```dart
    import 'dart:convert';
    import 'package:http/http.dart' as http;
    
    Future<void> streamChat(Map<String, dynamic> requestBody) async {
      final response = await http.post(
        Uri.parse('https://api.example.com/pillow/freak-world/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(requestBody),
      );
      
      final lines = response.body.split('\\n\\n');
      for (final line in lines) {
        if (!line.startsWith('data: ')) continue;
        final data = jsonDecode(line.substring(6));
        
        switch (data['type']) {
          case 'delta':
            appendContent(data['content']);  // 追加 markdown 内容
            break;
          case 'done':
            renderResult(data['result']);    // 渲染最终结果
            break;
          case 'error':
            print('错误: ${data["message"]}');
            break;
        }
        
        if (data['complete'] == true) {
          print('SSE 流已结束');
          return;
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
    
    1. **Java 层创建会话**：Java 层先调用独立接口创建 sessionId
    2. **用户选择 GM（前置）**：用户在调用本接口前已选好 GM，通过 `gmId` 传入
    3. **角色创建流程**：`action: "start"` 直接进入属性分配（step 1），无需再选 GM
    4. **playing 阶段返回 markdown**：step=6 时，所有内容为纯 markdown 叙事文本
    5. **换人**：换的是游戏角色，不是 GM
    
    > **说明**：`action: "start"` 表示新游戏，GM 已由 `gmId` 指定，直接开始角色创建
    
    ## 请求参数（与副本世界统一）
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | userId | str | 是 | 用户ID |
    | worldId | str | 是 | 世界 config_id（COC 固定为 "world_coc"） |
    | sessionId | str | 是 | 会话ID（Java 层创建，测试可传空串） |
    | gmId | str | 是 | 用户选择的 GM config_id（如 "gm_02"） |
    | step | str | 是 | 游戏阶段，初始传 "1" |
    | message | str | 是 | 用户消息/选择，可为空串 |
    | saveId | str | 否 | 存档ID，读档时必填 |
    | extParam | object | 否 | 扩展参数（见下方说明） |
    | stream | bool | 否 | true=SSE（默认），false=同步JSON |
    
    ## step 游戏阶段说明（COC 特有）
    
    | step | 含义 | 响应格式 | 说明 |
    |------|------|----------|------|
    | 1 | step1_attributes | **JSON** | 常规属性分配（`action: "start"` 直接进入） |
    | 2 | step2_secondary | **JSON** | 次要属性确认 |
    | 3 | step3_profession | **JSON** | 职业选择 |
    | 4 | step4_background | **JSON** | 背景确认 |
    | 5 | step5_summary | **JSON** | 人物卡总结 |
    | 6 | playing | **markdown** | 游戏进行中（纯文本叙事） |
    | 7 | ended | **markdown** | 游戏结束 |
    
    > **注意**：GM 已由用户提前选择，`action: "start"` 时直接从 step=1（属性分配）开始
    
    ## extParam 扩展参数说明
    
    | 字段 | 类型 | 说明 |
    |------|------|------|
    | action | str | 操作类型：`"save"` 存档、`"load"` 读档、`"start"` 开始、`"confirm"` 确认、`"reroll"` 重投 |
    | selection | str | 选择的选项ID（如 `"confirm"`, `"reroll"`, `"prof_0"`） |
    | save_data | object | 读档时传入的存档数据（由 Java 层提供） |
    
    ## 请求示例
    
    ### 1. 开始新游戏（直接进入角色创建）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "1",
        "message": "",
        "extParam": {"action": "start"}
    }
    ```
    > GM 已通过 `gmId` 指定，`action: "start"` 直接进入属性分配阶段
    
    ### 2. 确认属性（角色创建流程）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
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
        "worldId": "world_coc",
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
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "6",
        "message": "我想调查这个房间"
    }
    ```
    
    ### 5. 存档
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "6",
        "message": "",
        "extParam": {"action": "save"}
    }
    ```
    
    ### 6. 读档
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "1",
        "message": "",
        "saveId": "save_abc123",
        "extParam": {"action": "load"}
    }
    ```
    
    ## 响应格式
    
    ### 角色创建阶段响应（step 1-5，JSON 结构化数据）
    
    #### step=1 常规属性分配（action=start 后的首个响应）
    ```json
    {
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "1",
        "content": {
            "title": "第一步：常规属性分配结果",
            "description": "（璃微微颔首）以下是你随机分配的8个常规属性值：",
            "attributes": [
                {"name": "STR", "display": "力量(STR)", "value": 65},
                {"name": "CON", "display": "体质(CON)", "value": 50},
                {"name": "SIZ", "display": "体型(SIZ)", "value": 60},
                {"name": "DEX", "display": "敏捷(DEX)", "value": 55},
                {"name": "APP", "display": "外貌(APP)", "value": 70},
                {"name": "INT", "display": "智力(INT)", "value": 75},
                {"name": "POW", "display": "意志(POW)", "value": 50},
                {"name": "EDU", "display": "教育(EDU)", "value": 80}
            ],
            "selections": [
                {"id": "confirm", "text": "确认属性"},
                {"id": "reroll", "text": "重新随机"}
            ]
        },
        "complete": false,
        "saveId": null,
        "extData": {"investigatorCard": null, "turn": 0, "round": 0}
    }
    ```
    
    #### step=3 职业选择
    ```json
    {
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "3",
        "content": {
            "title": "第三步：职业与技能生成",
            "description": "（璃轻声说道）根据你的属性，以下职业比较适合你：",
            "professions": [
                {
                    "id": "prof_0",
                    "name": "私家侦探",
                    "description": "擅长调查和社交",
                    "skills": ["侦查", "心理学", "图书馆使用", "乔装"]
                },
                {
                    "id": "prof_1",
                    "name": "记者",
                    "description": "擅长获取信息和说服",
                    "skills": ["快速交谈", "心理学", "说服", "母语"]
                }
            ],
            "selections": [
                {"id": "prof_0", "text": "选择私家侦探"},
                {"id": "prof_1", "text": "选择记者"},
                {"id": "reroll", "text": "重新生成职业"}
            ]
        },
        "complete": false,
        "saveId": null,
        "extData": {"investigatorCard": null, "turn": 0, "round": 0}
    }
    ```
    
    #### step=5 人物卡总结
    ```json
    {
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "5",
        "content": {
            "title": "第五步：调查员信息总结",
            "description": "（璃微笑着）你的调查员已经准备就绪：",
            "investigatorCard": {
                "name": "张明",
                "age": 28,
                "profession": "私家侦探",
                "attributes": {"STR": 65, "CON": 50, "DEX": 55},
                "skills": {"侦查": 60, "心理学": 45},
                "background": "曾是警察，因一起神秘案件离职..."
            },
            "selections": [
                {"id": "start_game", "text": "开始游戏"},
                {"id": "back", "text": "返回修改"}
            ]
        },
        "complete": false,
        "saveId": null,
        "extData": {"investigatorCard": {...}, "turn": 0, "round": 0}
    }
    ```
    
    ### playing 阶段响应（step=6，markdown 纯文本）
    ```json
    {
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "6",
        "content": "## 调查结果\\n\\n你仔细打量着这个昏暗的房间。墙上的挂钟已经停止了转动，指针永远定格在3点15分...\\n\\n*你注意到书桌抽屉微微开着，里面似乎有什么东西在反光。*\\n\\n> **理智检定：成功**\\n> 你保持了冷静，没有被房间里诡异的氛围所影响。",
        "complete": false,
        "saveId": null,
        "extData": {"investigatorCard": {...}, "turn": 5, "round": 2}
    }
    ```
    
    ### SSE 响应（stream=true）
    
    与副本世界相同的 delta/done/error 事件格式。选择阶段返回 JSON，playing 阶段返回 markdown。
    
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