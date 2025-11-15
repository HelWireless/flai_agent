"""
统一的 LLM 调用服务
整合所有 LLM API 调用逻辑，消除代码重复
"""
import json
import random
import asyncio
from typing import List, Dict, Optional, Any
from functools import partial
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from ..custom_logger import custom_logger


class LLMService:
    """统一的 LLM 调用服务"""
    
    def __init__(self, config: Dict):
        """
        初始化 LLM 服务
        
        Args:
            config: 配置字典（从 config.yaml 加载）
        """
        self.config = config
        self.session = self._create_retry_session()
    
    def _create_retry_session(self, retries=3, backoff_factor=0.3, 
                              status_forcelist=(500, 502, 504)):
        """创建带重试机制的 HTTP 会话"""
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    async def _make_request(self, url: str, json_data: Dict, headers: Dict):
        """异步 HTTP 请求"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            partial(self.session.post, url, json=json_data, headers=headers)
        )
    
    def _get_model_config(self, model_name: str) -> Dict:
        """获取模型配置"""
        if model_name not in self.config:
            raise ValueError(f"Model {model_name} not found in config")
        
        return {
            "api_base": self.config[model_name]["base_url"],
            "model": self.config[model_name]["model"],
            "api_key": self.config[model_name]["api_key"]
        }
    
    def _select_model(self, model_pool: List[str]) -> str:
        """从模型池中随机选择一个模型"""
        return random.choice(model_pool)
    
    def _build_request_data(
        self,
        model: str,
        messages: List[Dict],
        temperature: float = 0.9,
        top_p: float = 0.85,
        max_tokens: int = 2048,
        enable_thinking: bool = False,
        presence_penalty: float = 1.0,
        response_format: Optional[Dict] = None
    ) -> Dict:
        """构建 API 请求数据"""
        request_data = {
            "model": model,
            "messages": messages,
            "stream": False,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "enable_thinking": enable_thinking,
            "presence_penalty": presence_penalty,
        }
        
        if response_format:
            request_data["response_format"] = response_format
        
        return request_data
    
    async def _parse_json_response(
        self, 
        response_text: str, 
        max_retries: int = 3,
        retry_count: int = 0
    ) -> Dict:
        """
        解析 JSON 响应（带重试逻辑）
        
        Args:
            response_text: LLM 返回的文本
            max_retries: 最大重试次数
            retry_count: 当前重试次数
        
        Returns:
            解析后的字典
        
        Raises:
            json.JSONDecodeError: 解析失败
        """
        try:
            # 清理可能的 markdown 代码块
            if "```json" in response_text:
                response_text = response_text.replace("```json\n", "").replace("\n```", "")
            
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            if retry_count < max_retries:
                custom_logger.warning(f"JSON 解析失败，第 {retry_count + 1} 次重试...")
                raise  # 让调用者处理重试
            else:
                custom_logger.error(f"最终 JSON 解析失败: {str(e)}")
                raise
    
    async def chat_completion(
        self,
        messages: List[Dict],
        model_name: Optional[str] = None,
        model_pool: Optional[List[str]] = None,
        temperature: float = 0.9,
        top_p: float = 0.85,
        max_tokens: int = 2048,
        enable_thinking: bool = False,
        presence_penalty: float = 1.0,
        response_format: str = "json_object",
        parse_json: bool = True,
        retry_on_error: bool = True,
        fallback_response: Optional[Any] = None
    ) -> Dict:
        """
        统一的 LLM 调用接口
        
        Args:
            messages: 对话消息列表
            model_name: 指定模型名称
            model_pool: 模型池（随机选择）
            temperature: 温度参数
            top_p: top_p 参数
            max_tokens: 最大 token 数
            enable_thinking: 是否启用思考模式
            presence_penalty: 存在惩罚
            response_format: 响应格式 ('json_object' or 'text')
            parse_json: 是否解析为 JSON
            retry_on_error: 是否在错误时重试
            fallback_response: 失败时的降级响应
        
        Returns:
            LLM 响应（字典或字符串）
        """
        # 1. 选择模型
        if not model_name:
            if model_pool:
                model_name = self._select_model(model_pool)
            else:
                raise ValueError("Must provide either model_name or model_pool")
        
        # 2. 获取模型配置
        try:
            model_config = self._get_model_config(model_name)
        except ValueError as e:
            custom_logger.error(f"Model config error: {e}")
            if fallback_response is not None:
                return {"content": fallback_response}
            raise
        
        # 3. 构建请求
        request_data = self._build_request_data(
            model=model_config["model"],
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            presence_penalty=presence_penalty,
            response_format={"type": response_format} if response_format else None
        )
        
        headers = {
            "Authorization": f"Bearer {model_config['api_key']}",
            "Content-Type": "application/json"
        }
        
        custom_logger.info(f"LLM request to {model_name}: {len(messages)} messages")
        
        # 在调试模式下记录完整的消息内容
        from .custom_logger import debug_log
        debug_log(f"Full messages sent to LLM: {messages}")

        # 4. 调用 API（带重试）
        try:
            response = await self._make_request(
                model_config["api_base"], 
                request_data, 
                headers
            )
            
            # 检查响应状态
            if response.status_code != 200:
                custom_logger.error(
                    f"API request failed: {response.status_code} - {response.text} using {model_name}"
                )
                
                # 重试逻辑
                if retry_on_error and model_pool and len(model_pool) > 1:
                    custom_logger.info("Retrying with different model...")
                    # 换一个模型重试
                    new_pool = [m for m in model_pool if m != model_name]
                    return await self.chat_completion(
                        messages=messages,
                        model_pool=new_pool,
                        temperature=temperature,
                        top_p=top_p,
                        max_tokens=max_tokens,
                        parse_json=parse_json,
                        retry_on_error=False,
                        fallback_response=fallback_response
                    )
                else:
                    if fallback_response is not None:
                        return {"content": fallback_response}
                    raise Exception(f"API request failed with status {response.status_code}")
            
            # 5. 解析响应
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            
            custom_logger.info(f"LLM response received from {model_name}")
            
            # 在调试模式下记录完整的响应内容
            debug_log(f"Full LLM response: {response_data}")
            
            # 6. JSON 解析（如果需要）
            if parse_json:
                try:
                    parsed_data = await self._parse_json_response(content)
                    
                    # 在调试模式下记录解析后的数据
                    debug_log(f"Parsed JSON response: {parsed_data}")
                    
                    return parsed_data
                except json.JSONDecodeError as e:
                    # JSON 解析失败，重试
                    if retry_on_error and model_pool:
                        custom_logger.warning("JSON parsing failed, retrying with different model...")
                        new_pool = [m for m in model_pool if m != model_name]
                        if new_pool:
                            return await self.chat_completion(
                                messages=messages,
                                model_pool=new_pool,
                                temperature=temperature,
                                top_p=top_p,
                                max_tokens=max_tokens,
                                parse_json=parse_json,
                                retry_on_error=False,
                                fallback_response=fallback_response
                            )
                    
                    # 最终失败
                    if fallback_response is not None:
                        return {"content": fallback_response}
                    raise
            else:
                return {"content": content}
        
        except Exception as e:
            custom_logger.error(f"Error in LLM service: {str(e)}")
            if fallback_response is not None:
                return {"content": fallback_response}
            raise
    
    async def generate_chat_response(
        self,
        system_prompt: str,
        user_prompt: str,
        history: Optional[List[Dict]] = None,
        model_pool: Optional[List[str]] = None,
        fallback_responses: Optional[List[str]] = None
    ) -> Dict:
        """
        生成对话响应
        
        专门用于对话场景，封装了常用参数
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": user_prompt})
        
        fallback = random.choice(fallback_responses) if fallback_responses else None
        
        return await self.chat_completion(
            messages=messages,
            model_pool=model_pool or ["qwen_max", "qwen3_32b_custom"],
            temperature=0.9,
            top_p=0.85,
            max_tokens=2048,
            response_format="json_object",
            parse_json=True,
            retry_on_error=True,
            fallback_response=fallback
        )
    
    async def analyze_emotion(
        self,
        conversation_history: List[Dict],
        model_pool: Optional[List[str]] = None
    ) -> str:
        """
        分析对话情绪
        
        Args:
            conversation_history: 对话历史
            model_pool: 模型池
        
        Returns:
            情绪类型字符串
        """
        system_prompt = "你是一个优秀的情感分析专家"
        
        user_content = f"""
请根据以下对话历史分析用户的情绪状态，并只在以下emotion_list列表中选择一个，仅以以下JSON格式返回结果:
emotion_list = [
    'happy', 
    'admiration', 
    'anger', 
    'sadness', 
    'fear', 
    'disgust', 
    'surprise', 
    'anxiety', 
    'neutral'
]

{{
    "emotion_type": "emotion_list 的其中之一"
}}

对话历史:
{str(conversation_history)}

请分析上述对话中用户的情绪状态，只需返回emotion_type字段。
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            result = await self.chat_completion(
                messages=messages,
                model_pool=model_pool or ["qwen_plus", "qwen_max"],
                temperature=0.7,
                top_p=0.8,
                max_tokens=512,
                response_format="json_object",
                parse_json=True,
                retry_on_error=True
            )
            
            return result.get("emotion_type", "neutral")
        except Exception as e:
            custom_logger.error(f"Emotion analysis failed: {e}")
            return "neutral"
    
    async def generate_opener(
        self,
        system_prompt: str,
        openers: List[str],
        conversation_history: List[Dict],
        model_name: str = "qwen_max",
        fallback_responses: Optional[List[str]] = None
    ) -> List[str]:
        """
        生成角色开场白
        
        Args:
            system_prompt: 系统提示词
            openers: 参考开场白
            conversation_history: 对话历史
            model_name: 模型名称
            fallback_responses: 失败时的降级响应
        
        Returns:
            生成的开场白列表
        """
        user_content = f"""
<history>
{conversation_history}
</history>
<openers>
{openers}
</openers>

根据用户的history以及openers里提供的参考内容，生成2个新的开场白。开场白以json的格式返回，且仅返回json，其他不要返回，具体格式如下：
{{
    "openers":[
        "学弟，这杯「月光微醺」是今晚的特别款，基酒用了最新的纳米活性金酒",
        "学弟，这杯「星梦迷离」是特别为你调制的（手指轻敲着水晶杯沿，眼神中闪过一丝狡黠）"
    ]
}}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            result = await self.chat_completion(
                messages=messages,
                model_name=model_name,
                temperature=0.65,
                top_p=0.9,
                max_tokens=2048,
                response_format="json_object",
                parse_json=True,
                retry_on_error=True
            )
            
            return result.get("openers", fallback_responses or [])
        except Exception as e:
            custom_logger.error(f"Opener generation failed: {e}")
            return fallback_responses or []

