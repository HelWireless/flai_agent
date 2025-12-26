"""
对话服务 - 处理对话相关的业务逻辑
"""
from typing import List, Dict, Optional, Tuple
import random

from fastapi import HTTPException
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
        import time
        start_time = time.time()
        custom_logger.info(
            f"Processing chat for user: {request.user_id}, "
            f"character: {request.character_id}, voice: {request.voice}"
        )
        
        # 初始化变量
        emotion_type = 0  # 默认情绪类型
        
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
        
        # 2. 获取组合记忆（对话历史 + 持久化记忆 + 向量检索）
        memory_start_time = time.time()
        try:
            combined_history, nickname, persistent_memory, skip_vector_storage = await self.memory.get_combined_memory(
                user_id=request.user_id,
                current_message=request.message,
                character_id=request.character_id,
                if_voice=request.voice,
                conversation_history_limit=7,
                vector_memory_limit=3
            )
        except Exception as e:
            custom_logger.error(f"Error getting memory: {str(e)}")
            combined_history, nickname, persistent_memory = [], "熟悉的人", {}
            skip_vector_storage = False
        
        memory_end_time = time.time()
        memory_duration = memory_end_time - memory_start_time
        custom_logger.info(f"Memory retrieval completed in {memory_duration:.2f} seconds")
        
        user_history_exists = bool(combined_history)
        conversation_history = combined_history if user_history_exists else []
        
        # 3. 获取情绪类型
        emotion_start_time = time.time()
        EMS_type = self.emotion_service.get_current_emotion(request.user_id, request.character_id)
        emotion_end_time = time.time()
        emotion_duration = emotion_end_time - emotion_start_time
        custom_logger.info(f"Emotion detection completed in {emotion_duration:.2f} seconds")
        
        # 4. 获取角色配置和提示词
        prompt_start_time = time.time()
        prompt, model_name = get_prompt_by_character_id(
            character_id=request.character_id,
            user_id=request.user_id,
            nickname=nickname,
            EMS_type=EMS_type
        )
        prompt_end_time = time.time()
        prompt_duration = prompt_end_time - prompt_start_time
        custom_logger.info(f"Prompt generation completed in {prompt_duration:.2f} seconds")
        
        # 5. 调用 LLM 生成回答
        llm_start_time = time.time()
        try:
            # 构建消息列表（包含对话历史和持久化记忆）
            messages = [
                {"role": "system", "content": prompt["system_prompt"]}
            ]
            
            # 添加对话历史（作为多个连续的用户/助手消息）
            if user_history_exists:
                messages.extend(conversation_history)
            
            # 添加持久化记忆上下文（如果有）
            memory_context = ""
            if persistent_memory.get("long_term"):
                memory_context += f"\n\n【用户长期特征】\n{persistent_memory['long_term']}"
            if persistent_memory.get("short_term"):
                memory_context += f"\n\n【最近事件】\n{persistent_memory['short_term']}"
            
            if memory_context:
                # 添加持久化记忆作为系统消息
                messages.append({"role": "system", "content": memory_context})
            
            # 添加当前用户消息（包含JSON格式要求以满足API规范）
            # 某些模型要求消息中包含'json'字样才能使用json_object响应格式
            current_user_message = f"{request.message} 请以JSON格式回复，包含emotion_type和answer字段。"
            messages.append({"role": "user", "content": current_user_message})
            
            # 记录发送给LLM的完整消息内容
            custom_logger.info(f"Sending {len(messages)} messages to LLM")
            for i, msg in enumerate(messages):
                custom_logger.info(f"Message {i+1}: Role={msg['role']}, Content Length={len(str(msg['content']))} chars")
            
            # 在调试模式下记录完整的消息内容
            from ..custom_logger import debug_log
            debug_log(f"Full messages sent to LLM: {messages}")

            # 调用 LLM
            result = await self.llm.chat_completion(
                messages=messages,
                model_name=model_name,
                model_pool=["qwen3_32b_custom", "qwen_max", "deepseek"] if not model_name else None,
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
            
            # 在调试模式下记录LLM的响应
            debug_log(f"LLM Response: {result}")

        except Exception as e:
            custom_logger.error(f"Error generating answer: {str(e)}")
            answer = random.choice(self.error_responses)
            emotion_type_from_llm = None
        
        llm_end_time = time.time()
        llm_duration = llm_end_time - llm_start_time
        custom_logger.info(f"LLM response generation completed in {llm_duration:.2f} seconds")
        
        # 6. 分割消息
        split_start_time = time.time()
        if answer not in self.error_responses:
            llm_messages = split_message(answer, request.message_count)
        else:
            llm_messages = [answer]
        split_end_time = time.time()
        split_duration = split_end_time - split_start_time
        custom_logger.info(f"Message splitting completed in {split_duration:.2f} seconds")
        
        # 7. 识别情绪
        emotion_recognition_start_time = time.time()
        emotion_type = get_emotion_type(answer, emotion_type_from_llm)
        emotion_recognition_end_time = time.time()
        emotion_recognition_duration = emotion_recognition_end_time - emotion_recognition_start_time
        custom_logger.info(f"Emotion recognition completed in {emotion_recognition_duration:.2f} seconds")
        
        # 8. 保存到记忆（三种记忆）
        # 这会触发：
        # - LLM判断记忆类型
        # - 持久化记忆更新（chat_memory表）
        # - 向量存储（如果启用且未检测到高度相似内容）
        memory_save_start_time = time.time()
        memory_result = await self.memory.save_conversation(
            user_id=request.user_id,
            character_id=request.character_id,
            user_message=request.message,
            ai_response=answer,
            metadata={
                "emotion_type": emotion_type,
                "voice": request.voice
            },
            skip_vector_storage=skip_vector_storage
        )
        memory_save_end_time = time.time()
        memory_save_duration = memory_save_end_time - memory_save_start_time
        custom_logger.info(f"Memory saving completed in {memory_save_duration:.2f} seconds")
        
        # 记录记忆处理结果
        if memory_result:
            custom_logger.debug(f"Memory save result: {memory_result}")
        
        end_time = time.time()
        total_duration = end_time - start_time
        custom_logger.info(f"Chat processed, emotion: {emotion_type}, total time: {total_duration:.2f} seconds")
        
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
        
        # 5. 直接使用预设的开场白，不进行数据库查询和LLM调用
        # 所有用户都只是获取预设开场白，不需要基于历史生成新开场白
        
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
        except Exception as e:
            custom_logger.error(f"Unexpected error when getting opener: {str(e)}")
            from fastapi import HTTPException
            raise HTTPException(
                status_code=500,
                detail="获取开场白时发生未知错误"
            )
        
        return GenerateOpenerResponse(opener=selected_opener)

