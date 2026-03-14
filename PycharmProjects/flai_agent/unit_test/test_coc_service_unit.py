"""
COC服务核心功能单元测试
测试COC服务的各个核心方法和错误处理
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from unittest import IsolatedAsyncioTestCase

from src.services.coc_service import COCService, GameStatus
from src.models.coc_game_state import COCGameState
from src.error_handler import GameError, ErrorCode
from src.schemas import IWChatRequest


class TestCOCService(IsolatedAsyncioTestCase):
    """COC服务单元测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_llm = AsyncMock()
        self.mock_db = Mock()
        self.config = {"test": True}
        
        # 创建服务实例
        self.service = COCService(self.mock_llm, self.mock_db, self.config)
        
        # 模拟COCGameState
        self.session = Mock(spec=COCGameState)
        self.session.session_id = "test_session_001"
        self.session.user_id = 1000001
        self.session.investigator_card = {
            "name": "测试调查员",
            "currentHP": 10,
            "currentMP": 8,
            "currentSAN": 70
        }
        self.session.game_status = GameStatus.PLAYING
        self.session.turn_number = 5
        self.session.round_number = 1
        self.session.dialogue_summary = None
        self.session.temp_data = {"gm_name": "测试GM"}
        
        # 添加必要的方法
        self.session.get_temp_data.return_value = {"gm_name": "测试GM"}
        self.session.get_investigator_card.return_value = self.session.investigator_card
        
        # 模拟数据库操作
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        
    def test_build_response(self):
        """测试构建响应方法"""
        content = "测试内容"
        result = self.service._build_response(content)
        
        assert result["content"] == content
        assert "timestamp" in result
        
    def test_error_response(self):
        """测试错误响应方法"""
        error_msg = "测试错误"
        result = self.service._build_error_response(error_msg)
        
        assert result["content"] == error_msg
        assert result["error"] is True
        
    def test_sync_investigator_status_normal(self):
        """测试正常情况下的调查员状态同步"""
        ai_content = "你受到了伤害，❤ 生命 8 💎 魔法 6 🧠 理智 65"
        
        self.service._sync_investigator_status(self.session, ai_content)
        
        # 验证数据库更新调用
        assert self.session.investigator_card is not None
        
    def test_sync_investigator_status_game_over(self):
        """测试游戏结束状态同步"""
        ai_content = "你死了，❤ 生命 0 💎 魔法 0 🧠 理智 0"
        
        self.service._sync_investigator_status(self.session, ai_content)
        
        # 应该触发游戏结束
        assert self.session.game_status == GameStatus.ENDED
        
    def test_sync_investigator_status_no_numbers(self):
        """测试没有数值的情况"""
        ai_content = "这是一个普通的描述，没有状态数值"
        
        original_card = self.session.investigator_card.copy()
        self.service._sync_investigator_status(self.session, ai_content)
        
        # 状态不应改变
        assert self.session.investigator_card == original_card
        
    def test_clean_turn_header(self):
        """测试清理轮数标题"""
        content_with_header = "【第1轮 / 第1回合】\n这是内容"
        result = self.service._clean_turn_header(content_with_header)
        
        assert "【" not in result
        assert "】" not in result
        assert result.strip() == "这是内容"
        
    def test_extract_selections_and_format_status(self):
        """测试选项提取和状态格式化"""
        content = "你可以:\n1. 选项一\n2. 选项二\n\n❤ 生命 10"
        
        cleaned_content, selections = self.service._extract_selections_and_format_status(content)
        
        # 验证选项被提取
        assert len(selections) > 0
        assert selections[0]["id"] == "sel_01"
        assert selections[0]["text"] == "选项一"
        assert selections[1]["text"] == "选项二"
        
    @pytest.mark.asyncio
    async def test_llm_call_failure_handling(self):
        """测试LLM调用失败处理"""
        # 模拟LLM调用失败
        self.mock_llm.chat_completion.side_effect = Exception("LLM调用失败")
        
        # 模拟对话历史获取
        with patch.object(self.service, '_get_dialogue_history', return_value=[]):
            with patch.object(self.service, '_build_messages_with_summary', return_value=[
                {"role": "system", "content": "系统提示"},
                {"role": "user", "content": "用户消息"}
            ]):
                
                request = Mock(spec=IWChatRequest)
                request.message = "测试消息"
                
                result = await self.service._step6_playing(self.session, request)
                
                # 应该返回错误消息
                assert "抱歉" in result["content"] or "系统暂时无法响应" in result["content"]
                
    def test_get_rules_content_fallback(self):
        """测试规则内容获取的fallback机制"""
        # 清空缓存以测试fallback
        self.service._COCService__class__rules_cache = {}
        
        with patch.object(self.service, '_load_rules_from_files'):
            self.service._load_rules_files()
            
    def test_increment_methods(self):
        """测试计数方法"""
        # 测试增加轮数
        original_turn = self.session.turn_number
        self.session.increment_turn()
        assert self.session.turn_number == original_turn + 1
        
        # 测试增加回合数
        original_round = self.session.round_number
        self.session.increment_round()
        assert self.session.round_number == original_round + 1
        
    def test_save_count_increment(self):
        """测试存档计数"""
        self.session.save_count = 5
        new_save_id = self.session.increment_save_count()
        assert new_save_id == 6
        assert self.session.save_count == 6
        
    def test_temp_data_operations(self):
        """测试临时数据操作"""
        # 测试设置临时数据
        self.session.set_temp_data({"key": "value"})
        
        # 测试获取临时数据
        data = self.session.get_temp_data()
        assert data["key"] == "value"
        
        # 测试更新临时数据
        self.session.update_temp_data("new_key", "new_value")
        updated_data = self.session.get_temp_data()
        assert updated_data["new_key"] == "new_value"
        assert updated_data["key"] == "value"  # 原有数据应该保留


class TestCOCErrorHandling(IsolatedAsyncioTestCase):
    """COC错误处理测试"""
    
    def test_game_error_creation(self):
        """测试游戏错误创建"""
        error = GameError(
            ErrorCode.COC_LLM_CALL_FAILED,
            "LLM调用失败",
            details={"model": "test_model"},
            original_exception=Exception("原始错误")
        )
        
        assert error.error_code == ErrorCode.COC_LLM_CALL_FAILED
        assert error.message == "LLM调用失败"
        assert error.details["model"] == "test_model"
        
        # 测试转换为字典
        error_dict = error.to_dict()
        assert error_dict["error_code"] == ErrorCode.COC_LLM_CALL_FAILED.value
        assert error_dict["error_type"] == "COC_LLM_CALL_FAILED"
        assert "timestamp" in error_dict
        
    @pytest.mark.asyncio
    async def test_error_handling_decorator(self):
        """测试错误处理装饰器"""
        from src.error_handler import ErrorHandler
        
        @ErrorHandler.handle_coc_error
        async def failing_function():
            raise FileNotFoundError("文件不存在")
            
        with pytest.raises(GameError) as exc_info:
            await failing_function()
            
        error = exc_info.value
        assert error.error_code == ErrorCode.COC_INVALID_GAME_STATE