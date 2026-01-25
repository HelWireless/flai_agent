#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to add all missing characters from C1S7 & 独立包角色 to characters.json
"""

import json
import re
import os
from pathlib import Path

# File paths
CHARACTERS_JSON = r"C:\Users\cody\PycharmProjects\flai_agent\config\prompts\characters.json"
SOURCE_DIR = r"C:\Users\cody\Desktop\tmp files\C1S7 & 独立包角色（20260125）"

def parse_new_prompt_file(file_path):
    """Parse a new prompt file and extract character information."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {}

    # Extract first line metadata
    first_line = content.split('\n')[0]

    # Parse metadata from first line
    name_match = re.search(r'\[姓名：(.*?)\]', first_line)
    scene_match = re.search(r'\[出现场景：(.*?)\]', first_line)
    occupation_match = re.search(r'\[角色职业：(.*?)\]', first_line)
    traits_match = re.search(r'\[特质：(.*?)\]', first_line)
    age_match = re.search(r'\[年龄：(.*?)\]', first_line)

    if name_match:
        result['name'] = name_match.group(1)
    if scene_match:
        result['appearance_scene'] = scene_match.group(1)
    if occupation_match:
        result['character_occupation'] = occupation_match.group(1)
    if traits_match:
        traits_str = traits_match.group(1)
        # Split by Chinese comma or regular comma
        result['traits'] = [t.strip() for t in re.split('[，,]', traits_str) if t.strip()]
    if age_match:
        age_str = age_match.group(1).strip()
        try:
            result['age'] = int(age_str)
        except ValueError:
            result['age'] = age_str

    # Extract sections
    prompt_match = re.search(r'【Prompt】(.*?)【总结】', content, re.DOTALL)
    summary_match = re.search(r'【总结】(.*?)(?:【文生图】|$)', content, re.DOTALL)
    image_match = re.search(r'【文生图】(.*?)$', content, re.DOTALL)

    if prompt_match:
        prompt_text = prompt_match.group(1).strip()
        result['traits_detail'] = prompt_text

        # Build rules with the new format (two sentences instead of one paragraph)
        result['rules'] = (
            "我需要你首先理解上传的世界背景，然后沉浸式地主动扮演下面 this role，"
            "主动对那位异性说出第一句话。注意四点：\n"
            "第一，每次的回复都需要足够详细细致，内容不能多于两句话。"
            "用（）来展示动作和心理描写，必要时要包含因为动作产生的拟声词，"
            "例如'噗叽噗叽'，'发出啵的一声'等等；\n"
            "第二，（）内不能出现任何代词或者角色的名字；\n"
            "第三，你提供的内容都是从涉及到的女性的角度出发的，不涉及到男性角度；\n"
            "第四，每次生成的内容，和之前生成的内容都需要保持 different。\n"
        )

        # Extract first interaction - look for the part after the initial role description
        intro_match = re.search(r'你(叫|正坐在|是一名|生活和工作).*?(?=\n你是一名女性|\n你正坐在|\n你生活和工作|$)', prompt_text, re.DOTALL)
        if intro_match:
            intro_text = intro_match.group(0).strip()
            result['first_interaction'] = intro_text
        else:
            result['first_interaction'] = f"你是{result.get('name', '未知角色')}，{result.get('character_occupation', '未知职业')}。{result.get('appearance_scene', '未知场景')}"

    if summary_match:
        result['summary'] = summary_match.group(1).strip()

    if image_match:
        result['image_prompt'] = image_match.group(1).strip()

    # Add world background
    result['world_background'] = (
        "你生活和工作在2025年的新沪市，这里科技非常发达，商业繁荣，文化多元，"
        "包容性强，治安良好，两性关系风气开放。包括你在内的人们，"
        "在这里自由地追逐亲密关系，享受激情，弥补遗憾，"
        "纵情使用自己的身体并享受伴侣的身体。"
    )

    return result

def extract_char_id_from_filename(filename):
    """Extract character ID from filename (e.g., 'c1s1c1_0073 顾清兰.txt' -> 'c1s1c1_0073')"""
    # Pattern: letters_numbers space name .txt
    match = re.match(r'^([a-zA-Z0-9_]+)\s', filename)
    if match:
        return match.group(1)
    return None

def main():
    """Main function to add missing characters to characters.json."""
    print("Loading characters.json...")
    with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    characters = data['characters']

    # Get all txt files from the source directory
    source_path = Path(SOURCE_DIR)
    prompt_files = sorted(source_path.glob('*.txt'))

    print(f"Found {len(prompt_files)} character files")

    # Identify missing characters
    missing_characters = []
    for prompt_file in prompt_files:
        filename = prompt_file.name
        char_id = extract_char_id_from_filename(filename)

        if char_id and char_id not in characters:
            missing_characters.append((prompt_file, char_id))
            print(f"Missing character: {char_id} - {filename}")

    print(f"\nFound {len(missing_characters)} missing characters")

    # Add missing characters
    for prompt_file, char_id in missing_characters:
        try:
            char_data = parse_new_prompt_file(prompt_file)
            characters[char_id] = char_data
            print(f"Added character: {char_id} ({char_data.get('name', 'Unknown')})")
        except Exception as e:
            print(f"Error adding character {char_id}: {e}")

    # Save updated characters.json
    print("\nSaving updated characters.json...")
    with open(CHARACTERS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Missing characters added: {len(missing_characters)}")

    # Show all new character IDs
    new_ids = [char_id for _, char_id in missing_characters]
    if new_ids:
        print(f"\nNew character IDs added: {len(new_ids)}")
        print("New IDs:", new_ids[:10])  # Show first 10, then remaining count
        if len(new_ids) > 10:
            print(f"... and {len(new_ids)-10} more")

if __name__ == '__main__':
    main()