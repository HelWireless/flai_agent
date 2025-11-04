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

from ..custom_logger import custom_logger
from .memory_classifier import MemoryClassifier


class PersistentMemoryService:
    """持久化记忆服务 - 管理MySQL中的chat_memory表"""
    
    # 类级别的短期记忆缓存（内存中）
    _short_term_cache = defaultdict(lambda: {"memories": [], "count": 0})
    
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
        self.config = config or {}
        
        # 配置参数
        self.short_term_update_interval = self.config.get('short_term_update_interval', 10)  # 每10轮更新
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
           - short_term: 缓存，累积10轮后批量更新
           - long_term: 立即更新到MySQL
        
        Args:
            user_id: 用户ID
            character_id: 角色ID（即 robot_id）
            user_message: 用户消息
            ai_response: AI回复
        
        Returns:
            处理结果字典
        """
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
            memory = self.query_with_retry(self.db, self._get_memory_record, user_id, character_id)
            if not memory:
                self.query_with_retry(self.db, self._create_memory_record, user_id, character_id)
                memory = self.query_with_retry(self.db, self._get_memory_record, user_id, character_id)
        except Exception as e:
            custom_logger.error(f"Failed to get/create memory record: {e}")
            return {"memory_enabled": False, "error": str(e)}
        
        # 2. 使用 LLM 判断记忆类型
        classification = await self.classifier.classify_memory_type(
            user_message=user_message,
            ai_response=ai_response
        )
        
        memory_type = classification["memory_type"]
        memory_content = classification["memory_content"]
        
        custom_logger.info(
            f"Memory classification for user {user_id}: "
            f"type={memory_type}, content={memory_content[:50] if memory_content else 'N/A'}..."
        )
        
        # 3. 根据类型处理
        if memory_type == "none":
            # 不需要记忆，但计数器+1
            try:
                self.query_with_retry(self.db, self._increment_conversation_count, user_id, character_id)
            except Exception as e:
                custom_logger.error(f"Failed to increment count: {e}")
            
            return {
                "memory_enabled": True,
                "memory_type": "none",
                "message": "日常对话，不需要记忆"
            }
        
        elif memory_type == "short_term":
            # 短期记忆：缓存，10轮后批量更新
            return await self._handle_short_term_memory(
                user_id, character_id, memory_content
            )
        
        elif memory_type == "long_term":
            # 长期记忆：立即更新
            return await self._handle_long_term_memory(
                user_id, character_id, memory_content
            )
        
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
        3. 如果达到10轮，批量更新到MySQL并清空缓存
        
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
            # 达到10轮，批量更新
            return await self._flush_short_term_cache(user_id, robot_id, cache_key)
        else:
            # 还没到10轮，继续缓存（但仍要增加数据库计数器）
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
            self._short_term_cache[cache_key] = {"memories": [], "count": 0}
            
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
            
            # 追加到长期记忆（带时间戳）
            timestamp = datetime.now().strftime("%Y-%m-%d")
            new_memory = f"[{timestamp}] {memory_content}"
            
            if existing_long_term:
                combined = f"{existing_long_term}\n{new_memory}"
            else:
                combined = new_memory
            
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
                "message": "长期记忆已立即更新"
            }
        except Exception as e:
            custom_logger.error(f"Failed to update long-term memory: {e}")
            return {
                "memory_enabled": True,
                "error": str(e),
                "message": "长期记忆更新失败"
            }
    
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
        强制刷新短期记忆缓存（不等10轮）
        
        Args:
            user_id: 用户ID
            robot_id: 机器人ID
        
        Returns:
            刷新结果
        """
        cache_key = f"{user_id}:{robot_id}"
        
        if cache_key not in self._short_term_cache or not self._short_term_cache[cache_key]["memories"]:
            return {"message": "无待更新的短期记忆"}
        
        return await self._flush_short_term_cache(user_id, robot_id, cache_key)
    
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
