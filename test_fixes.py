#!/usr/bin/env python3
"""
Test script to verify the fixes for character lookup and error handling
"""
import sys
import os

# Add the project root to Python path
project_root = r"C:\Users\cody\PycharmProjects\flai_agent"
sys.path.insert(0, project_root)

def test_smart_reload_and_error_handling():
    """Test the smart reload and error handling mechanisms"""
    print("Testing smart reload and error handling mechanisms...")

    # Import required modules
    from src.api.prompts.generate_prompts import get_prompt_by_character_id
    from src.core.config_loader import get_config_loader

    print("\n1. Testing existing character retrieval...")
    try:
        # Test with a known existing character
        prompt, model_id = get_prompt_by_character_id("c1s1c1_0001")
        if prompt and "system_prompt" in prompt:
            print("   ✅ Existing character retrieved successfully")
        else:
            print("   ❌ Failed to retrieve existing character")
    except Exception as e:
        print(f"   ❌ Error retrieving existing character: {e}")

    print("\n2. Testing non-existent character handling...")
    try:
        # Test with a non-existent character
        prompt, model_id = get_prompt_by_character_id("non_existent_character_9999")
        system_content = prompt.get("system_prompt", "") if isinstance(prompt, dict) else str(prompt)

        if "\"error\":\"角色ID non_existent_character_9999 不存在，请检查ID是否正确\"" in system_content:
            print("   ✅ Non-existent character properly handled with error message")
        else:
            print("   ❌ Non-existent character not handled correctly")
            print(f"   System content: {system_content}")
    except Exception as e:
        print(f"   ❌ Error handling non-existent character: {e}")

    print("\n3. Testing config loader reload capability...")
    try:
        loader = get_config_loader()
        # Test that we can reload configs
        chars_normal = loader.get_characters()
        chars_reloaded = loader.get_characters(reload=True)

        if chars_normal is not None and chars_reloaded is not None:
            print("   ✅ Config loader supports both normal and reload operations")
        else:
            print("   ❌ Config loader test failed")
    except Exception as e:
        print(f"   ❌ Error testing config loader: {e}")

    print("\n4. Testing new character availability...")
    try:
        # Test with one of our newly added characters
        prompt, model_id = get_prompt_by_character_id("c1s1c1_0073")  # 顾清兰
        if prompt and "system_prompt" in prompt and "error" not in prompt.get("system_prompt", "").lower():
            print("   ✅ New character (c1s1c1_0073) retrieved successfully")
        else:
            print("   ❌ New character (c1s1c1_0073) not found or has error")
            if isinstance(prompt, dict):
                print(f"   System content: {prompt.get('system_prompt', '')[:200]}...")
    except Exception as e:
        print(f"   ❌ Error retrieving new character: {e}")

    print("\nAll tests completed!")

if __name__ == "__main__":
    test_smart_reload_and_error_handling()