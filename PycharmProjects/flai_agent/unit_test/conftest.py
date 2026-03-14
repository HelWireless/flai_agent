"""
单元测试配置文件
提供测试夹具和共享测试数据
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def mock_llm_service():
    """模拟LLM服务"""
    mock = Mock()
    mock.chat_completion.return_value = {
        "content": "这是AI的回复",
        "tokens": 100
    }
    return mock


@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    return Mock()


@pytest.fixture
def sample_investigator_card():
    """示例调查员卡片数据"""
    return {
        "name": "张三",
        "age": 30,
        "gender": "male",
        "profession": "记者",
        "attributes": {
            "STR": 70,
            "CON": 65,
            "SIZ": 70,
            "DEX": 75,
            "APP": 80,
            "INT": 80,
            "POW": 70,
            "EDU": 80
        },
        "skills": {
            "侦查": 60,
            "聆听": 50,
            "图书馆使用": 60,
            "心理学": 30
        },
        "currentHP": 13,
        "maxHP": 13,
        "currentMP": 14,
        "maxMP": 14,
        "currentSAN": 70,
        "maxSAN": 90
    }


@pytest.fixture
def sample_coc_request():
    """示例COC请求数据"""
    return {
        "user_id": "1000001",
        "world_id": "trpg_01",
        "session_id": "test_session_001",
        "gm_id": "gm_02",
        "message": "我向前走一步",
        "step": 6,
        "ext_param": {"action": "playing"}
    }


@pytest.fixture
def sample_iw_request():
    """示例副本世界请求数据"""
    return {
        "user_id": "1000001",
        "world_id": "world_01",
        "session_id": "test_iw_session_001",
        "gm_id": "gm_01",
        "message": "你好",
        "step": 3,
        "ext_param": {"action": "playing"}
    }


@pytest.fixture
def temp_config_dir():
    """创建临时配置目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()
        
        # 创建测试配置文件
        instance_world_dir = config_dir / "instance_world"
        instance_world_dir.mkdir()
        
        # 创建世界设置文件
        world_settings_dir = instance_world_dir / "world_settings"
        world_settings_dir.mkdir()
        
        setting_file = world_settings_dir / "01_abyss_tavern_setting.txt"
        setting_file.write_text("测试世界设定内容")
        
        yield config_dir


@pytest.fixture
def sample_dialogue_history():
    """示例对话历史数据"""
    return [
        {"role": "user", "content": "我进入酒馆"},
        {"role": "assistant", "content": "你走进了永夜酒馆，里面灯火通明"},
        {"role": "user", "content": "我找了个位置坐下"},
        {"role": "assistant", "content": "你在一张木桌旁坐下，酒馆老板走了过来"}
    ]


@pytest.fixture
def mock_custom_logger():
    """模拟自定义日志器"""
    with patch('src.services.coc_service.custom_logger') as mock:
        yield mock


@pytest.fixture
def enable_debug_mode():
    """启用调试模式"""
    os.environ['PROMPT_CONFIG_USE_DB'] = 'false'
    yield
    if 'PROMPT_CONFIG_USE_DB' in os.environ:
        del os.environ['PROMPT_CONFIG_USE_DB']