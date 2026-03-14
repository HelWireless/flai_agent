"""
副本世界服务核心功能单元测试
测试副本世界服务的各个核心方法和错误处理
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from unittest import IsolatedAsyncioTestCase

from src.services.instance_world_service import FreakWorldService, GameStatus
from src.models.instance_world import FreakWorldGameState
from src.error_handler import GameError, ErrorCode
from src.schemas import IWChatRequest


class TestInstanceWorldService(IsolatedAsyncioTestCase):
    """副本世界服务单元测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_llm = AsyncMock()
        self.mock_db = Mock()
        self.config = {"test": True}
        
        # 创建服务实例
        self.service = FreakWorldService(self.mock_llm, self.mock_db, self.config)
        
        # 模拟FreakWorldGameState
        self.session = Mock(spec=FreakWorldGameState)
        self.session.session_id = "test_iw_session_001"
        self.session.user_id = 1000001
        self.session.freak_world_id = 1
        self.session.gm_id = "gm_01"
        self.session.game_status = GameStatus.PLAYING
        self.session.gender_preference = "female"
        self.session.current_character_id = "character_01"
        self.session.characters = [{"id": "character_01", "name": "测试角色"}]
        self.session.dialogue_summary = None
        self.session.random_seed = 12345
        
    def test_generate_session_id(self):
        """测试session ID生成"""
        session_id = self.service._generate_session_id()
        assert session_id.startswith("fw_")
        assert len(session_id) == 16  # fw_ + 13位UUID
        
    def test_generate_save_id(self):
        """测试save ID生成"""
        save_id = self.service._generate_save_id()
        assert save_id.startswith("save_")
        assert len(save_id) > 10
        
    def test_get_random_gm_id(self):
        """测试随机GM ID获取"""
        # 模拟GM ID列表
        with patch('src.services.instance_world_service.get_gm_ids', return_value=['gm_01', 'gm_02']):
            gm_id = self.service._get_random_gm_id()
            assert gm_id in ['gm_01', 'gm_02']
            
    def test_parse_world_id_with_prefix(self):
        """测试带前缀的世界ID解析"""
        result = self.service._parse_world_id("world_10")
        assert result == 10
        
    def test_parse_world_id_without_prefix(self):
        """测试不带前缀的世界ID解析"""
        result = self.service._parse_world_id("5")
        assert result == 5
        
    def test_parse_world_id_invalid(self):
        """测试无效世界ID解析"""
        result = self.service._parse_world_id("invalid_world")
        assert result == 1  # 默认值
        
    def test_format_world_id(self):
        """测试世界ID格式化"""
        result = self.service._format_world_id(5)
        assert result == "world_05"
        
    @pytest.mark.asyncio
    async def test_step3_playing_success(self):
        """测试正常的游戏对话流程"""
        # 模拟LLM响应
        self.mock_llm.chat_completion.return_value = {
            "content": "角色回复了你说的话"
        }
        
        # 模拟必要的方法
        with patch.object(self.service, '_get_dialogue_history', return_value=[]):
            with patch('src.services.instance_world_service.build_system_prompt', return_value="系统提示"):
                with patch.object(self.service, '_build_messages_with_summary', return_value=[
                    {"role": "system", "content": "系统提示"},
                    {"role": "user", "content": "用户消息"}
                ]):
                    with patch.object(self.service, '_clean_llm_content', side_effect=lambda x: x):
                        with patch.object(self.service, '_trigger_summary_if_needed'):
                            
                            request = Mock(spec=IWChatRequest)
                            request.message = "你好"
                            
                            result = await self.service._step3_playing(self.session, request)
                            
                            assert result["content"] == "角色回复了你说的话"
                            
    @pytest.mark.asyncio
    async def test_step3_playing_game_ended(self):
        """测试游戏结束状态的处理"""
        self.session.game_status = GameStatus.ENDED
        
        request = Mock(spec=IWChatRequest)
        request.message = "你好"
        
        result = await self.service._step3_playing(self.session, request)
        
        assert "游戏已结束" in result["content"]
        
    @pytest.mark.asyncio
    async def test_step3_playing_not_ready(self):
        """测试游戏未准备好的处理"""
        self.session.game_status = GameStatus.CHARACTER_SELECT
        
        request = Mock(spec=IWChatRequest)
        request.message = "你好"
        
        result = await self.service._step3_playing(self.session, request)
        
        assert "请先完成角色选择" in result["error"]
        
    @pytest.mark.asyncio
    async def test_handle_change_char_success(self):
        """测试角色切换功能"""
        # 模拟LLM响应
        self.mock_llm.chat_completion.return_value = {
            "content": "你可以与以下角色对话:\n1. 角色一\n2. 角色二"
        }
        
        # 模拟必要的方法
        with patch.object(self.service, '_get_dialogue_history', return_value=[]):
            with patch('src.services.instance_world_service.build_system_prompt', return_value="系统提示"):
                with patch.object(self.service, '_build_messages_with_summary', return_value=[
                    {"role": "system", "content": "系统提示"},
                    {"role": "user", "content": "用户消息"}
                ]):
                    with patch.object(self.service, '_clean_llm_content', side_effect=lambda x: x):
                        
                        from src.schemas import IWChatRequest
                        request = IWChatRequest(
                            user_id="1000001",
                            world_id="world_01",
                            session_id="test_session",
                            gm_id="gm_01",
                            message="",
                            step=3,
                            ext_param={"action": "change_char"}
                        )
                        
                        result = await self.service._handle_change_char(request)
                        
                        assert "你可以与以下角色对话" in result["content"]
                        
    @pytest.mark.asyncio
    async def test_handle_change_char_session_not_found(self):
        """测试角色切换时会话不存在"""
        with patch.object(self.service, '_get_session_db', return_value=None):
            
            from src.schemas import IWChatRequest
            request = IWChatRequest(
                user_id="1000001",
                world_id="world_01",
                session_id="nonexistent_session",
                gm_id="gm_01",
                message="",
                step=3,
                ext_param={"action": "change_char"}
            )
            
            result = await self.service._handle_change_char(request)
            
            assert "会话不存在" in result["error"]
            
    @pytest.mark.asyncio
    async def test_handle_change_char_not_in_game(self):
        """测试游戏未开始时的角色切换"""
        self.session.game_status = GameStatus.CHARACTER_SELECT
        
        with patch.object(self.service, '_get_session_db', return_value=self.session):
            
            from src.schemas import IWChatRequest
            request = IWChatRequest(
                user_id="1000001",
                world_id="world_01",
                session_id="test_session",
                gm_id="gm_01",
                message="",
                step=3,
                ext_param={"action": "change_char"}
            )
            
            result = await self.service._handle_change_char(request)
            
            assert "请先进入游戏后再换人" in result["error"]
            
    @pytest.mark.asyncio
    async def test_llm_call_failure_in_playing(self):
        """测试游戏对话时LLM调用失败"""
        # 模拟LLM调用失败
        self.mock_llm.chat_completion.side_effect = Exception("LLM调用失败")
        
        # 模拟必要的方法
        with patch.object(self.service, '_get_dialogue_history', return_value=[]):
            with patch('src.services.instance_world_service.build_system_prompt', return_value="系统提示"):
                with patch.object(self.service, '_build_messages_with_summary', return_value=[
                    {"role": "system", "content": "系统提示"},
                    {"role": "user", "content": "用户消息"}
                ]):
                    with patch.object(self.service, '_trigger_summary_if_needed'):
                        
                        request = Mock(spec=IWChatRequest)
                        request.message = "你好"
                        
                        result = await self.service._step3_playing(self.session, request)
                        
                        assert "抱歉" in result["content"] or "系统暂时无法响应" in result["content"]


class TestInstanceWorldErrorHandling(IsolatedAsyncioTestCase):
    """副本世界错误处理测试"""
    
    def test_iw_game_error_creation(self):
        """测试副本世界游戏错误创建"""
        error = GameError(
            ErrorCode.IW_LLM_CALL_FAILED,
            "副本世界LLM调用失败",
            details={"world_id": "world_01"},
            original_exception=Exception("原始错误")
        )
        
        assert error.error_code == ErrorCode.IW_LLM_CALL_FAILED
        assert error.message == "副本世界LLM调用失败"
        assert error.details["world_id"] == "world_01"
        
    def test_world_config_error_handling(self):
        """测试世界配置错误处理"""
        error = GameError(
            ErrorCode.IW_CONFIG_LOAD_FAILED,
            "世界配置文件加载失败",
            details={"world_id": "world_01", "file": "nonexistent.txt"}
        )
        
        # 测试错误转换为API响应格式
        error_dict = error.to_dict()
        assert error_dict["error_code"] == ErrorCode.IW_CONFIG_LOAD_FAILED.value
        assert "世界配置文件加载失败" in error_dict["message"]
        assert error_dict["details"]["world_id"] == "world_01"