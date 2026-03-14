"""
错误处理和日志系统优化模块

提供了详细的错误分类、处理机制和增强的日志记录功能
"""

import traceback
import time
import functools
from typing import Dict, Any, Optional, Callable, TypeVar, cast
from datetime import datetime
from enum import Enum

from .custom_logger import custom_logger


class ErrorCode(Enum):
    """错误代码枚举"""
    # COC系统错误 (1XXX)
    COC_GAME_NOT_FOUND = 1001
    COC_INVALID_ACTION = 1002
    COC_CHARACTER_CREATE_FAILED = 1003
    COC_SAVE_LOAD_ERROR = 1004
    COC_LLM_CALL_FAILED = 1005
    COC_INVALID_GAME_STATE = 1006
    
    # 副本世界错误 (2XXX)
    IW_WORLD_NOT_FOUND = 2001
    IW_INVALID_WORLD_SETTING = 2002
    IW_CHARACTER_SWITCH_FAILED = 2003
    IW_CONFIG_LOAD_FAILED = 2004
    IW_LLM_CALL_FAILED = 2005
    
    # 配置系统错误 (3XXX)
    CONFIG_FILE_NOT_FOUND = 3001
    CONFIG_DB_CONNECTION_FAILED = 3002
    CONFIG_INVALID_FORMAT = 3003
    CONFIG_LOAD_TIMEOUT = 3004
    
    # 数据库错误 (4XXX)
    DB_CONNECTION_ERROR = 4001
    DB_QUERY_TIMEOUT = 4002
    DB_TRANSACTION_FAILED = 4003
    
    # LLM服务错误 (5XXX)
    LLM_TIMEOUT = 5001
    LLM_RATE_LIMIT = 5002
    LLM_INVALID_RESPONSE = 5003
    LLM_MODEL_NOT_AVAILABLE = 5004
    
    # 通用错误 (9XXX)
    UNKNOWN_ERROR = 9001
    VALIDATION_ERROR = 9002
    PERMISSION_DENIED = 9003


class GameError(Exception):
    """游戏系统基础错误类"""
    
    def __init__(self, 
                 error_code: ErrorCode, 
                 message: str, 
                 details: Optional[Dict] = None,
                 original_exception: Optional[Exception] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.now()
        super().__init__(f"[{error_code.value}] {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应"""
        result = {
            "error_code": self.error_code.value,
            "error_type": self.error_code.name,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }
        
        if self.details:
            result["details"] = self.details
            
        return result


class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def handle_coc_error(func):
        """COC系统的错误处理装饰器"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            except GameError:
                # 已经处理的GameError直接重新抛出
                raise
            except FileNotFoundError as e:
                custom_logger.error(f"COC配置文件未找到: {e}", 
                                  extra={"function": func.__name__, "args": str(args)})
                raise GameError(
                    ErrorCode.COC_INVALID_GAME_STATE,
                    "游戏配置文件未找到，请联系管理员",
                    {"file": str(e.filename) if hasattr(e, 'filename') else "unknown"},
                    e
                )
            except TimeoutError as e:
                custom_logger.error(f"COC操作超时: {e}", 
                                  extra={"function": func.__name__, "duration": time.time() - start_time})
                raise GameError(
                    ErrorCode.LLM_TIMEOUT,
                    "操作超时，请稍后重试",
                    {"duration": time.time() - start_time},
                    e
                )
            except Exception as e:
                custom_logger.exception(f"COC系统未处理的错误: {e}", 
                                      extra={"function": func.__name__, "duration": time.time() - start_time})
                raise GameError(
                    ErrorCode.UNKNOWN_ERROR,
                    "系统内部错误，请稍后重试",
                    {"function": func.__name__},
                    e
                )
        return wrapper
    
    @staticmethod
    
    def handle_iw_error(func):
        """副本世界系统的错误处理装饰器"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            except GameError:
                # 已经处理的GameError直接重新抛出
                raise
            except FileNotFoundError as e:
                custom_logger.error(f"副本世界配置文件未找到: {e}", 
                                  extra={"function": func.__name__, "args": str(args)})
                raise GameError(
                    ErrorCode.IW_CONFIG_LOAD_FAILED,
                    "世界配置文件未找到，请联系管理员",
                    {"file": str(e.filename) if hasattr(e, 'filename') else "unknown"},
                    e
                )
            except TimeoutError as e:
                custom_logger.error(f"副本世界操作超时: {e}", 
                                  extra={"function": func.__name__, "duration": time.time() - start_time})
                raise GameError(
                    ErrorCode.LLM_TIMEOUT,
                    "操作超时，请稍后重试", 
                    {"duration": time.time() - start_time},
                    e
                )
            except Exception as e:
                custom_logger.exception(f"副本世界系统未处理的错误: {e}", 
                                      extra={"function": func.__name__, "duration": time.time() - start_time})
                raise GameError(
                    ErrorCode.UNKNOWN_ERROR,
                    "系统内部错误，请稍后重试",
                    {"function": func.__name__},
                    e
                )
        return wrapper
    
    @staticmethod
    def handle_config_error(func):
        """配置系统的错误处理装饰器"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            except FileNotFoundError as e:
                custom_logger.error(f"配置文件未找到: {e}", 
                                  extra={"function": func.__name__, "args": str(args)})
                raise GameError(
                    ErrorCode.CONFIG_FILE_NOT_FOUND,
                    "配置文件不存在",
                    {"file": str(e.filename) if hasattr(e, 'filename') else "unknown"},
                    e
                )
            except TimeoutError as e:
                custom_logger.error(f"配置加载超时: {e}",
                                  extra={"function": func.__name__, "duration": time.time() - start_time})
                raise GameError(
                    ErrorCode.CONFIG_LOAD_TIMEOUT,
                    "配置加载超时，请稍后重试",
                    {"duration": time.time() - start_time},
                    e
                )
            except Exception as e:
                custom_logger.exception(f"配置系统错误: {e}",
                                      extra={"function": func.__name__, "duration": time.time() - start_time})
                raise GameError(
                    ErrorCode.CONFIG_INVALID_FORMAT,
                    "配置文件格式错误",
                    {"function": func.__name__},
                    e
                )
        return wrapper


class PerformanceMonitor:
    """性能监控器"""
    
    @staticmethod
    def track_llm_performance(func):
        """LLM调用的性能监控装饰器"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # 记录性能指标
                custom_logger.info(f"LLM调用性能", 
                                 extra={
                                     "function": func.__name__,
                                     "duration": round(duration, 3),
                                     "tokens": getattr(result, 'tokens', 'unknown'),
                                     "model": kwargs.get('model_pool', ['unknown'])[0]
                                 })
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                custom_logger.error(f"LLM调用失败", 
                                  extra={
                                      "function": func.__name__,
                                      "duration": round(duration, 3),
                                      "error": str(e)
                                  })
                raise
        return wrapper
    
    @staticmethod
    def track_database_performance(func):
        """数据库操作的性能监控装饰器"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # 记录性能指标
                if duration > 1.0:  # 超过1秒的数据库操作需要关注
                    custom_logger.warning(f"慢数据库查询", 
                                        extra={
                                            "function": func.__name__,
                                            "duration": round(duration, 3),
                                            "args": str(args[:2])  # 只记录前两个参数避免敏感信息
                                        })
                else:
                    custom_logger.debug(f"数据库操作性能", 
                                      extra={
                                          "function": func.__name__,
                                          "duration": round(duration, 3)
                                      })
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                custom_logger.error(f"数据库操作失败", 
                                  extra={
                                      "function": func.__name__,
                                      "duration": round(duration, 3),
                                      "error": str(e)
                                  })
                raise
        return wrapper