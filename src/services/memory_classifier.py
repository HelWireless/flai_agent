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
                "is_long": "yes" | "no" | "unknown",
                "memory_content": "要记忆的内容摘要（如果需要记忆）"
            }
        """
        system_prompt = """你是一个记忆分类专家，负责判断对话是否包含需要长期记忆的信息并提取摘要。

判断标准：
- 回答"yes"：对话中包含用户的持久特征、偏好或重要个人信息
  例如："我喜欢吃辣的"、"我不喜欢运动"、"我是程序员"、"我住在上海"

- 回答"no"：日常对话、简单应答、临时信息
  例如："好的"、"哈哈"、"帮我拿杯水"、"今天天气不错"

- 回答"unknown"：无法确定或模棱两可的情况

请分析对话并只返回如下JSON格式的结果：
{"is_long": "yes", "memory_content": "用户特征摘要"}
或
{"is_long": "no", "memory_content": ""}
或
{"is_long": "unknown", "memory_content": ""}

注意：
1. 只有当is_long为"yes"时才需要提供memory_content
2. memory_content应该简洁明了，概括用户的重要特征或偏好
3. 严格遵循上述JSON格式
"""

        user_content = f"""
用户消息：{user_message}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            result = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen_turbo"],
                temperature=0.3,
                top_p=0.8,
                max_tokens=100,
                response_format="json_object",
                parse_json=True,
                retry_on_error=True
            )
            
            # 验证返回格式
            is_long = result.get("is_long", "unknown")
            if is_long not in ["yes", "no", "unknown"]:
                custom_logger.warning(f"Invalid is_long value: {is_long}, defaulting to 'unknown'")
                is_long = "unknown"
            
            memory_content = result.get("memory_content", "") if is_long == "yes" else ""
            
            return {
                "is_long": is_long,
                "memory_content": memory_content
            }
        except Exception as e:
            custom_logger.error(f"Memory classification failed: {e}")
            # 默认返回不需要记忆
            return {
                "is_long": "unknown",
                "memory_content": ""
            }