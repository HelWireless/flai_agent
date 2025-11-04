"""
对话服务 - 处理对话相关的业务逻辑
"""
from typing import List, Dict, Optional, Tuple
import random

from ..schemas import ChatRequest, ChatResponse, GenerateOpenerRequest, GenerateOpenerResponse
from ..core.content_filter import ContentFilter
from ..core.config_loader import get_config_loader
from ..utils import get_emotion_type, split_message
from ..custom_logger import custom_logger
from .llm_service import LLMService
from .memory_service import MemoryService
from .emotion_service import EmotionService
from src.api.prompts.generate_prompts import get_prompt_by_character_id


class ChatService:
    """对话业务服务"""
    
    def __init__(
        self, 
        llm_service: LLMService,
        memory_service: MemoryService,
        content_filter: ContentFilter,
        config_loader
    ):
        """
        初始化对话服务
        
        Args:
            llm_service: LLM服务
            memory_service: 记忆服务
            content_filter: 内容过滤器
            config_loader: 配置加载器
        """
        self.llm = llm_service
        self.memory = memory_service
        self.cf = content_filter
        self.config_loader = config_loader
        self.emotion_service = EmotionService(llm_service)
        
        # 加载配置
        responses_config = config_loader.get_responses()
        self.error_responses = responses_config.get('error_responses', [])
        self.sensitive_responses = responses_config.get('sensitive_responses', [])
        self.characters_opener = config_loader.get_character_openers()
    
    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """
        处理对话请求
        
        Args:
            request: 对话请求
        
        Returns:
            对话响应
        """
        custom_logger.info(
            f"Processing chat for user: {request.user_id}, "
            f"character: {request.character_id}, voice: {request.voice}"
        )
        
        # 1. 敏感内容检查
        is_sensitive, sensitive_words = self.cf.detect_sensitive_content(request.message)
        if is_sensitive:
            custom_logger.warning(f"Sensitive content detected: {sensitive_words}")
            answer = random.choice(self.sensitive_responses)
            emotion_type = get_emotion_type(answer)
            
            return ChatResponse(
                user_id=request.user_id,
                llm_message=[answer],
                emotion_type=emotion_type
            )
        
        # 2. 获取组合记忆
        # 2.1 对话历史 + 持久化记忆 + 向量检索
        conversation_history, nickname, persistent_memory = await self.memory.get_combined_memory(
            user_id=request.user_id,
            current_message=request.message,
            character_id=request.character_id,
            if_voice=request.voice,
            conversation_history_limit=7,  # 最近7轮对话
            vector_memory_limit=3          # 3个语义相似的历史对话（额外记忆）
        )
        
        user_history_exists = len(conversation_history) > 0
        
        # 3. 分析情绪（如果有历史）
        ESM_type = None
        if user_history_exists and request.character_id == 'default':
            ESM_type = await self.emotion_service.analyze_from_history(conversation_history)
        
        # 4. 生成 prompt
        prompt, model_name = get_prompt_by_character_id(
            request.character_id,
            request.user_id,
            nickname,
            ESM_type
        )
        
        # 5. 调用 LLM 生成回答
        try:
            # 构建用户消息（包含对话历史和持久化记忆）
            user_content = prompt["user_prompt"].replace("query", request.message)
            
            # 添加对话历史
            user_content = user_content.replace("history_chat", str(conversation_history) if user_history_exists else "None")
            
            # 添加持久化记忆上下文（如果有）
            memory_context = ""
            if persistent_memory.get("long_term"):
                memory_context += f"\n\n【用户长期特征】\n{persistent_memory['long_term']}"
            if persistent_memory.get("short_term"):
                memory_context += f"\n\n【最近事件】\n{persistent_memory['short_term']}"
            
            if memory_context:
                user_content = f"{user_content}\n{memory_context}"
            
            messages = [
                {"role": "system", "content": prompt["system_prompt"]},
                {"role": "user", "content": user_content}
            ]
            
            # 调用 LLM
            result = await self.llm.chat_completion(
                messages=messages,
                model_name=model_name,
                model_pool=["autodl", "qwen3_32b_custom", "qwen_max", "deepseek"] if not model_name else None,
                temperature=0.9,
                top_p=0.85,
                max_tokens=2048,
                response_format="json_object",
                parse_json=True,
                retry_on_error=True,
                fallback_response=random.choice(self.error_responses)
            )
            
            answer = result.get("answer", random.choice(self.error_responses))
            emotion_type_from_llm = result.get("emotion_type")
            
        except Exception as e:
            custom_logger.error(f"Error generating answer: {str(e)}")
            answer = random.choice(self.error_responses)
            emotion_type_from_llm = None
        
        # 6. 分割消息
        if answer not in self.error_responses:
            llm_messages = split_message(answer, request.message_count)
        else:
            llm_messages = [answer]
        
        # 7. 识别情绪
        emotion_type = get_emotion_type(answer, emotion_type_from_llm)
        
        # 8. 保存到记忆（三种记忆）
        # 这会触发：
        # - LLM判断记忆类型
        # - 持久化记忆更新（chat_memory表）
        # - 向量存储（如果启用）
        memory_result = await self.memory.save_conversation(
            user_id=request.user_id,
            character_id=request.character_id,
            user_message=request.message,
            ai_response=answer,
            metadata={
                "emotion_type": emotion_type,
                "voice": request.voice
            }
        )
        
        # 记录记忆处理结果
        if memory_result:
            custom_logger.debug(f"Memory save result: {memory_result}")
        
        custom_logger.info(f"Chat processed, emotion: {emotion_type}")
        
        return ChatResponse(
            user_id=request.user_id,
            llm_message=llm_messages,
            emotion_type=emotion_type
        )
    
    async def generate_opener(self, request: GenerateOpenerRequest) -> GenerateOpenerResponse:
        """
        生成角色开场白
        
        Args:
            request: 开场白请求
        
        Returns:
            开场白响应
        """
        custom_logger.info(
            f"Generating opener for character: {request.character_id}, "
            f"index: {request.opener_index}, user: {request.user_id}"
        )
        
        # 1. 获取角色开场白配置
        opener = self.characters_opener.get(request.character_id, None)
        
        # 2. 角色不存在处理
        if opener is None:
            custom_logger.error(f"Character {request.character_id} not found")
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"角色 {request.character_id} 不存在")
        
        # 3. 空列表处理
        if not opener:
            custom_logger.error(f"Character {request.character_id} has empty opener list")
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"角色 {request.character_id} 未配置开场白")
        
        # 4. 索引范围校验
        if request.opener_index < 0 or request.opener_index > 4:
            custom_logger.error(f"Invalid opener index: {request.opener_index}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="开场白索引需在 0-4 内")
        
        # 5. 如果需要基于历史生成新开场白
        if request.user_id != 'guest' and request.history:
            conversation_history, nickname = await self.memory.get_short_term_memory(
                user_id=request.user_id,
                character_id=request.character_id
            )
            
            if conversation_history:
                # 获取提示词
                prompt, model_name = get_prompt_by_character_id(
                    request.character_id,
                    request.user_id,
                    nickname
                )
                
                # 使用 LLM 生成新开场白
                opener = await self.llm.generate_opener(
                    system_prompt=prompt["system_prompt"],
                    openers=opener,
                    conversation_history=conversation_history,
                    model_name=model_name or "qwen_max",
                    fallback_responses=self.error_responses
                )
        
        # 6. 索引有效性检查
        try:
            selected_opener = opener[request.opener_index]
        except IndexError:
            max_index = len(opener) - 1
            custom_logger.error(f"Index {request.opener_index} exceeds max {max_index}")
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"当前角色仅支持 0-{max_index} 号开场白"
            )
        
        return GenerateOpenerResponse(opener=selected_opener)

