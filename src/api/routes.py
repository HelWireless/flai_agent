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
    
    ## 游戏流程图
    
    ```
                              ┌─reroll─┐       ┌─reroll─┐
                              │        │       │        │
    action=start → step=1 → step=2 → step=3 → step=4 → step=5 → step=6 → 持续对话
    背景介绍       属性分配   次级属性   职业选择  角色确认  装备+属性摘要  游戏开始
    (markdown)    (JSON)    (JSON)    (JSON)    (JSON)    (JSON)      (markdown)
    ```
    
    ## 核心机制
    
    1. **extParam.action 控制特殊操作**：`start` 开始游戏、`select_character` 角色创建/换人、`save` 存档、`load` 读档
    2. **step + extParam.selection 控制游戏流程**：selection 传 `confirm`/`reroll`/职业ID
    3. **职业 ID 格式为 `prof_01`~`prof_N`**：对应 step=3 返回的职业列表索引
    4. **step=4 角色确认**：可发 message 修改姓名/性别/年龄，confirm 进入 step 5
    5. **step=5 随身装备+人物属性摘要**：只有 confirm
    6. **step=6 为游戏阶段**：首次发送开始游戏，之后持续发送 step=6 + message 进行对话
    
    ## 请求参数
    
    | 字段 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | userId | str | 是 | 用户ID |
    | worldId | str | 是 | 世界 config_id（COC 固定为 "world_coc"） |
    | sessionId | str | 是 | 会话ID（Java 层创建，测试可传空串） |
    | gmId | str | 是 | 用户选择的 GM config_id（如 "gm_02"） |
    | step | str | 是 | 游戏阶段（见下方说明） |
    | message | str | 是 | step=4 可传修改信息，step=6 传游戏输入，其余可空串 |
    | saveId | str | 否 | 存档ID，读档时必填 |
    | extParam | object | 是 | 扩展参数（action/selection，见下方说明） |
    | stream | bool | 否 | true=SSE（默认），false=同步JSON |
    
    ## step 说明（请求）
    
    | step | 含义 | extParam | 响应格式 |
    |------|------|----------|----------|
    | — | 开始游戏 | `action: "start"` | markdown（背景介绍） |
    | — | 角色创建 | `action: "select_character"` | JSON（常规属性 + 选择器） |
    | 1 | 属性分配 | `selection: "confirm"/"reroll"/空` | JSON（常规属性 + 选择器） |
    | 2 | 次级属性 | `selection: "confirm"/"reroll"/空` | JSON（次级属性 + 选择器） |
    | 3 | 职业选择 | `selection: "prof_01"~"prof_N"/"reroll"/空` | JSON（职业选项） |
    | 4 | 角色确认 | `selection: "confirm"` 或发 `message` 修改 | JSON（角色信息） |
    | 5 | 随身装备+属性摘要 | `selection: "confirm"`（只有确认） | JSON（装备+属性） |
    | 6 | 游戏对话 | — | markdown（游戏叙事） |
    
    ## extParam 扩展参数说明
    
    | 字段 | 类型 | 说明 |
    |------|------|------|
    | action | str | 操作类型：`"start"` 开始游戏、`"select_character"` 角色创建/换人、`"save"` 存档、`"load"` 读档 |
    | selection | str | 用户选择：`"confirm"` 确认、`"reroll"` 重roll、或职业ID（`prof_01`~`prof_N`） |
    | saveId | str | 存档ID（存档时由前端生成传入，读档时传入要恢复的存档ID） |
    
    ## extParam 使用说明
    
    **action 驱动**：`start`/`save`/`load` 通过 `extParam.action` 触发，不依赖 step。
    
    **selection 驱动**：前端收到响应后，根据 `selections` 数组显示选项按钮。用户点击后，前端在下次请求中通过 `extParam.selection` 传回选择的 id：
    
    | step | selection 值 | 后端行为 |
    |------|-------------|---------|
    | 1 | `"confirm"` | 确认属性，返回次级属性（相当于进入 step 2） |
    | 1 | `"reroll"` 或空 | 重新 roll 属性 |
    | 2 | `"confirm"` | 确认次级属性，返回职业选项（相当于进入 step 3） |
    | 2 | `"reroll"` 或空 | 返回 step 1 重新分配常规属性 |
    | 3 | `"prof_01"`~`"prof_N"` | 选择职业，返回角色确认（相当于进入 step 4） |
    | 3 | `"reroll"` 或空 | 重新 roll 职业 |
    | 4 | `"confirm"` | 确认角色，返回随身装备+属性摘要（相当于进入 step 5） |
    | 4 | 发 `message` | 修改姓名/性别/年龄，重新展示角色确认页 |
    | 5 | `"confirm"` | 确认装备+属性，开始游戏（相当于进入 step 6） |
    
    ## 请求示例
    
    ### 1. 开始新游戏（action=start → 返回背景）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "0",
        "message": "",
        "extParam": {"action": "start"}
    }
    ```
    
    ### 2. 进入角色创建（action=select_character → 返回常规属性）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "1",
        "message": "",
        "extParam": {"action": "select_character"}
    }
    ```
    
    ### 3. 确认属性（step=1 + selection=confirm → 返回次级属性）
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
    
    ### 4. 重roll属性（step=1 + selection=reroll）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "1",
        "message": "",
        "extParam": {"selection": "reroll"}
    }
    ```
    
    ### 5. 确认次级属性（step=2 + selection=confirm → 返回职业选项）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "2",
        "message": "",
        "extParam": {"selection": "confirm"}
    }
    ```
    
    ### 6. 返回重新分配常规属性（step=2 + selection=reroll）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "2",
        "message": "",
        "extParam": {"selection": "reroll"}
    }
    ```
    
    ### 7. 选择职业（step=3 + selection=prof_01 → 返回人物卡）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "3",
        "message": "",
        "extParam": {"selection": "prof_01"}
    }
    ```
    
    ### 8. 重roll职业（step=3 + selection=reroll）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "3",
        "message": "",
        "extParam": {"selection": "reroll"}
    }
    ```
    
    ### 9. 确认角色（step=4 + selection=confirm → 随身装备+属性摘要）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "4",
        "message": "",
        "extParam": {"selection": "confirm"}
    }
    ```
    
    ### 10. 修改角色信息（step=4 + message）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "4",
        "message": "名字改为李明远，女，28岁"
    }
    ```
    
    ### 11. 确认装备+属性，开始游戏（step=5 + selection=confirm）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "5",
        "message": "",
        "extParam": {"selection": "confirm"}
    }
    ```
    
    ### 12. 游戏中对话（step=6 + message）
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
    
    ### 13. 存档（extParam 传 action + saveId）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "coc_abc123",
        "gmId": "gm_02",
        "step": "6",
        "message": "",
        "extParam": {"action": "save", "saveId": "save_abc123"}
    }
    ```
    > `saveId` 由前端/Java 层生成并传入，后端写入 `t_coc_save_slot` 表
    
    ### 14. 读档（extParam 传 action + saveId）
    ```json
    {
        "userId": "1000001",
        "worldId": "world_coc",
        "sessionId": "",
        "gmId": "gm_02",
        "step": "0",
        "message": "",
        "extParam": {"action": "load", "saveId": "save_abc123"}
    }
    ```
    > 后端根据 `saveId` 查 `t_coc_save_slot` 表恢复游戏状态，调用 LLM 生成继续对话
    
    ## 响应格式
    
    响应只有 2 个字段：`content` 和 `complete`
    
    - `content`：选择阶段(step 1-4)为 JSON 对象，游戏阶段(step 0,5)为 markdown 字符串
    - `complete`：游戏是否结束
    
    ### step=0 背景介绍（markdown）
    ```json
    {
        "content": "（璃冷静中带着利落感...）\\n\\n你好，我是璃...",
        "complete": false
    }
    ```
    
    ### step=1 常规属性（JSON）
    ```json
    {
        "content": {
            "title": "常规属性分配结果",
            "description": "（璃）以下是你随机分配的8个常规属性值：",
            "attributes": [
                {"key": "STR", "name": "力量", "value": 60, "description": "衡量调查员纯粹身体力量"},
                {"key": "CON", "name": "体质", "value": 50, "description": "衡量调查员健康与强韧程度"}
            ],
            "selections": [
                {"id": "confirm", "text": "确认属性"},
                {"id": "reroll", "text": "重新随机"}
            ]
        },
        "complete": false
    }
    ```
    
    ### step=2 次级属性（JSON）
    ```json
    {
        "content": {
            "title": "次级属性计算结果",
            "description": "（璃记录下你的属性）根据常规属性计算出以下次级属性：",
            "attributes": [
                {"key": "HP", "name": "生命值", "value": 10, "formula": "(体质50 + 体型50) ÷ 10 = 10", "description": "调查员能承受的伤害量"},
                {"key": "SAN", "name": "理智值", "value": 80, "formula": "等于意志值 = 80", "description": "调查员的心理健康程度"}
            ],
            "selections": [
                {"id": "confirm", "text": "确认次级属性"},
                {"id": "reroll", "text": "返回重新分配常规属性"}
            ]
        },
        "complete": false
    }
    ```
    
    ### step=3 职业选项（JSON）
    ```json
    {
        "content": {
            "title": "职业选择",
            "description": "（璃满意地点头）以下是随机生成的3个职业供你选择：",
            "professions": [
                {
                    "id": "prof_01",
                    "name": "考古学家",
                    "description": "探索古代遗迹的冒险学者",
                    "skills": [{"name": "考古学", "value": 60, "display": "考古学: 60%"}]
                },
                {
                    "id": "prof_02",
                    "name": "作家",
                    "description": "以笔为剑的文字工作者",
                    "skills": [{"name": "母语", "value": 60, "display": "母语: 60%"}]
                },
                {
                    "id": "prof_03",
                    "name": "私家侦探",
                    "description": "追寻真相的独立调查者",
                    "skills": [{"name": "侦查", "value": 60, "display": "侦查: 60%"}]
                }
            ],
            "selections": [
                {"id": "prof_01", "text": "选择 考古学家"},
                {"id": "prof_02", "text": "选择 作家"},
                {"id": "prof_03", "text": "选择 私家侦探"},
                {"id": "reroll", "text": "重新随机职业"}
            ]
        },
        "complete": false
    }
    ```
    
    ### step=4 角色确认（JSON，可发 message 修改姓名/性别/年龄）
    ```json
    {
        "content": {
            "title": "角色确认",
            "description": "（璃翻阅着你的资料）以下是你的调查员信息，可以通过输入消息修改姓名、性别和年龄：",
            "character": {
                "name": "张明远",
                "gender": "男",
                "age": 32,
                "profession": "考古学家",
                "background": "出生于北京的书香门第，自幼对古代文明充满好奇。大学主修考古学，曾参与多次田野发掘..."
            },
            "selections": [
                {"id": "confirm", "text": "确认角色"}
            ]
        },
        "complete": false
    }
    ```
    
    ### step=5 随身装备+人物属性摘要（JSON，只有确认按钮）
    ```json
    {
        "content": {
            "equipmentList": {
                "title": "装备清单",
                "equipment": [
                    {"name": "左轮手枪", "description": "可靠的.38口径左轮手枪", "damage": "1D10"},
                    {"name": "考古工具包", "description": "包含刷子、铲子等田野工具", "damage": "—"},
                    {"name": "手电筒", "description": "便携照明工具", "damage": "—"},
                    {"name": "笔记本", "description": "记录线索的随身本", "damage": "—"},
                    {"name": "绳索", "description": "10米结实麻绳", "damage": "—"}
                ]
            },
            "investigatorCard": {
                "title": "人物属性摘要",
                "primaryAttributes": {"STR": 60, "CON": 50, "DEX": 70, "SIZ": 50, "INT": 40, "POW": 80, "APP": 60, "EDU": 50},
                "secondaryAttributes": {"HP": 10, "MP": 16, "SAN": 80, "LUCK": 55, "DB": 0, "Build": 110, "MOV": 8},
                "skills": {"考古学": 60, "侦查": 60, "攀爬": 70, "图书馆使用": 60},
                "background": "一名经验丰富的考古学家，性格沉稳，善于观察。",
                "currentHP": 10,
                "currentMP": 16,
                "currentSAN": 80
            },
            "selections": [
                {"id": "confirm", "text": "确认，开始游戏"}
            ]
        },
        "complete": false
    }
    ```
    
    ### step=6 游戏对话（markdown）
    ```json
    {
        "content": "**【01轮 / 01回合】**\\n\\n你仔细打量着这个昏暗的房间...\\n\\n❤ 生命 10   💎 魔法 16   🧠 理智 80",
        "complete": false
    }
    ```
    
    ### 存档响应
    ```json
    {
        "content": "（璃点点头）\\n\\n**【存档 001】**\\n\\n存档已保存。",
        "complete": false
    }
    ```
    
    ### 读档响应（后端查表恢复 + 调用 LLM 继续对话）
    ```json
    {
        "content": "**【读档成功】**\\n\\n**【05轮 / 01回合】**\\n\\n（璃翻开记录本）你之前正在调查一座废弃的档案馆...\\n\\n❤ 生命 10   💎 魔法 16   🧠 理智 80",
        "complete": false
    }
    ```
    
    ### SSE 响应（stream=true）
    
    #### delta 事件（流式内容，仅 markdown 阶段）
    ```
    data: {"type": "delta", "content": "（璃的眼中闪过一丝期待）\\n\\n"}
    data: {"type": "delta", "content": "**游戏正式开始！**"}
    ```
    
    #### done 事件（最终结果，流结束）
    ```
    data: {"type": "done", "complete": true, "result": {"content": "...", "complete": false}}
    ```
    
    #### error 事件（错误，流结束）
    ```
    data: {"type": "error", "complete": true, "message": "错误信息"}
    ```
    
    > **注意**: SSE 事件中的 `complete: true` 表示**流已结束**，前端收到后应关闭连接。响应体中的 `complete` 表示**游戏是否结束**。
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