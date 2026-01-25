#!/usr/bin/env python3
"""
测试角色查找功能
"""

from src.api.prompts.generate_prompts import get_prompt_by_character_id

def test_character_lookup():
    print("Testing existing character 'c1s1c1_0074'...")
    try:
        prompt, model = get_prompt_by_character_id('c1s1c1_0074')
        print(f"✓ Found character, system prompt type: {type(prompt['system_prompt'])}")
        print(f"  System prompt preview: {prompt['system_prompt'][:100]}...")
        print(f"  Model: {model}")
    except Exception as e:
        print(f"✗ Error with existing character: {e}")
    
    print("\nTesting non-existing character 'non_existing_id'...")
    try:
        prompt, model = get_prompt_by_character_id('non_existing_id')
        print(f"System prompt: {prompt['system_prompt']}")
        print(f"Model: {model}")
        if "error" in prompt["system_prompt"]:
            print("✓ Correctly returned error message for non-existing character")
        else:
            print("? Unexpected result for non-existing character")
    except Exception as e:
        print(f"Error with non-existing character: {e}")

if __name__ == "__main__":
    test_character_lookup()