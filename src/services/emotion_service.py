"""
情绪分析服务
"""
from typing import List, Dict, Optional

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

