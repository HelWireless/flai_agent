"""
情绪分析服务
"""
from typing import List, Dict, Optional
from collections import defaultdict
import time

from ..custom_logger import custom_logger


class EmotionService:
    """情绪分析服务"""
    
    def __init__(self, llm_service):
        """
        初始化情绪服务
        
        Args:
            llm_service: LLM服务实例
        """
        self.llm = llm_service
        # 简单的情绪状态缓存，实际项目中可能需要持久化存储
        self._emotion_cache = defaultdict(lambda: {"emotion": "neutral", "timestamp": 0})
        # 情绪状态过期时间（秒）
        self._emotion_expiry = 300  # 5分钟
    
    async def analyze_from_history(
        self,
        conversation_history: List[Dict],
        model_pool: Optional[List[str]] = None
    ) -> str:
        """
        从对话历史分析情绪
        
        Args:
            conversation_history: 对话历史
            model_pool: 模型池
        
        Returns:
            情绪类型字符串
        """
        if not conversation_history:
            return "neutral"
        
        try:
            emotion_type = await self.llm.analyze_emotion(
                conversation_history=conversation_history,
                model_pool=model_pool or ["qwen_plus", "qwen_max"]
            )
            
            custom_logger.info(f"Emotion analyzed: {emotion_type}")
            return emotion_type
        except Exception as e:
            custom_logger.error(f"Emotion analysis failed: {e}")
            return "neutral"
    
    def get_current_emotion(self, user_id: str, character_id: str = "default") -> str:
        """
        获取当前情绪状态
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
            
        Returns:
            当前情绪类型
        """
        cache_key = f"{user_id}:{character_id}"
        cached = self._emotion_cache[cache_key]
        
        # 检查是否过期
        if time.time() - cached["timestamp"] > self._emotion_expiry:
            return "neutral"
        
        return cached["emotion"]
    
    def set_current_emotion(self, user_id: str, emotion: str, character_id: str = "default"):
        """
        设置当前情绪状态
        
        Args:
            user_id: 用户ID
            emotion: 情绪类型
            character_id: 角色ID
        """
        cache_key = f"{user_id}:{character_id}"
        self._emotion_cache[cache_key] = {
            "emotion": emotion,
            "timestamp": time.time()
        }