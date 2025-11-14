"""
记忆管理服务 - 整合三种记忆：对话历史、持久化记忆、向量检索
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from ..core.dialogue_query import DialogueQuery
from .vector_store import VectorStore
from .persistent_memory_service import PersistentMemoryService
from ..custom_logger import custom_logger


class MemoryService:
    """
    记忆管理服务 - 整合三种记忆类型
    
    1. 对话历史（MySQL t_dialogue）- 最近的对话记录
    2. 持久化记忆（MySQL chat_memory）- LLM提取的短期/长期记忆
    3. 向量检索（Qdrant）- 语义相似的历史对话（额外记忆）
    """
    
    def __init__(
        self, 
        db=None, 
        llm_service=None,
        vector_config: Optional[Dict] = None,
        persistent_memory_config: Optional[Dict] = None
    ):
        """
        初始化记忆服务
        
        Args:
            db: 数据库会话
            llm_service: LLM服务
            vector_config: 向量数据库配置（可选）
            persistent_memory_config: 持久化记忆配置（可选）
        """
        self.db = db
        
        # 向量存储（额外记忆 - 可选）
        self.vector_store = VectorStore(vector_config)
        
        # 持久化记忆服务（短期/长期记忆 - 可选）
        self.persistent_memory = None
        if llm_service and persistent_memory_config:
            self.persistent_memory = PersistentMemoryService(
                db, llm_service, persistent_memory_config
            )
    
    async def get_short_term_memory(
        self, 
        user_id: str, 
        character_id: str = "default",
        if_voice: bool = False,
        limit: int = 20
    ) -> Tuple[List[Dict], str]:
        """
        获取短期记忆（最近的对话历史）
        
        来源：MySQL t_dialogue 表
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
            if_voice: 是否语音对话
            limit: 返回数量
        
        Returns:
            (对话历史, 用户昵称)
        """
        if user_id == 'guest':
            return [], "熟悉的人"
        
        try:
            dq = DialogueQuery(self.db)
            
            if character_id == 'default':
                conversation_history, nickname = dq.get_user_pillow_dialogue_history(user_id, if_voice)
            else:
                conversation_history, nickname = dq.get_user_third_character_dialogue_history(user_id, character_id)
            
            # 限制返回数量
            return conversation_history[:limit], nickname
        except Exception as e:
            custom_logger.error(f"Failed to get short-term memory: {e}")
            return [], "熟悉的人"
    
    async def get_persistent_memory(
        self,
        user_id: str,
        character_id: str
    ) -> Dict[str, str]:
        """
        获取持久化记忆（LLM提取的短期/长期记忆）
        
        来源：MySQL chat_memory 表
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
        
        Returns:
            {
                "short_term": "短期记忆文本",
                "long_term": "长期记忆文本"
            }
        """
        if not self.persistent_memory:
            return {"short_term": "", "long_term": ""}
        
        return await self.persistent_memory.get_memory_context(user_id, character_id)
    
    async def get_vector_memory(
        self,
        user_id: str,
        current_message: str,
        limit: int = 3
    ) -> Tuple[List[Dict], bool]:
        """
        获取向量检索记忆（语义相似的历史对话 - 额外记忆）
        
        来源：Qdrant 向量数据库
        
        Args:
            user_id: 用户ID
            current_message: 当前消息（用于语义检索）
            limit: 返回数量
        
        Returns:
            (相关的历史对话列表, 是否需要跳过存储)
        """
        if user_id == 'guest':
            return [], False
        
        # 使用向量数据库搜索相似对话
        similar_conversations = await self.vector_store.search_similar_conversations(
            user_id=user_id,
            query_text=current_message,
            limit=limit
        )
        
        # 检查是否有高度相似的对话（超过阈值则认为是重复内容）
        should_skip_storage = False
        if similar_conversations and similar_conversations[0]["score"] >= 0.96:
            should_skip_storage = True
            custom_logger.debug(f"Found highly similar conversation (score: {similar_conversations[0]['score']}) - will skip storage")
        
        # 转换为对话格式
        vector_memory = []
        for conv in similar_conversations:
            vector_memory.extend([
                {"role": "user", "content": conv["user_message"]},
                {"role": "assistant", "content": conv["ai_response"]}
            ])
        
        return vector_memory, should_skip_storage
    
    async def get_combined_memory(
        self,
        user_id: str,
        current_message: str,
        character_id: str = "default",
        if_voice: bool = False,
        conversation_history_limit: int = 7,
        vector_memory_limit: int = 3
    ) -> Tuple[List[Dict], str, Dict[str, str], bool]:
        """
        获取组合记忆（对话历史 + 持久化记忆 + 向量检索）
        
        Args:
            user_id: 用户ID
            current_message: 当前消息
            character_id: 角色ID
            if_voice: 是否语音
            conversation_history_limit: 对话历史数量
            vector_memory_limit: 向量检索数量
        
        Returns:
            (对话历史, 用户昵称, 持久化记忆, 是否需要跳过向量存储)
        """
        import time
        start_time = time.time()
        custom_logger.info(f"Starting to get combined memory for user {user_id}")
        
        # 1. 获取对话历史（MySQL t_dialogue）
        history_start_time = time.time()
        conversation_history, nickname = await self.get_short_term_memory(
            user_id, character_id, if_voice, conversation_history_limit
        )
        history_end_time = time.time()
        history_duration = history_end_time - history_start_time
        custom_logger.info(f"Short-term memory retrieval completed in {history_duration:.2f} seconds")
        
        # 2. 获取持久化记忆（MySQL chat_memory - 短期和长期记忆）
        persistent_start_time = time.time()
        persistent_memory = await self.get_persistent_memory(user_id, character_id)
        persistent_end_time = time.time()
        persistent_duration = persistent_end_time - persistent_start_time
        custom_logger.info(f"Persistent memory retrieval completed in {persistent_duration:.2f} seconds")
        
        # 3. 获取向量检索记忆（Qdrant - 额外记忆，可选）
        vector_start_time = time.time()
        vector_memory, skip_vector_storage = await self.get_vector_memory(
            user_id, current_message, vector_memory_limit
        )
        vector_end_time = time.time()
        vector_duration = vector_end_time - vector_start_time
        custom_logger.info(f"Vector memory retrieval completed in {vector_duration:.2f} seconds")
        
        # 4. 组合记忆
        # 向量记忆 + 对话历史（向量记忆在前，作为额外参考）
        combined_history = vector_memory + conversation_history
        
        custom_logger.info(
            f"Combined memory for user {user_id}: "
            f"{len(conversation_history)} history + "
            f"{len(vector_memory)} vector + "
            f"persistent(short:{len(persistent_memory.get('short_term', ''))} chars, "
            f"long:{len(persistent_memory.get('long_term', ''))} chars)"
        )
        
        end_time = time.time()
        total_duration = end_time - start_time
        custom_logger.info(f"Total combined memory retrieval completed in {total_duration:.2f} seconds")
        
        return combined_history, nickname, persistent_memory, skip_vector_storage
    
    async def save_conversation(
        self,
        user_id: str,
        character_id: str,
        user_message: str,
        ai_response: str,
        metadata: Optional[Dict] = None,
        skip_vector_storage: bool = False
    ) -> Dict:
        """
        保存对话（三种存储）
        
        1. 对话历史：保存到 t_dialogue（前端或其他服务处理）
        2. 持久化记忆：LLM判断后选择性保存到 chat_memory
        3. 向量检索：保存到 Qdrant（如果启用）
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
            user_message: 用户消息
            ai_response: AI回复
            metadata: 元数据
            skip_vector_storage: 是否跳过向量存储（当已检测到高度相似内容时）
        
        Returns:
            保存结果
        """
        import time
        start_time = time.time()
        custom_logger.info(f"Starting to save conversation for user {user_id}")
        
        if user_id == 'guest':
            return {"saved": False, "message": "访客不保存记忆"}
        
        results = {}
        
        # 1. 持久化记忆处理（LLM判断 + MySQL chat_memory）
        persistent_start_time = time.time()
        if self.persistent_memory:
            persistent_result = await self.persistent_memory.process_conversation_memory(
                user_id=user_id,
                character_id=character_id,
                user_message=user_message,
                ai_response=ai_response
            )
            results["persistent_memory"] = persistent_result
        persistent_end_time = time.time()
        persistent_duration = persistent_end_time - persistent_start_time
        custom_logger.info(f"Persistent memory saving completed in {persistent_duration:.2f} seconds")
        
        # 2. 向量存储（额外记忆 - 语义检索）
        vector_start_time = time.time()
        if self.vector_store.enabled and not skip_vector_storage:
            metadata = metadata or {}
            metadata['timestamp'] = datetime.now().isoformat()
            metadata['character_id'] = character_id
            
            vector_saved = await self.vector_store.store_conversation(
                user_id=user_id,
                user_message=user_message,
                ai_response=ai_response,
                metadata=metadata
            )
            results["vector_memory"] = {"saved": vector_saved}
        elif skip_vector_storage:
            results["vector_memory"] = {"saved": False, "reason": "High similarity detected, storage skipped"}
        vector_end_time = time.time()
        vector_duration = vector_end_time - vector_start_time
        custom_logger.info(f"Vector memory saving completed in {vector_duration:.2f} seconds")
        
        end_time = time.time()
        total_duration = end_time - start_time
        custom_logger.info(f"Total conversation saving completed in {total_duration:.2f} seconds")
        
        return results
    
    async def get_user_profile(self, user_id: str, character_id: str) -> Dict:
        """
        获取用户画像（基于持久化记忆）
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
        
        Returns:
            用户画像字典
        """
        # 获取持久化记忆
        persistent_memory = await self.get_persistent_memory(user_id, character_id)
        
        return {
            "user_id": user_id,
            "character_id": character_id,
            "short_term_summary": persistent_memory.get("short_term", ""),
            "long_term_profile": persistent_memory.get("long_term", ""),
            "stats": await self.get_memory_stats(user_id, character_id) if self.persistent_memory else {}
        }
    
    async def get_memory_stats(self, user_id: str, character_id: str) -> Dict:
        """获取记忆统计"""
        if not self.persistent_memory:
            return {}
        
        return await self.persistent_memory.get_memory_stats(user_id, character_id)
    
    async def clear_memory(self, user_id: str, character_id: str) -> bool:
        """
        清除用户记忆（所有类型）
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
        
        Returns:
            是否成功
        """
        success = True
        
        # 清除持久化记忆
        if self.persistent_memory:
            success = await self.persistent_memory.clear_memory(user_id, character_id)
        
        # TODO: 清除向量记忆（如需要）
        # TODO: 清除对话历史（如需要）
        
        return success
