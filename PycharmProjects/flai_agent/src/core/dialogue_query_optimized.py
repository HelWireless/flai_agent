"""
优化的对话查询服务
提供高性能的对话历史查询和缓存机制
"""

import asyncio
import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy import text, and_, func
from ..custom_logger import custom_logger


class OptimizedDialogueQuery:
    """优化的对话查询服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self._cache_hits = 0
        self._cache_misses = 0
        
    # ==================== 缓存管理 ====================
    
    @lru_cache(maxsize=1000)
    def _get_cache_key(self, session_id: str, max_turns: int, character_id: Optional[str] = None) -> str:
        """生成缓存键(使用LRU缓存)"""
        cache_data = f"{session_id}:{max_turns}:{character_id or ''}"
        return hashlib.md5(cache_data.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """从内存缓存获取数据（简化实现）"""
        # 这里可以使用Redis等外部缓存
        # 暂时使用内存缓存演示概念
        return None
    
    def _set_to_cache(self, cache_key: str, data: List[Dict], ttl: int = 300):
        """设置缓存（简化实现）"""
        # 这里可以实现Redis缓存或其他外部缓存
        pass
    
    def _update_cache_stats(self, hit: bool):
        """更新缓存统计"""
        if hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1
            
        # 定期输出缓存统计
        total = self._cache_hits + self._cache_misses
        if total % 100 == 0:
            hit_rate = self._cache_hits / total * 100
            custom_logger.debug(f"对话查询缓存统计: 命中率 {hit_rate:.1f}% ({self._cache_hits}/{total})")
    
    # ==================== 优化的对话历史查询 ====================
    
    async def get_dialogue_history_optimized(
        self, 
        session_id: str, 
        max_turns: int = 10,
        character_id: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Dict[str, str]]:
        """优化的对话历史查询
        
        特点:
        1. 使用索引查询优化
        2. 支持内存缓存
        3. 异步查询减少阻塞
        4. 查询字段优化
        5. 结果分页
        
        Args:
            session_id: 会话ID
            max_turns: 最大轮数（建议10-20轮）
            character_id: 第三方角色ID（可选）
            use_cache: 是否使用缓存
        """
        # 检查缓存
        if use_cache:
            cache_key = self._get_cache_key(session_id, max_turns, character_id)
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                self._update_cache_stats(hit=True)
                return cached_data
        
        self._update_cache_stats(hit=False)
        
        try:
            # 异步执行数据库查询
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._execute_dialogue_query, 
                session_id, 
                max_turns, 
                character_id
            )
            
            # 设置缓存
            if use_cache and result:
                self._set_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            custom_logger.error(f"优化对话查询失败: {e}", 
                              extra={"session_id": session_id, "character_id": character_id})
            return []
    
    def _execute_dialogue_query(
        self, 
        session_id: str, 
        max_turns: int, 
        character_id: Optional[str]
    ) -> List[Dict[str, str]]:
        """执行实际的数据库查询"""
        
        # 计算需要的消息数（每轮对话2条消息：用户+AI）
        message_limit = max_turns * 2
        
        # 使用优化的查询
        if character_id:
            # 第三方角色对话查询
            sql = text("""
                SELECT message, text, create_time
                FROM t_freak_world_dialogue 
                WHERE account_id = :session_id 
                  AND third_character_id = :character_id
                  AND del = 0
                ORDER BY id DESC
                LIMIT :limit
            """)
            
            params = {
                "session_id": session_id,
                "character_id": character_id,
                "limit": message_limit
            }
            
        else:
            # 默认角色对话查询
            sql = text("""
                SELECT message, text, create_time
                FROM t_freak_world_dialogue 
                WHERE session_id = :session_id 
                  AND del = 0
                ORDER BY id DESC
                LIMIT :limit
            """)
            
            params = {
                "session_id": session_id,
                "limit": message_limit
            }
        
        # 执行查询
        result = self.db.execute(sql, params)
        rows = result.fetchall()
        
        # 处理结果
        messages = []
        for row in rows:
            user_msg, assistant_msg, timestamp = row
            
            if assistant_msg:
                messages.append({"role": "assistant", "content": assistant_msg.strip()})
            if user_msg:
                messages.append({"role": "user", "content": user_msg.strip()})
        
        # 按时间正序排列（最早的在前）
        messages.reverse()
        
        return messages
    
    # ==================== 批量查询优化 ====================
    
    async def get_multiple_sessions_history(
        self, 
        session_ids: List[str], 
        max_turns: int = 5
    ) -> Dict[str, List[Dict[str, str]]]:
        """批量获取多个会话的对话历史
        
        使用单个查询获取多个会话数据，减少数据库往返次数
        """
        if not session_ids:
            return {}
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._execute_batch_query,
                session_ids,
                max_turns
            )
            
            return result
            
        except Exception as e:
            custom_logger.error(f"批量查询对话历史失败: {e}")
            return {session_id: [] for session_id in session_ids}
    
    def _execute_batch_query(
        self, 
        session_ids: List[str], 
        max_turns: int
    ) -> Dict[str, List[Dict[str, str]]]:
        """执行批量查询"""
        
        # 构建批量查询
        placeholders = ",".join([f":session_{i}" for i in range(len(session_ids))])
        sql = text(f"""
            SELECT session_id, message, text, create_time
            FROM t_freak_world_dialogue 
            WHERE session_id IN ({placeholders})
              AND del = 0
            ORDER BY session_id, id DESC
        """)
        
        # 构建参数
        params = {f"session_{i}": session_id for i, session_id in enumerate(session_ids)}
        
        result = self.db.execute(sql, params)
        rows = result.fetchall()
        
        # 按会话分组处理
        session_data = {}
        for row in rows:
            session_id, user_msg, assistant_msg, timestamp = row
            
            if session_id not in session_data:
                session_data[session_id] = []
            
            # 简单的轮数限制（这里可以优化为更精确的轮数计算）
            if len(session_data[session_id]) < max_turns * 2:
                if assistant_msg:
                    session_data[session_id].append({"role": "assistant", "content": assistant_msg.strip()})
                if user_msg:
                    session_data[session_id].append({"role": "user", "content": user_msg.strip()})
        
        # 对每个会话的数据按时间排序
        for session_id in session_data:
            session_data[session_id].reverse()
        
        return session_data
    
    # ==================== 对话统计和监控 ====================
    
    async def get_dialogue_stats(self, session_id: str) -> Dict[str, Any]:
        """获取对话统计信息"""
        try:
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(
                None,
                self._execute_stats_query,
                session_id
            )
            
            return stats
            
        except Exception as e:
            custom_logger.error(f"获取对话统计失败: {e}")
            return {}
    
    def _execute_stats_query(self, session_id: str) -> Dict[str, Any]:
        """执行统计查询"""
        
        # 查询基本统计信息
        sql = text("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT DATE(create_time)) as active_days,
                MIN(create_time) as first_message_time,
                MAX(create_time) as last_message_time,
                AVG(LENGTH(message)) as avg_message_length,
                AVG(LENGTH(text)) as avg_response_length
            FROM t_freak_world_dialogue 
            WHERE session_id = :session_id AND del = 0
        """)
        
        result = self.db.execute(sql, {"session_id": session_id})
        row = result.fetchone()
        
        if not row:
            return {}
        
        total_messages, active_days, first_time, last_time, avg_msg_len, avg_resp_len = row
        
        # 计算轮数（每轮2条消息）
        total_rounds = total_messages // 2
        
        return {
            "session_id": session_id,
            "total_messages": total_messages or 0,
            "total_rounds": total_rounds,
            "active_days": active_days or 0,
            "first_message_time": first_time.isoformat() if first_time else None,
            "last_message_time": last_time.isoformat() if last_time else None,
            "avg_message_length": round(avg_msg_len or 0, 2),
            "avg_response_length": round(avg_resp_len or 0, 2),
            "updated_at": datetime.now().isoformat()
        }
    
    # ==================== 数据清理和维护 ====================
    
    async def cleanup_old_dialogues(self, days: int = 90, batch_size: int = 1000):
        """清理旧对话数据（异步操作）"""
        try:
            loop = asyncio.get_event_loop()
            
            # 分批次清理避免长事务
            for offset in range(0, 100000, batch_size):  # 假设最多10万条需要清理
                deleted = await loop.run_in_executor(
                    None,
                    self._cleanup_batch,
                    days,
                    batch_size,
                    offset
                )
                
                if deleted == 0:
                    break  # 没有更多数据需要清理
                
                custom_logger.info(f"清理批次完成: 删除 {deleted} 条旧对话数据")
                
                # 小延迟避免过度占用数据库
                await asyncio.sleep(0.1)
            
            custom_logger.info(f"旧对话数据清理完成（{days}天前）")
            
        except Exception as e:
            custom_logger.error(f"清理旧对话数据失败: {e}")
    
    def _cleanup_batch(self, days: int, batch_size: int, offset: int) -> int:
        """清理一批旧数据"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 标记删除而不是物理删除，避免表锁
        sql = text("""
            UPDATE t_freak_world_dialogue 
            SET del = 1, update_time = NOW()
            WHERE del = 0 
              AND create_time < :cutoff_date
            LIMIT :batch_size
        """)
        
        result = self.db.execute(sql, {
            "cutoff_date": cutoff_date,
            "batch_size": batch_size
        })
        
        return result.rowcount