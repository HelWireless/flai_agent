"""
记忆管理服务 - 管理短期和长期记忆
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from ..core.dialogue_query import DialogueQuery
from .vector_store import VectorStore
from ..custom_logger import custom_logger


class MemoryService:
    """记忆管理服务"""
    
    def __init__(self, db=None, vector_config: Optional[Dict] = None):
        """
        初始化记忆服务
        
        Args:
            db: 数据库会话
            vector_config: 向量数据库配置（可选）
        """
        self.db = db
        self.vector_store = VectorStore(vector_config)
    
    async def get_short_term_memory(
        self, 
        user_id: str, 
        character_id: str = "default",
        if_voice: bool = False,
        limit: int = 20
    ) -> Tuple[List[Dict], str]:
        """
        获取短期记忆（最近的对话历史）
        
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
    
    async def get_long_term_memory(
        self,
        user_id: str,
        current_message: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        获取长期记忆（基于语义相似度的历史对话）
        
        Args:
            user_id: 用户ID
            current_message: 当前消息（用于语义检索）
            limit: 返回数量
        
        Returns:
            相关的历史对话列表
        """
        if user_id == 'guest':
            return []
        
        # 使用向量数据库搜索相似对话
        similar_conversations = await self.vector_store.search_similar_conversations(
            user_id=user_id,
            query_text=current_message,
            limit=limit
        )
        
        # 转换为对话格式
        long_term_memory = []
        for conv in similar_conversations:
            long_term_memory.extend([
                {"role": "user", "content": conv["user_message"]},
                {"role": "assistant", "content": conv["ai_response"]}
            ])
        
        return long_term_memory
    
    async def save_conversation(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        保存对话到记忆（数据库 + 向量数据库）
        
        Args:
            user_id: 用户ID
            user_message: 用户消息
            ai_response: AI回复
            metadata: 元数据（情绪、角色等）
        
        Returns:
            是否成功
        """
        if user_id == 'guest':
            return False
        
        try:
            # 1. 保存到关系数据库（通过现有的数据库逻辑）
            # TODO: 这部分需要添加保存逻辑到数据库
            # 目前对话保存在前端或其他地方处理
            
            # 2. 保存到向量数据库（用于长期记忆检索）
            metadata = metadata or {}
            metadata['timestamp'] = datetime.now().isoformat()
            
            await self.vector_store.store_conversation(
                user_id=user_id,
                user_message=user_message,
                ai_response=ai_response,
                metadata=metadata
            )
            
            return True
        except Exception as e:
            custom_logger.error(f"Failed to save conversation: {e}")
            return False
    
    async def get_combined_memory(
        self,
        user_id: str,
        current_message: str,
        character_id: str = "default",
        if_voice: bool = False,
        short_term_limit: int = 7,
        long_term_limit: int = 3
    ) -> Tuple[List[Dict], str]:
        """
        获取组合记忆（短期 + 长期）
        
        Args:
            user_id: 用户ID
            current_message: 当前消息
            character_id: 角色ID
            if_voice: 是否语音
            short_term_limit: 短期记忆数量
            long_term_limit: 长期记忆数量
        
        Returns:
            (组合的对话历史, 用户昵称)
        """
        # 1. 获取短期记忆
        short_term, nickname = await self.get_short_term_memory(
            user_id, character_id, if_voice, short_term_limit
        )
        
        # 2. 获取长期记忆（如果向量存储启用）
        long_term = await self.get_long_term_memory(
            user_id, current_message, long_term_limit
        )
        
        # 3. 合并记忆（长期记忆在前，短期记忆在后）
        combined_memory = long_term + short_term
        
        custom_logger.info(
            f"Combined memory for user {user_id}: "
            f"{len(short_term)} short-term + {len(long_term)} long-term"
        )
        
        return combined_memory, nickname
    
    async def get_user_profile(self, user_id: str) -> Dict:
        """
        获取用户画像
        
        Args:
            user_id: 用户ID
        
        Returns:
            用户画像字典
        """
        # TODO: 实现用户画像功能
        # 可以基于历史对话总结用户的：
        # - 兴趣爱好
        # - 性格特征
        # - 常见情绪
        # - 对话风格
        return {
            "user_id": user_id,
            "profile": "待实现"
        }
    
    async def clear_memory(self, user_id: str) -> bool:
        """
        清除用户记忆
        
        Args:
            user_id: 用户ID
        
        Returns:
            是否成功
        """
        # TODO: 实现清除记忆功能
        # 1. 清除数据库中的对话历史
        # 2. 清除向量数据库中的记忆
        return True

