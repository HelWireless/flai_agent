"""
统一的 LLM 调用服务
整合所有 LLM API 调用逻辑，消除代码重复
"""
import json
import random
import asyncio
from typing import List, Dict, Optional, Any, AsyncGenerator
from functools import partial
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib3
import httpx
from ..custom_logger import custom_logger, debug_log

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
    
    def _create_retry_session(self, retries=5, backoff_factor=1.0, 
                              status_forcelist=(500, 502, 504)):
        """创建带重试机制的 HTTP 会话"""
        session = requests.Session()
        # 禁用SSL警告
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            # 添加对SSL错误的重试
            allowed_methods=frozenset(['HEAD', 'GET', 'PUT', 'DELETE', 'OPTIONS', 'TRACE', 'POST'])
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    async def _make_request(self, url: str, json_data: Dict, headers: Dict, timeout: int = 15):
        """异步 HTTP 请求"""
        # 如果是存档操作（通过消息内容或 model_name 判断），增加超时时间
        is_save_op = False
        if "messages" in json_data:
            for msg in json_data["messages"]:
                if "存档" in msg.get("content", "") or "73829104碧鹿孽心0109" in msg.get("content", ""):
                    is_save_op = True
                    break
        
        actual_timeout = 60 if is_save_op else timeout
        if is_save_op:
            custom_logger.info(f"Detected save/summary operation, increasing timeout to {actual_timeout}s")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            partial(self.session.post, url, json=json_data, headers=headers, timeout=actual_timeout)
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
        """从模型池中选择一个模型，优先选择有过期时间且未过期的模型"""
        from datetime import datetime
        
        # 分类模型：有过期时间的和没有过期时间的
        expiring_models = []
        non_expiring_models = []
        
        for model_name in model_pool:
            if model_name in self.config and 'expired_at' in self.config[model_name]:
                # 检查是否已过期
                expired_at_str = self.config[model_name]['expired_at']
                try:
                    expired_at = datetime.strptime(expired_at_str, "%Y-%m-%d")
                    if expired_at >= datetime.now():
                        # 未过期，加入即将过期模型列表
                        expiring_models.append(model_name)
                    # 如果已过期，则不加入任何列表
                except ValueError:
                    # 如果日期格式不正确，当作不过期处理
                    non_expiring_models.append(model_name)
            else:
                # 没有设置过期时间的模型
                non_expiring_models.append(model_name)
        
        # 优先选择有过期时间且未过期的模型
        if expiring_models:
            return random.choice(expiring_models)
        
        # 如果没有即将过期的模型，从普通模型中选择
        if non_expiring_models:
            return random.choice(non_expiring_models)
        
        # 如果都没有可用的模型，抛出异常
        raise ValueError("No available models in model pool")
    
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
        解析 JSON 响应（带重试逻辑，增加鲁棒性清洗）
        """
        import re
        import json
        
        original_text = response_text
        
        def clean_and_fix_json(text: str) -> str:
            """增强版 JSON 清洗逻辑"""
            if not text:
                return text
            
            # 1. 移除 deepseek 的 <think> 标签
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            
            # 2. 清理 Markdown 代码块
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            
            # 3. 修复常见的 LLM 输出错误：转义引号 \" -> "
            # 只有当外层已经是引号包围时，内部的 \" 才是合法的，但 LLM 经常错误地转义所有引号
            if text.count('\\"') > text.count('"') / 2:
                text = text.replace('\\"', '"')
            
            # 4. 修复字符串内部未转义的换行符
            def fix_newlines(match):
                prefix = match.group(1)
                content = match.group(2)
                # 将字符串内部的真实换行替换为 \n 转义符
                fixed_content = content.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                return f'{prefix}"{fixed_content}"'

            # 匹配 "key": "value" 模式，修复 value 中的换行
            text = re.sub(r'(".*?"\s*:\s*)"([\s\S]*?)"(?=\s*[,}])', fix_newlines, text)
            
            return text

        try:
            # 处理空白响应
            if not response_text or response_text.isspace():
                raise json.JSONDecodeError("Empty response", "", 0)
            
            # 执行清洗
            cleaned_text = clean_and_fix_json(response_text)
            
            # 尝试解析
            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError:
                # 如果解析失败，尝试从文本中正则提取第一个 {...}
                json_match = re.search(r'\{[\s\S]*\}', cleaned_text)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
            
            # 如果还是不行，且看起来不是 JSON，包装成 JSON
            if not cleaned_text.startswith('{'):
                custom_logger.warning(f"LLM returned non-JSON, wrapping: {cleaned_text[:100]}...")
                return {
                    "answer": cleaned_text,
                    "emotion_type": "开心"
                }
            
            # 最后的倔强：直接抛出异常触发重试
            return json.loads(cleaned_text)
            
        except json.JSONDecodeError as e:
            custom_logger.warning(f"JSON parse failed for: {original_text[:200]}...")
            if retry_count < max_retries:
                custom_logger.warning(f"JSON 解析失败，第 {retry_count + 1} 次重试...")
                raise
            else:
                custom_logger.error(f"最终 JSON 解析失败: {str(e)}")
                # 最后的兜底：如果完全无法解析 JSON，将原始文本作为内容返回
                return {
                    "answer": original_text,
                    "emotion_type": "开心"
                }
    
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
        fallback_response: Optional[Any] = None,
        timeout: int = 15
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
            timeout: 请求超时时间
        
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
                
                # 检查是否是内容过滤错误（400 - data_inspection_failed）
                response_text_lower = response.text.lower()
                if response.status_code == 400 and ("data_inspection_failed" in response_text_lower or "inappropriate content" in response_text_lower):
                    custom_logger.warning(f"Content filtered by API: {model_name}")
                    # 直接返回敏感内容回复
                    if fallback_response is not None:
                        return {"content": fallback_response}
                    else:
                        # 如果没有提供fallback_response，从配置中获取随机敏感内容回复
                        from ..core.config_loader import get_config_loader
                        config_loader = get_config_loader()
                        responses_config = config_loader.get_responses()
                        import random
                        default_sensitive_response = random.choice(responses_config.get('sensitive_responses', ["抱歉，由于内容安全策略，无法处理您的请求。"]))
                        return {"content": default_sensitive_response}
                
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
            
            # 检查内容是否为空
            if not content or content.isspace():
                custom_logger.warning(f"Empty content received from LLM {model_name}")
                if fallback_response is not None:
                    return {"content": fallback_response}
                raise Exception("Empty response from LLM")
            
            # 6. JSON 解析（如果需要）
            if parse_json:
                try:
                    parsed_data = await self._parse_json_response(content)
                    
                    # 在调试模式下记录解析后的数据
                    debug_log(f"Parsed JSON response: {parsed_data}")
                    
                    # 添加额外调试信息
                    if "answer" in parsed_data:
                        debug_log(f"Answer field content: '{parsed_data['answer']}'")
                        debug_log(f"Answer field length: {len(str(parsed_data['answer']))}")
                    
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
    
    async def stream_chat_completion(
        self,
        messages: List[Dict],
        model_name: Optional[str] = None,
        model_pool: Optional[List[str]] = None,
        temperature: float = 0.9,
        top_p: float = 0.85,
        max_tokens: int = 4096,
        enable_thinking: bool = False,
        presence_penalty: float = 1.0,
        response_format: Optional[str] = None,
        timeout: float = 120.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式 LLM 调用接口（SSE 直通）
        
        Args:
            messages: 对话消息列表
            model_name: 指定模型名称
            model_pool: 模型池（随机选择）
            temperature: 温度参数
            top_p: top_p 参数
            max_tokens: 最大 token 数
            enable_thinking: 是否启用思考模式
            presence_penalty: 存在惩罚
            response_format: 响应格式 ('json_object' or 'text' or None)
            timeout: 超时时间（秒）
        
        Yields:
            流式响应数据块
            - {"type": "delta", "content": "部分文本"}
            - {"type": "done", "content": "完整文本", "usage": {...}}
            - {"type": "error", "message": "错误信息"}
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
            yield {"type": "error", "message": str(e)}
            return
        
        # 3. 构建流式请求数据
        request_data = {
            "model": model_config["model"],
            "messages": messages,
            "stream": True,  # 启用流式
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "enable_thinking": enable_thinking,
            "presence_penalty": presence_penalty,
        }
        
        if response_format:
            request_data["response_format"] = {"type": response_format}
        
        headers = {
            "Authorization": f"Bearer {model_config['api_key']}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        custom_logger.info(f"Streaming LLM request to {model_name}: {len(messages)} messages")
        debug_log(f"Stream request data: {request_data}")
        
        # 4. 使用 httpx 进行流式请求
        full_content = ""
        usage_info = {}
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    model_config["api_base"],
                    json=request_data,
                    headers=headers
                ) as response:
                    # 检查响应状态
                    if response.status_code != 200:
                        error_text = await response.aread()
                        custom_logger.error(f"Stream API failed: {response.status_code} - {error_text}")
                        yield {"type": "error", "message": f"API error: {response.status_code}"}
                        return
                    
                    # 解析 SSE 流
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        # SSE 格式: "data: {...}"
                        if line.startswith("data: "):
                            data_str = line[6:]  # 去掉 "data: " 前缀
                            
                            # 检查是否结束
                            if data_str.strip() == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                
                                # 提取内容增量
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    
                                    if content:
                                        full_content += content
                                        yield {
                                            "type": "delta",
                                            "content": content
                                        }
                                    
                                    # 检查是否结束
                                    finish_reason = choices[0].get("finish_reason")
                                    if finish_reason:
                                        usage_info = data.get("usage", {})
                                
                            except json.JSONDecodeError as e:
                                custom_logger.warning(f"Failed to parse SSE data: {data_str[:100]}")
                                continue
            
            # 流结束，返回完整内容
            custom_logger.info(f"Stream completed from {model_name}, total length: {len(full_content)}")
            yield {
                "type": "done",
                "content": full_content,
                "usage": usage_info
            }
            
        except httpx.TimeoutException:
            custom_logger.error(f"Stream request timeout: {model_name}")
            yield {"type": "error", "message": "Request timeout"}
        except Exception as e:
            custom_logger.error(f"Stream error: {str(e)}")
            yield {"type": "error", "message": str(e)}
    
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

