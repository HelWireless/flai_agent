# Custom Logger Using Loguru

import logging
import sys
from pathlib import Path
from loguru import logger
import yaml


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
    def customize_logging(cls,
            filepath: Path,
            level: str,
            rotation: str,
            retention: str,
            format: str
    ):

        logger.remove()
        logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
            format=format
        )
        logger.add(
            str(filepath),
            rotation=rotation,
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


config_path = Path(__file__).with_name('config.yaml')
custom_logger = CustomizeLogger.make_logger(config_path=config_path)
