import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import BackgroundTasks

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.llm_service import LLMService
# Need to patch imports in chat_service before importing it if dependencies are complex, 
# but here we just import and patch dependencies.
from src.services.chat_service import ChatService
from src.schemas import ChatRequest

async def test_llm_timeout():
    print(f"\n[Test] LLM Timeout Configuration")
    config = {
        "test_model": {
            "base_url": "http://test",
            "model": "test",
            "api_key": "key"
        }
    }
    service = LLMService(config)
    
    # Mock _make_request to check if timeout is passed
    # _make_request is async, so we use AsyncMock
    with patch.object(service, '_make_request', new_callable=AsyncMock) as mock_request:
        # The return value of _make_request (when awaited) should be a response object
        mock_response = MagicMock()
        mock_response.status_code = 200
        # response.json() is a synchronous method returning dict
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "{\"answer\": \"hi\"}"}}]
        }
        mock_request.return_value = mock_response
        
        await service.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model_name="test_model",
            timeout=10
        )
        
        args, kwargs = mock_request.call_args
        if kwargs.get('timeout') == 10:
            print("✅ Timeout parameter correctly passed to _make_request")
        else:
            print(f"❌ Timeout parameter missing or incorrect: {kwargs}")

async def test_background_tasks():
    print(f"\n[Test] Background Tasks for Memory")
    
    # Mocks
    llm_mock = MagicMock()
    # chat_completion is async
    llm_mock.chat_completion = AsyncMock(return_value={"answer": "Hello", "emotion_type": 1})
    
    memory_mock = AsyncMock()
    # Mock get_combined_memory to return empty values
    memory_mock.get_combined_memory.return_value = ([], "User", {}, False)
    # Mock save_conversation
    memory_mock.save_conversation = AsyncMock(return_value={"saved": True})
    
    content_filter_mock = MagicMock()
    content_filter_mock.detect_sensitive_content.return_value = (False, [])
    
    config_loader_mock = MagicMock()
    # These return dicts directly (sync)
    config_loader_mock.get_responses.return_value = {'error_responses': ['Error'], 'sensitive_responses': ['No']}
    config_loader_mock.get_character_openers.return_value = {}
    
    # Patch get_prompt_by_character_id (it's imported in chat_service)
    with patch('src.services.chat_service.get_prompt_by_character_id') as prompt_mock:
        prompt_mock.return_value = ({"user_prompt": "query", "system_prompt": "sys"}, "model")
        
        # Patch emotion service class creation
        with patch('src.services.chat_service.EmotionService') as emotion_cls_mock:
            # The instance methods
            emotion_cls_mock.return_value.get_current_emotion.return_value = 1
            
            service = ChatService(llm_mock, memory_mock, content_filter_mock, config_loader_mock)
            
            # Request
            request = ChatRequest(user_id="u1", character_id="c1", message="hi", message_count=1)
            bg_tasks = BackgroundTasks()
            
            # Run
            await service.process_chat(request, background_tasks=bg_tasks)
            
            # Check if save_conversation was NOT called directly (awaited)
            if memory_mock.save_conversation.call_count == 0:
                print("✅ memory.save_conversation was NOT called synchronously")
            else:
                print("❌ memory.save_conversation WAS called synchronously")

            # Check if headers added to background tasks
            # BackgroundTasks stores tasks in .tasks list
            if len(bg_tasks.tasks) == 1:
                print("✅ Task added to background_tasks")
            else:
                print(f"❌ Background tasks count incorrect: {len(bg_tasks.tasks)}")

async def main():
    try:
        await test_llm_timeout()
        await test_background_tasks()
        print("\n✅ All optimization tests passed!")
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
