"""
持久化记忆服务 - 管理 MySQL 中的短期和长期记忆
"""
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DBAPIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime
from collections import defaultdict
import asyncio
import json

from ..custom_logger import custom_logger
from .memory_classifier import MemoryClassifier


class PersistentMemoryService:
    """持久化记忆服务 - 管理MySQL中的chat_memory表"""
    
    # 类级别的短期记忆缓存（内存中）
    _short_term_cache = defaultdict(lambda: {"memories": [], "count": 0, "dialogues": []})
    
    def __init__(self, db: Session, llm_service, config: Optional[Dict] = None):
        """
        初始化持久化记忆服务
        
        Args:
            db: 数据库会话
            llm_service: LLM服务（用于记忆分类）
            config: 记忆配置
        """
        self.db = db
        self.classifier = MemoryClassifier(llm_service)
        self.llm_service = llm_service
        self.config = config or {}
        
        # 配置参数
        self.short_term_update_interval = self.config.get('short_term_update_interval', 7)  # 每7轮更新
        self.enabled_characters = self.config.get('enabled_characters', [])  # 启用记忆的角色列表
        self.global_enabled = self.config.get('enabled', True)  # 全局开关
    
    def is_memory_enabled(self, character_id: str) -> bool:
        """
        判断指定角色是否启用记忆功能
        
        Args:
            character_id: 角色ID
        
        Returns:
            是否启用
        """
        # 全局关闭则全部关闭
        if not self.global_enabled:
            return False
        
        # 如果没有配置 enabled_characters，则默认全部启用
        if not self.enabled_characters:
            return True
        
        # 检查角色是否在启用列表中
        return character_id in self.enabled_characters
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((OperationalError, DBAPIError))
    )
    def query_with_retry(self, db_session, query_func, *args, **kwargs):
        """使用重试机制执行查询"""
        return query_func(db_session, *args, **kwargs)
    
    def _get_memory_record(self, db_session, user_id: str, robot_id: str) -> Optional[Dict]:
        """
        获取记忆记录
        
        Args:
            db_session: 数据库会话
            user_id: 用户ID
            robot_id: 机器人ID
        
        Returns:
            记忆记录字典或None
        """
        result = db_session.execute(
            text("""
                SELECT 
                    id, user_id, robot_id, 
                    short_term_memory, long_term_memory,
                    conversation_count, last_daily_update,
                    created_at, updated_at
                FROM chat_memory
                WHERE user_id = :user_id 
                AND robot_id = :robot_id
                LIMIT 1
            """),
            {"user_id": user_id, "robot_id": robot_id}
        )
        
        row = result.fetchone()
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "robot_id": row[2],
                "short_term_memory": row[3] or "",
                "long_term_memory": row[4] or "",
                "conversation_count": row[5],
                "last_daily_update": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            }
        return None
    
    def _create_memory_record(self, db_session, user_id: str, robot_id: str) -> int:
        """
        创建新的记忆记录
        
        Args:
            db_session: 数据库会话
            user_id: 用户ID
            robot_id: 机器人ID
        
        Returns:
            新记录的ID
        """
        result = db_session.execute(
            text("""
                INSERT INTO chat_memory 
                (user_id, robot_id, short_term_memory, long_term_memory, conversation_count)
                VALUES (:user_id, :robot_id, '', '', 0)
            """),
            {"user_id": user_id, "robot_id": robot_id}
        )
        db_session.commit()
        
        # 获取新插入的ID
        new_id = result.lastrowid
        custom_logger.info(f"Created new memory record (ID: {new_id}) for user {user_id}, robot {robot_id}")
        return new_id
    
    def _update_short_term_memory(self, db_session, user_id: str, robot_id: str, 
                                  memory_content: str, increment: int = 1):
        """
        更新短期记忆
        
        Args:
            db_session: 数据库会话
            user_id: 用户ID
            robot_id: 机器人ID
            memory_content: 记忆内容
            increment: 计数器增量
        """
        db_session.execute(
            text("""
                UPDATE chat_memory
                SET short_term_memory = :memory_content,
                    conversation_count = conversation_count + :increment,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = :user_id 
                AND robot_id = :robot_id
            """),
            {
                "memory_content": memory_content,
                "increment": increment,
                "user_id": user_id,
                "robot_id": robot_id
            }
        )
        db_session.commit()
    
    def _update_long_term_memory(self, db_session, user_id: str, robot_id: str, 
                                 memory_content: str):
        """
        更新长期记忆
        
        Args:
            db_session: 数据库会话
            user_id: 用户ID
            robot_id: 机器人ID
            memory_content: 记忆内容
        """
        db_session.execute(
            text("""
                UPDATE chat_memory
                SET long_term_memory = :memory_content,
                    conversation_count = conversation_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = :user_id 
                AND robot_id = :robot_id
            """),
            {
                "memory_content": memory_content,
                "user_id": user_id,
                "robot_id": robot_id
            }
        )
        db_session.commit()
    
    def _increment_conversation_count(self, db_session, user_id: str, robot_id: str):
        """
        仅增加对话计数器
        
        Args:
            db_session: 数据库会话
            user_id: 用户ID
            robot_id: 机器人ID
        """
        db_session.execute(
            text("""
                UPDATE chat_memory
                SET conversation_count = conversation_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = :user_id 
                AND robot_id = :robot_id
            """),
            {"user_id": user_id, "robot_id": robot_id}
        )
        db_session.commit()
    
    async def process_conversation_memory(
        self,
        user_id: str,
        character_id: str,
        user_message: str,
        ai_response: str
    ) -> Dict:
        """
        处理对话记忆
        
        流程：
        1. 检查记忆功能是否启用
        2. 使用 LLM 判断记忆类型
        3. 根据类型处理：
           - none: 仅计数器+1
           - short_term: 缓存，累积7轮后批量更新
           - long_term: 立即更新到MySQL
        
        Args:
            user_id: 用户ID
            character_id: 角色ID（即 robot_id）
            user_message: 用户消息
            ai_response: AI回复
        
        Returns:
            处理结果字典
        """
        import time
        start_time = time.time()
        custom_logger.info(f"Starting to process conversation memory for user {user_id}")
        
        # 1. 检查记忆功能是否启用
        if not self.is_memory_enabled(character_id):
            return {
                "memory_enabled": False,
                "memory_type": "disabled",
                "message": f"角色 {character_id} 未启用记忆功能"
            }
        
        # Guest 用户不记忆
        if user_id == 'guest':
            return {
                "memory_enabled": False,
                "memory_type": "guest",
                "message": "访客用户不记忆"
            }
        
        try:
            # 确保记录存在
            record_start_time = time.time()
            memory = self.query_with_retry(self.db, self._get_memory_record, user_id, character_id)
            if not memory:
                self.query_with_retry(self.db, self._create_memory_record, user_id, character_id)
                memory = self.query_with_retry(self.db, self._get_memory_record, user_id, character_id)
            record_end_time = time.time()
            record_duration = record_end_time - record_start_time
            custom_logger.info(f"Memory record retrieval/creation completed in {record_duration:.2f} seconds")
        except Exception as e:
            custom_logger.error(f"Failed to get/create memory record: {e}")
            return {"memory_enabled": False, "error": str(e)}
        
        # 2. 使用 LLM 判断记忆类型
        classification_start_time = time.time()
        classification = await self.classifier.classify_memory_type(
            user_message=user_message,
            ai_response=ai_response
        )
        classification_end_time = time.time()
        classification_duration = classification_end_time - classification_start_time
        custom_logger.info(f"Memory classification completed in {classification_duration:.2f} seconds")
        
        # 根据新的分类结果确定记忆类型
        is_long = classification["is_long"]
        memory_content = classification["memory_content"]
        
        if is_long == "yes":
            memory_type = "long_term"
        elif is_long == "no":
            memory_type = "none"
        else:
            memory_type = "none"
        
        custom_logger.info(
            f"Memory classification for user {user_id}: "
            f"type={memory_type}, content={memory_content[:50] if memory_content else 'N/A'}..."
        )
        
        # 3. 根据类型处理
        if memory_type == "none":
            # 不需要记忆，但计数器+1
            try:
                increment_start_time = time.time()
                self.query_with_retry(self.db, self._increment_conversation_count, user_id, character_id)
            except Exception as e:
                custom_logger.error(f"Failed to increment count: {e}")
            
            # 将对话添加到短期记忆缓存中用于后续摘要
            cache_key = f"{user_id}:{character_id}"
            self._short_term_cache[cache_key]["dialogues"].append({
                "user": user_message,
                "ai": ai_response
            })
            
            # 检查是否需要生成短期记忆摘要
            self._short_term_cache[cache_key]["count"] += 1
            if self._short_term_cache[cache_key]["count"] >= self.short_term_update_interval:
                # 异步生成摘要
                asyncio.create_task(self._generate_short_term_summary(user_id, character_id, cache_key))
            
            increment_end_time = time.time()
            increment_duration = increment_end_time - increment_start_time
            custom_logger.info(f"Memory increment completed in {increment_duration:.2f} seconds")
            
            return {
                "memory_enabled": True,
                "memory_type": "none",
                "message": "日常对话，不需要记忆"
            }
        
        elif memory_type == "short_term":
            # 短期记忆：缓存，7轮后批量更新
            short_term_start_time = time.time()
            result = await self._handle_short_term_memory(
                user_id, character_id, memory_content
            )
            short_term_end_time = time.time()
            short_term_duration = short_term_end_time - short_term_start_time
            custom_logger.info(f"Short-term memory handling completed in {short_term_duration:.2f} seconds")
            return result
        
        elif memory_type == "long_term":
            # 长期记忆：异步更新，立即返回结果
            long_term_start_time = time.time()
            # 异步处理长期记忆，不等待完成
            asyncio.create_task(self._handle_long_term_memory_async(
                user_id, character_id, memory_content
            ))
            long_term_end_time = time.time()
            long_term_duration = long_term_end_time - long_term_start_time
            custom_logger.info(f"Long-term memory async task created in {long_term_duration:.2f} seconds")
            # 立即返回结果，不等待长期记忆处理完成
            return {
                "memory_enabled": True,
                "memory_type": "long_term",
                "updated": True,
                "message": "长期记忆正在后台更新"
            }
        
        end_time = time.time()
        total_duration = end_time - start_time
        custom_logger.info(f"Total conversation memory processing completed in {total_duration:.2f} seconds")
        
        return {"memory_enabled": True, "memory_type": memory_type}
    
    async def _handle_short_term_memory(
        self,
        user_id: str,
        robot_id: str,
        memory_content: str
    ) -> Dict:
        """
        处理短期记忆
        
        策略：
        1. 将新记忆加入缓存
        2. 计数器+1
        3. 如果达到7轮，批量更新到MySQL并清空缓存
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
            memory_content: 记忆内容
        
        Returns:
            处理结果
        """
        cache_key = f"{user_id}:{robot_id}"
        
        # 1. 添加到缓存
        self._short_term_cache[cache_key]["memories"].append(memory_content)
        self._short_term_cache[cache_key]["count"] += 1
        
        count = self._short_term_cache[cache_key]["count"]
        pending_count = len(self._short_term_cache[cache_key]["memories"])
        
        custom_logger.debug(
            f"Short-term memory cached for {cache_key}: "
            f"count={count}, pending={pending_count}"
        )
        
        # 2. 检查是否需要更新到数据库
        if count >= self.short_term_update_interval:
            # 达到7轮，批量更新
            return await self._flush_short_term_cache(user_id, robot_id, cache_key)
        else:
            # 还没到7轮，继续缓存（但仍要增加数据库计数器）
            try:
                self.query_with_retry(self.db, self._increment_conversation_count, user_id, robot_id)
            except Exception as e:
                custom_logger.error(f"Failed to increment count: {e}")
            
            return {
                "memory_enabled": True,
                "memory_type": "short_term",
                "cached": True,
                "pending_count": pending_count,
                "remaining_rounds": self.short_term_update_interval - count,
                "message": f"短期记忆已缓存，还需 {self.short_term_update_interval - count} 轮对话后更新"
            }
    
    async def _flush_short_term_cache(
        self,
        user_id: str,
        robot_id: str,
        cache_key: str
    ) -> Dict:
        """
        将缓存的短期记忆批量更新到数据库
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
            cache_key: 缓存键
        
        Returns:
            更新结果
        """
        try:
            # 获取缓存的记忆
            cached_memories = self._short_term_cache[cache_key]["memories"]
            
            if not cached_memories:
                return {"memory_enabled": True, "message": "无待更新的短期记忆"}
            
            # 获取现有短期记忆
            memory = self.query_with_retry(self.db, self._get_memory_record, user_id, robot_id)
            
            if not memory:
                return {"error": "记忆记录不存在"}
            
            existing_short_term = memory["short_term_memory"] or ""
            
            # 合并新记忆（添加时间戳）
            timestamp = datetime.now().strftime("%Y-%m-%d")
            new_memories_with_time = [f"[{timestamp}] {m}" for m in cached_memories]
            new_memories_text = "\n".join(new_memories_with_time)
            
            # 合并到现有短期记忆
            if existing_short_term:
                combined = f"{existing_short_term}\n{new_memories_text}"
            else:
                combined = new_memories_text
            
            # 限制短期记忆总长度（保留最后5000字符）
            if len(combined) > 5000:
                combined = combined[-5000:]
            
            # 更新数据库
            self.query_with_retry(
                self.db, 
                self._update_short_term_memory, 
                user_id, 
                robot_id, 
                combined,
                len(cached_memories)
            )
            
            custom_logger.info(
                f"Short-term memory flushed for {cache_key}: "
                f"{len(cached_memories)} memories → DB"
            )
            
            # 清空缓存
            self._short_term_cache[cache_key] = {"memories": [], "count": 0, "dialogues": []}
            
            return {
                "memory_enabled": True,
                "memory_type": "short_term",
                "cached": False,
                "flushed": True,
                "flushed_count": len(cached_memories),
                "message": f"已更新 {len(cached_memories)} 条短期记忆到数据库"
            }
        except Exception as e:
            custom_logger.error(f"Failed to flush short-term memory: {e}")
            return {
                "memory_enabled": True,
                "error": str(e),
                "message": "短期记忆更新失败"
            }
    
    async def _generate_short_term_summary(
        self,
        user_id: str,
        robot_id: str,
        cache_key: str
    ):
        """
        异步生成短期记忆摘要
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
            cache_key: 缓存键
        """
        try:
            # 获取缓存的对话
            cached_dialogues = self._short_term_cache[cache_key]["dialogues"]
            
            if not cached_dialogues:
                return
            
            # 构建对话历史字符串
            dialogue_history = "\n".join([
                f"用户: {dialogue['user']}\nAI: {dialogue['ai']}" 
                for dialogue in cached_dialogues
            ])
            
            # 获取现有短期记忆
            memory = self.query_with_retry(self.db, self._get_memory_record, user_id, robot_id)
            existing_short_term = memory["short_term_memory"] if memory else ""
            
            # 构建提示词
            system_prompt = """你是一个专业的记忆总结专家。你的任务是将用户的多轮对话内容总结成简洁的一句话摘要。
要求：
1. 只输出总结内容，不要添加任何其他文字
2. 摘要要简洁明了，突出对话的核心内容
3. 如果对话内容无特殊意义，可以输出"日常对话"
"""
            
            user_prompt = f"""请将以下对话历史总结成一句话：

现有短期记忆: {existing_short_term}

对话历史:
{dialogue_history}

请提供简洁的一句话摘要，输出json格式的结果：
{{
    "summary": "总结内容"
}}
"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # 调用LLM生成摘要
            summary_result = await self.llm_service.chat_completion(
                messages=messages,
                model_pool=["qwen_plus"],
                temperature=0.3,
                max_tokens=100,
                parse_json=True,
                retry_on_error=True
            )
            
            summary_content = summary_result.get("summary", "日常对话")
            
            # 添加时间戳
            timestamp = datetime.now().strftime("%Y-%m-%d")
            summary_with_time = f"[{timestamp}] {summary_content}"
            
            # 合并到现有短期记忆
            if existing_short_term:
                combined = f"{existing_short_term}\n{summary_with_time}"
            else:
                combined = summary_with_time
            
            # 限制短期记忆总长度（保留最后5000字符）
            if len(combined) > 5000:
                combined = combined[-5000:]
            
            # 更新数据库
            self.query_with_retry(
                self.db, 
                self._update_short_term_memory, 
                user_id, 
                robot_id, 
                combined,
                len(cached_dialogues)  # 增加相应的对话计数
            )
            
            custom_logger.info(
                f"Short-term memory summary generated for {cache_key}: "
                f"{len(cached_dialogues)} dialogues → summary: {summary_content[:50]}..."
            )
            
            # 清空对话缓存并重置计数器
            self._short_term_cache[cache_key]["dialogues"] = []
            self._short_term_cache[cache_key]["count"] = 0
            
        except Exception as e:
            custom_logger.error(f"Failed to generate short-term summary: {e}")
    
    async def _handle_long_term_memory_async(
        self,
        user_id: str,
        character_id: str,
        memory_content: str
    ):
        """
        异步处理长期记忆
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
            memory_content: 需要存储的记忆内容
        """
        try:
            # 直接处理长期记忆
            await self._handle_long_term_memory(
                user_id, character_id, memory_content
            )
            custom_logger.info(f"Long-term memory async update completed for user {user_id}")
        except Exception as e:
            custom_logger.error(f"Failed to async update long-term memory for user {user_id}: {e}")

    async def _handle_long_term_memory(
        self,
        user_id: str,
        robot_id: str,
        memory_content: str
    ) -> Dict:
        """
        处理长期记忆
        
        策略：立即更新到MySQL
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
            memory_content: 记忆内容
        
        Returns:
            处理结果
        """
        try:
            # 获取现有记录
            memory = self.query_with_retry(self.db, self._get_memory_record, user_id, robot_id)
            
            if not memory:
                return {"error": "记忆记录不存在"}
            
            existing_long_term = memory["long_term_memory"] or ""
            
            # 解析现有长期记忆为结构化数据
            existing_memories = []
            if existing_long_term:
                try:
                    # 尝试解析为JSON数组格式
                    existing_memories = json.loads(existing_long_term)
                except json.JSONDecodeError:
                    # 如果不是JSON格式，按行分割处理旧格式
                    lines = existing_long_term.strip().split('\n')
                    for line in lines:
                        # 尝试提取时间戳和内容
                        if line.startswith('[') and ']' in line:
                            # 格式如: [2025-11-17] 内容
                            end_bracket = line.find(']')
                            timestamp = line[1:end_bracket]
                            content = line[end_bracket + 2:]
                            existing_memories.append({
                                "time": timestamp,
                                "content": content
                            })
                        else:
                            # 没有时间戳的旧内容
                            existing_memories.append({
                                "time": "unknown",
                                "content": line
                            })
            
            # 添加新记忆（带时间戳）
            timestamp = datetime.now().strftime("%Y-%m-%d")
            new_memory_entry = {
                "time": timestamp,
                "content": memory_content
            }
            
            # 使用LLM合并和总结记忆
            updated_memories = await self._summarize_memories(
                existing_memories, 
                new_memory_entry, 
                user_id
            )
            
            # 保持最多5条记忆
            if len(updated_memories) > 5:
                updated_memories = updated_memories[-5:]
            
            # 转换为JSON字符串存储
            combined = json.dumps(updated_memories, ensure_ascii=False, indent=2)
            
            # 更新数据库
            self.query_with_retry(
                self.db,
                self._update_long_term_memory,
                user_id,
                robot_id,
                combined
            )
            
            custom_logger.info(
                f"Long-term memory updated for user {user_id}: {memory_content[:50]}..."
            )
            
            return {
                "memory_enabled": True,
                "memory_type": "long_term",
                "updated": True,
                "structured_memories": updated_memories,
                "message": "长期记忆已立即更新"
            }
        except Exception as e:
            custom_logger.error(f"Failed to update long-term memory: {e}")
            return {
                "memory_enabled": True,
                "error": str(e),
                "message": "长期记忆更新失败"
            }
    
    async def _summarize_memories(
        self,
        existing_memories: List[Dict],
        new_memory: Dict,
        user_id: str
    ) -> List[Dict]:
        """
        使用LLM合并和总结记忆
        
        Args:
            existing_memories: 现有记忆列表
            new_memory: 新记忆
            user_id: 用户ID
            
        Returns:
            更新后的记忆列表
        """
        # 构建系统提示
        system_prompt = """你是一个专业的记忆管理专家。你的任务是帮助AI助手管理用户的长期记忆。

你需要：
1. 分析用户的现有记忆和新信息
2. 判断新信息是否与现有记忆重复
3. 如果重复，更新现有记忆条目并更新时间戳
4. 如果不重复，添加为新记忆
5. 如果现有记忆超过5条，合并最相关的记忆条目

请以严格的JSON数组格式返回结果，每个记忆条目包含"time"和"content"字段。

示例输出格式：
[
  {"time": "2025-11-17", "content": "用户爱吃香蕉"},
  {"time": "2025-11-18", "content": "用户希望被称呼为小甜心"},
  {"time": "2025-11-21", "content": "用户喜欢尿床和吃香蕉"}
]

注意事项：
1. 保持最多5个记忆条目
2. 确保时间戳是最新的
3. 合并相关或重复的信息
4. 只输出JSON，不要添加解释文字
"""

        # 构建用户提示
        user_prompt = f"""用户ID: {user_id}

现有记忆:
{json.dumps(existing_memories, ensure_ascii=False, indent=2)}

新记忆:
{json.dumps(new_memory, ensure_ascii=False, indent=2)}

请根据以上信息更新记忆列表:
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            result = await self.llm_service.chat_completion(
                messages=messages,
                model_pool=["qwen_plus", "qwen_max"],
                temperature=0.3,
                top_p=0.8,
                max_tokens=500,
                response_format="json_object",
                parse_json=True,
                retry_on_error=True
            )
            
            # 验证返回结果
            if isinstance(result, list):
                # 确保每个条目都有必要的字段
                validated_memories = []
                for item in result:
                    if isinstance(item, dict) and "time" in item and "content" in item:
                        validated_memories.append({
                            "time": str(item["time"]),
                            "content": str(item["content"])
                        })
                return validated_memories[:5]  # 最多5条
            
            # 如果解析失败，回退到简单添加方式
            custom_logger.warning("Memory summarization failed, falling back to simple addition")
            
        except Exception as e:
            custom_logger.error(f"Memory summarization failed: {e}")
        
        # 出错时的回退方案：简单添加新记忆
        updated_memories = existing_memories.copy()
        updated_memories.append(new_memory)
        
        # 保持最多5条记忆
        if len(updated_memories) > 5:
            updated_memories = updated_memories[-5:]
            
        return updated_memories
    
    async def get_memory_context(
        self,
        user_id: str,
        robot_id: str
    ) -> Dict[str, str]:
        """
        获取用户的记忆上下文（用于生成回复时参考）
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
        
        Returns:
            {
                "short_term": "短期记忆内容",
                "long_term": "长期记忆内容"
            }
        """
        if user_id == 'guest':
            return {"short_term": "", "long_term": ""}
        
        try:
            memory = self.query_with_retry(self.db, self._get_memory_record, user_id, robot_id)
            
            if not memory:
                return {"short_term": "", "long_term": ""}
            
            return {
                "short_term": memory["short_term_memory"],
                "long_term": memory["long_term_memory"]
            }
        except Exception as e:
            custom_logger.error(f"Failed to get memory context: {e}")
            return {"short_term": "", "long_term": ""}
    
    async def force_flush_short_term(self, user_id: str, robot_id: str) -> Dict:
        """
        强制刷新短期记忆缓存（不等7轮）
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
        
        Returns:
            刷新结果
        """
        cache_key = f"{user_id}:{robot_id}"
        
        if cache_key not in self._short_term_cache or (
                not self._short_term_cache[cache_key]["memories"] and 
                not self._short_term_cache[cache_key]["dialogues"]):
            return {"message": "无待更新的短期记忆"}
        
        # 刷新常规短期记忆
        result = {}
        if self._short_term_cache[cache_key]["memories"]:
            result = await self._flush_short_term_cache(user_id, robot_id, cache_key)
        
        # 生成对话摘要
        if self._short_term_cache[cache_key]["dialogues"]:
            await self._generate_short_term_summary(user_id, robot_id, cache_key)
        
        return result or {"message": "已处理短期记忆刷新"}
    
    async def clear_memory(self, user_id: str, robot_id: str) -> bool:
        """
        清除用户记忆
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
        
        Returns:
            是否成功
        """
        try:
            # 1. 清除数据库记录
            result = self.db.execute(
                text("""
                    DELETE FROM chat_memory
                    WHERE user_id = :user_id 
                    AND robot_id = :robot_id
                """),
                {"user_id": user_id, "robot_id": robot_id}
            )
            self.db.commit()
            
            # 2. 清除缓存
            cache_key = f"{user_id}:{robot_id}"
            if cache_key in self._short_term_cache:
                del self._short_term_cache[cache_key]
            
            custom_logger.info(f"Memory cleared for user {user_id}, robot {robot_id}")
            return True
        except Exception as e:
            custom_logger.error(f"Failed to clear memory: {e}")
            self.db.rollback()
            return False
    
    async def get_memory_stats(self, user_id: str, robot_id: str) -> Dict:
        """
        获取记忆统计信息
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
        
        Returns:
            统计信息
        """
        try:
            memory = self.query_with_retry(self.db, self._get_memory_record, user_id, robot_id)
            
            if not memory:
                return {
                    "exists": False,
                    "message": "无记忆记录"
                }
            
            cache_key = f"{user_id}:{robot_id}"
            pending_short_term = len(self._short_term_cache.get(cache_key, {}).get("memories", []))
            
            return {
                "exists": True,
                "conversation_count": memory["conversation_count"],
                "short_term_length": len(memory["short_term_memory"]),
                "long_term_length": len(memory["long_term_memory"]),
                "pending_short_term": pending_short_term,
                "remaining_rounds": self.short_term_update_interval - (memory["conversation_count"] % self.short_term_update_interval),
                "last_update": memory["updated_at"].isoformat() if memory["updated_at"] else None
            }
        except Exception as e:
            custom_logger.error(f"Failed to get memory stats: {e}")
            return {"exists": False, "error": str(e)}
