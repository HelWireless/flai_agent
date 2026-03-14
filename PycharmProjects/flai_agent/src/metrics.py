"""
应用程序指标监控模块

提供关键业务指标的监控和统计功能
"""

import time
import threading
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class RequestMetrics:
    """请求指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0
    
    @property
    def avg_duration(self) -> float:
        """平均响应时间"""
        return (self.total_duration / self.total_requests) if self.total_requests > 0 else 0.0


@dataclass 
class ConversationMetrics:
    """对话指标"""
    conversation_count: int = 0
    message_count: int = 0
    total_tokens: int = 0
    avg_messages_per_conversation: float = 0.0
    avg_tokens_per_message: float = 0.0


@dataclass
class ErrorMetrics:
    """错误指标"""
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_hour_errors: int = 0
    last_24h_errors: int = 0


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self.requests: Dict[str, RequestMetrics] = defaultdict(RequestMetrics)
        self.conversations: Dict[str, ConversationMetrics] = defaultdict(ConversationMetrics)
        self.errors: Dict[str, ErrorMetrics] = defaultdict(ErrorMetrics)
        self._lock = threading.RLock()
        self._start_time = datetime.now()
        
    def record_request(self, 
                      endpoint: str, 
                      duration: float, 
                      success: bool = True,
                      error_type: Optional[str] = None):
        """记录请求指标"""
        with self._lock:
            metrics = self.requests[endpoint]
            metrics.total_requests += 1
            metrics.total_duration += duration
            metrics.min_duration = min(metrics.min_duration, duration)
            metrics.max_duration = max(metrics.max_duration, duration)
            
            if success:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1
                if error_type:
                    self.record_error(endpoint, error_type)
    
    def record_conversation(self, 
                          world_type: str, 
                          message_count: int, 
                          token_count: int):
        """记录对话指标"""
        with self._lock:
            metrics = self.conversations[world_type]
            metrics.conversation_count += 1
            metrics.message_count += message_count
            metrics.total_tokens += token_count
            
            if metrics.conversation_count > 0:
                metrics.avg_messages_per_conversation = metrics.message_count / metrics.conversation_count
                metrics.avg_tokens_per_message = metrics.total_tokens / metrics.message_count if metrics.message_count > 0 else 0.0
    
    def record_error(self, component: str, error_type: str):
        """记录错误指标"""
        with self._lock:
            metrics = self.errors[component]
            metrics.error_counts[error_type] += 1
            
            now = datetime.now()
            # 简化处理：每次记录都增加计数器
            metrics.last_hour_errors += 1
            metrics.last_24h_errors += 1
    
    def get_health_status(self) -> Dict[str, any]:
        """获取系统健康状态"""
        with self._lock:
            # 计算总体成功率
            total_requests = sum(m.total_requests for m in self.requests.values())
            successful_requests = sum(m.successful_requests for m in self.requests.values())
            overall_success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 100.0
            
            # 计算总体平均响应时间
            total_duration = sum(m.total_duration for m in self.requests.values())
            avg_response_time = (total_duration / total_requests) if total_requests > 0 else 0.0
            
            # 获取最活跃的端点
            active_endpoints = sorted(
                [(endpoint, metrics.total_requests) for endpoint, metrics in self.requests.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            # 获取最常见的错误
            top_errors = []
            for component, error_metrics in self.errors.items():
                if error_metrics.error_counts:
                    top_error = max(error_metrics.error_counts.items(), key=lambda x: x[1])
                    top_errors.append({
                        "component": component,
                        "error_type": top_error[0],
                        "count": top_error[1]
                    })
            
            return {
                "status": "healthy" if overall_success_rate > 95 and avg_response_time < 5.0 else "warning",
                "uptime_hours": (datetime.now() - self._start_time).total_seconds() / 3600,
                "overall_success_rate": round(overall_success_rate, 2),
                "avg_response_time": round(avg_response_time, 3),
                "total_requests": total_requests,
                "active_endpoints": active_endpoints,
                "top_errors": top_errors
            }
    
    def get_detailed_metrics(self) -> Dict[str, any]:
        """获取详细指标"""
        with self._lock:
            # 主机请求指标
            request_metrics = {}
            for endpoint, metrics in self.requests.items():
                request_metrics[endpoint] = {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "success_rate": round(metrics.success_rate, 2),
                    "avg_duration": round(metrics.avg_duration, 3),
                    "min_duration": round(metrics.min_duration, 3) if metrics.min_duration != float('inf') else 0,
                    "max_duration": round(metrics.max_duration, 3)
                }
            
            # 对话指标
            conversation_metrics = {}
            for world_type, metrics in self.conversations.items():
                conversation_metrics[world_type] = {
                    "conversation_count": metrics.conversation_count,
                    "message_count": metrics.message_count,
                    "total_tokens": metrics.total_tokens,
                    "avg_messages_per_conversation": round(metrics.avg_messages_per_conversation, 2),
                    "avg_tokens_per_message": round(metrics.avg_tokens_per_message, 2)
                }
            
            # 错误指标
            error_metrics = {}
            for component, metrics in self.errors.items():
                error_metrics[component] = {
                    "total_errors": sum(metrics.error_counts.values()),
                    "error_breakdown": dict(metrics.error_counts),
                    "last_hour_errors": metrics.last_hour_errors,
                    "last_24h_errors": metrics.last_24h_errors
                }
            
            return {
                "timestamp": datetime.now().isoformat(),
                "requests": request_metrics,
                "conversations": conversation_metrics,
                "errors": error_metrics,
                "health_status": self.get_health_status()
            }


# 全局指标收集器实例
metrics_collector = MetricsCollector()


def track_request_performance(endpoint: str):
    """请求性能追踪装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_type = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                duration = time.time() - start_time
                metrics_collector.record_request(
                    endpoint=endpoint,
                    duration=duration,
                    success=success,
                    error_type=error_type
                )
        return wrapper
    return decorator


def track_conversation_metrics(world_type: str):
    """对话指标追踪装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            message_count = 0
            token_count = 0
            
            try:
                result = func(*args, **kwargs)
                
                # 尝试从结果中提取消息和token计数
                if hasattr(result, 'get'):
                    content = result.get('content', '')
                    message_count = 1  # 假设每次调用产生一条消息
                    token_count = len(content) // 4  # 估算token数
                
                return result
            except Exception as e:
                raise
            finally:
                if message_count > 0:
                    metrics_collector.record_conversation(
                        world_type=world_type,
                        message_count=message_count,
                        token_count=token_count
                    )
        return wrapper
    return decorator