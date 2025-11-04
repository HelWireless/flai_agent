# Custom Logger Using Loguru

import logging
import sys
from pathlib import Path
from loguru import logger
import yaml
from datetime import datetime, timedelta
import os


class InterceptHandler(logging.Handler):
    loglevel_mapping = {
        50: 'CRITICAL',
        40: 'ERROR',
        30: 'WARNING',
        20: 'INFO',
        10: 'DEBUG',
        0: 'NOTSET',
    }

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except AttributeError:
            level = self.loglevel_mapping[record.levelno]

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        log = logger.bind(request_id='app')
        log.opt(
            depth=depth,
            exception=record.exc_info
        ).log(level,record.getMessage())


class CustomizeLogger:

    @classmethod
    def make_logger(cls, config_path: Path):
        config = cls.load_logging_config(config_path)
        logging_config = config.get('logger')

        logger = cls.customize_logging(
            Path(logging_config.get('path')),
            level=logging_config.get('level'),
            retention=logging_config.get('retention'),
            rotation=logging_config.get('rotation'),
            format=logging_config.get('format')
        )
        return logger

    @classmethod
    def get_weekly_log_path(cls):
        """
        获取按周划分的日志路径
        
        规则：
        - 每周一个日志文件（周一到周日）
        - 文件名：开始日期_结束日期.log
        - 按开始日期的年月归档：logs/YYYY-MM/YYYY-MM-DD_YYYY-MM-DD.log
        """
        now = datetime.now()
        
        # 计算本周的开始日期（周一）
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        week_start = now - timedelta(days=weekday)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 计算本周的结束日期（周日）
        week_end = week_start + timedelta(days=6)
        
        # 格式化日期
        start_date_str = week_start.strftime("%Y-%m-%d")
        end_date_str = week_end.strftime("%Y-%m-%d")
        
        # 按开始日期的年月创建文件夹
        year_month = week_start.strftime("%Y-%m")
        
        # 构建日志路径
        log_dir = Path("logs") / year_month
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件名：开始日期_结束日期.log
        log_filename = f"{start_date_str}_{end_date_str}.log"
        
        return str(log_dir / log_filename)
    
    @classmethod
    def cleanup_old_logs(cls, retention_months=6):
        """
        清理超过保留期的日志
        
        Args:
            retention_months: 保留月数，默认6个月
        """
        logs_dir = Path("logs")
        if not logs_dir.exists():
            return 0
        
        # 计算截止日期（保留最近N个月）
        cutoff_date = datetime.now() - timedelta(days=retention_months * 30)
        cutoff_month = cutoff_date.strftime("%Y-%m")
        
        deleted_count = 0
        
        # 遍历 logs 目录下的所有月份文件夹
        for month_dir in logs_dir.iterdir():
            if not month_dir.is_dir():
                continue
            
            # 检查文件夹名是否是月份格式 (YYYY-MM)
            if month_dir.name.count('-') != 1:
                continue
            
            try:
                # 比较月份，删除早于截止月份的目录
                if month_dir.name < cutoff_month:
                    print(f"清理旧日志目录: {month_dir}")
                    import shutil
                    shutil.rmtree(month_dir)
                    deleted_count += 1
            except Exception as e:
                print(f"清理日志目录失败 {month_dir}: {e}")
        
        if deleted_count > 0:
            print(f"已清理 {deleted_count} 个旧日志目录（{retention_months}个月前）")
        
        return deleted_count

    @classmethod
    def customize_logging(cls,
            filepath: Path,
            level: str,
            rotation: str,
            retention: str,
            format: str
    ):
        # 使用自定义的日志路径（按周划分）
        weekly_log_path = cls.get_weekly_log_path()
        
        logger.remove()
        logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
            format=format
        )
        logger.add(
            weekly_log_path,
            rotation="1 week",  # 每周轮转
            retention=retention,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
            format=format
        )
        logging.basicConfig(handlers=[InterceptHandler()], level=0)
        logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
        for _log in ['uvicorn',
                    #  'uvicorn.error', # uvicorn.error 应该是继承过 uvicorn，而 uvicorn 有默认的propagate msg 的行为，注销即可；解决日志重复出现的问题
                     'fastapi'
                     ]:
            _logger = logging.getLogger(_log)
            _logger.handlers = [InterceptHandler()]
        
        # 启动时清理旧日志
        cls.cleanup_old_logs(retention_months=6)

        return logger.bind(request_id=None, method=None)


    @classmethod
    def load_logging_config(cls, config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                config = yaml.safe_load(config_file)
                return config
        except FileNotFoundError:
            print(f"无法找到配置文件: {config_path}")
            # 可以在这里添加更多的错误处理逻辑
        except yaml.YAMLError as e:
            print(f"YAML 解析错误: {e}")
        except UnicodeDecodeError:
            print(f"文件编码错误,请确保 {config_path} 使用 UTF-8 编码")


config_path = Path(__file__).parent.parent / "config" / "config.yaml"
custom_logger = CustomizeLogger.make_logger(config_path=config_path)
