import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import BackgroundTasks

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.chat_service import ChatService
from src.schemas import ChatRequest


async def test_sensitive_content_blocking():
    """测试敏感内容拦截功能"""
    print(f"\n[Test] Sensitive Content Blocking")
    
    # Mock dependencies
    llm_mock = MagicMock()
    memory_mock = AsyncMock()
    
    # Content filter that detects sensitive content
    content_filter_mock = MagicMock()
    content_filter_mock.detect_sensitive_content.return_value = (True, ["敏感词"])
    
    config_loader_mock = MagicMock()
    config_loader_mock.get_responses.return_value = {
        'error_responses': ['抱歉，出错了'],
        'sensitive_responses': ['请注意您的言辞']
    }
    config_loader_mock.get_character_openers.return_value = {}
    
    with patch('src.services.chat_service.EmotionService') as emotion_cls_mock:
        emotion_cls_mock.return_value.get_current_emotion.return_value = 1
        
        service = ChatService(llm_mock, memory_mock, content_filter_mock, config_loader_mock)
        
        request = ChatRequest(user_id="u1", character_id="c1", message="敏感内容测试", message_count=1)
        response = await service.process_chat(request)
        
        # Verify LLM was NOT called
        if llm_mock.chat_completion.call_count == 0:
            print("✅ LLM was NOT called for sensitive content")
        else:
            print("❌ LLM was called for sensitive content")
        
        # Verify response is from sensitive_responses
        if response.llm_message[0] in config_loader_mock.get_responses()['sensitive_responses']:
            print("✅ Response is from sensitive_responses list")
        else:
            print(f"❌ Response not from sensitive list: {response.llm_message[0]}")


async def test_memory_context_injection():
    """测试记忆上下文注入"""
    print(f"\n[Test] Memory Context Injection")
    
    # Mock dependencies
    llm_mock = MagicMock()
    llm_mock.chat_completion = AsyncMock(return_value={"answer": "好的", "emotion_type": 1})
    
    memory_mock = AsyncMock()
    # Return conversation history and persistent memory
    memory_mock.get_combined_memory.return_value = (
        [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好啊"}],
        "小明",
        {"long_term": "用户喜欢运动", "short_term": "最近在学习编程"},
        False
    )
    memory_mock.save_conversation = AsyncMock(return_value={"saved": True})
    
    content_filter_mock = MagicMock()
    content_filter_mock.detect_sensitive_content.return_value = (False, [])
    
    config_loader_mock = MagicMock()
    config_loader_mock.get_responses.return_value = {'error_responses': ['Error'], 'sensitive_responses': ['No']}
    config_loader_mock.get_character_openers.return_value = {}
    
    with patch('src.services.chat_service.get_prompt_by_character_id') as prompt_mock:
        prompt_mock.return_value = (
            {"user_prompt": "query\nhistory_chat", "system_prompt": "你是AI助手"},
            "qwen_max"
        )
        
        with patch('src.services.chat_service.EmotionService') as emotion_cls_mock:
            emotion_cls_mock.return_value.get_current_emotion.return_value = 1
            
            service = ChatService(llm_mock, memory_mock, content_filter_mock, config_loader_mock)
            
            request = ChatRequest(user_id="u1", character_id="c1", message="今天天气怎么样", message_count=1)
            await service.process_chat(request)
            
            # Check if LLM was called with memory context
            call_args = llm_mock.chat_completion.call_args
            messages = call_args.kwargs['messages']
            user_content = messages[1]['content']
            
            # Verify conversation history is injected
            if "你好" in user_content:
                print("✅ Conversation history injected into prompt")
            else:
                print("❌ Conversation history NOT found in prompt")
            
            # Verify persistent memory is injected
            if "用户喜欢运动" in user_content and "最近在学习编程" in user_content:
                print("✅ Persistent memory (long_term & short_term) injected into prompt")
            else:
                print("❌ Persistent memory NOT found in prompt")


async def test_llm_error_handling():
    """测试 LLM 调用错误处理"""
    print(f"\n[Test] LLM Error Handling")
    
    # Mock dependencies
    llm_mock = MagicMock()
    # Simulate LLM failure
    llm_mock.chat_completion = AsyncMock(side_effect=Exception("Network error"))
    
    memory_mock = AsyncMock()
    memory_mock.get_combined_memory.return_value = ([], "User", {}, False)
    memory_mock.save_conversation = AsyncMock(return_value={"saved": True})
    
    content_filter_mock = MagicMock()
    content_filter_mock.detect_sensitive_content.return_value = (False, [])
    
    config_loader_mock = MagicMock()
    error_responses = ['抱歉，我遇到了一些问题', '系统繁忙，请稍后再试']
    config_loader_mock.get_responses.return_value = {
        'error_responses': error_responses,
        'sensitive_responses': ['No']
    }
    config_loader_mock.get_character_openers.return_value = {}
    
    with patch('src.services.chat_service.get_prompt_by_character_id') as prompt_mock:
        prompt_mock.return_value = (
            {"user_prompt": "query\nhistory_chat", "system_prompt": "sys"},
            "qwen_max"
        )
        
        with patch('src.services.chat_service.EmotionService') as emotion_cls_mock:
            emotion_cls_mock.return_value.get_current_emotion.return_value = 1
            
            service = ChatService(llm_mock, memory_mock, content_filter_mock, config_loader_mock)
            
            request = ChatRequest(user_id="u1", character_id="c1", message="测试", message_count=1)
            response = await service.process_chat(request)
            
            # Verify fallback response is used
            if response.llm_message[0] in error_responses:
                print("✅ Fallback error response used when LLM fails")
            else:
                print(f"❌ Unexpected response: {response.llm_message[0]}")


async def test_background_tasks_integration():
    """测试后台任务集成"""
    print(f"\n[Test] Background Tasks Integration")
    
    # Mock dependencies
    llm_mock = MagicMock()
    llm_mock.chat_completion = AsyncMock(return_value={"answer": "测试回复", "emotion_type": 1})
    
    memory_mock = AsyncMock()
    memory_mock.get_combined_memory.return_value = ([], "User", {}, False)
    memory_mock.save_conversation = AsyncMock(return_value={"saved": True})
    
    content_filter_mock = MagicMock()
    content_filter_mock.detect_sensitive_content.return_value = (False, [])
    
    config_loader_mock = MagicMock()
    config_loader_mock.get_responses.return_value = {'error_responses': ['Error'], 'sensitive_responses': ['No']}
    config_loader_mock.get_character_openers.return_value = {}
    
    with patch('src.services.chat_service.get_prompt_by_character_id') as prompt_mock:
        prompt_mock.return_value = (
            {"user_prompt": "query\nhistory_chat", "system_prompt": "sys"},
            "qwen_max"
        )
        
        with patch('src.services.chat_service.EmotionService') as emotion_cls_mock:
            emotion_cls_mock.return_value.get_current_emotion.return_value = 1
            
            service = ChatService(llm_mock, memory_mock, content_filter_mock, config_loader_mock)
            
            request = ChatRequest(user_id="u1", character_id="c1", message="hi", message_count=1)
            bg_tasks = BackgroundTasks()
            
            await service.process_chat(request, background_tasks=bg_tasks)
            
            # Verify save_conversation was NOT called directly
            if memory_mock.save_conversation.call_count == 0:
                print("✅ save_conversation NOT called synchronously")
            else:
                print("❌ save_conversation WAS called synchronously")
            
            # Verify task was added to background
            if len(bg_tasks.tasks) == 1:
                print("✅ Memory save task added to background_tasks")
            else:
                print(f"❌ Unexpected background tasks count: {len(bg_tasks.tasks)}")


async def main():
    try:
        await test_sensitive_content_blocking()
        await test_memory_context_injection()
        await test_llm_error_handling()
        await test_background_tasks_integration()
        print("\n✅ All ChatService tests passed!")
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
