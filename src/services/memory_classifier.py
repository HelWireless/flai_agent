"""
记忆分类服务 - 使用 LLM 判断对话是否需要记忆及记忆类型
"""
from typing import Dict, Literal
from ..custom_logger import custom_logger


class MemoryClassifier:
    """记忆分类器 - 判断对话是否需要记忆"""
    
    def __init__(self, llm_service):
        """
        初始化记忆分类器
        
        Args:
            llm_service: LLM服务实例
        """
        self.llm = llm_service
    
    async def classify_memory_type(
        self,
        user_message: str,
        ai_response: str
    ) -> Dict[str, any]:
        """
        判断对话的记忆类型
        
        Args:
            user_message: 用户消息
            ai_response: AI回复
        
        Returns:
            {
                "memory_type": "none" | "short_term" | "long_term",
                "memory_content": "要记忆的内容摘要（如果需要记忆）",
                "reason": "判断原因"
            }
        """
        system_prompt = """你是一个记忆分类专家，负责判断对话是否需要记忆以及记忆类型。

记忆类型定义：
1. none（不需要记忆）：日常口水话、简单应答、无信息量的对话
   例如："好的"、"哈哈"、"你真可爱"、"帮我拿杯水"、"嗯嗯"

2. short_term（短期记忆）：最近发生的事情、临时性的信息
   例如："我昨天吃了火锅"、"今天去了健身房"、"明天要开会"
   特征：有时间标记（昨天、今天、明天、最近等）

3. long_term（长期记忆）：用户的特征、喜好、重要信息
   例如："我喜欢吃辣的"、"我不喜欢运动"、"我是程序员"、"我住在上海"
   特征：反映用户的持久特征和偏好

请分析对话并返回JSON格式结果。"""

        user_content = f"""
请分析以下对话，判断是否需要记忆以及记忆类型：

用户消息：{user_message}
AI回复：{ai_response}

请以JSON格式返回：
{{
    "memory_type": "none" | "short_term" | "long_term",
    "memory_content": "如果需要记忆，提取要记忆的内容摘要；如果不需要则为空字符串",
    "reason": "简短说明判断原因"
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            result = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen_plus", "qwen_max"],
                temperature=0.3,  # 较低温度，保证判断一致性
                top_p=0.8,
                max_tokens=256,
                response_format="json_object",
                parse_json=True,
                retry_on_error=True
            )
            
            # 验证返回格式
            memory_type = result.get("memory_type", "none")
            if memory_type not in ["none", "short_term", "long_term"]:
                custom_logger.warning(f"Invalid memory_type: {memory_type}, defaulting to 'none'")
                memory_type = "none"
            
            return {
                "memory_type": memory_type,
                "memory_content": result.get("memory_content", ""),
                "reason": result.get("reason", "")
            }
        except Exception as e:
            custom_logger.error(f"Memory classification failed: {e}")
            # 默认返回不需要记忆
            return {
                "memory_type": "none",
                "memory_content": "",
                "reason": "分类失败"
            }

