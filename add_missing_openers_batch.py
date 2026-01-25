#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to add all missing character openers to character_openers.json
"""

import json
import re
import os
from pathlib import Path

# File paths
OPENERS_JSON = r"C:\Users\cody\PycharmProjects\flai_agent\config\prompts\character_openers.json"
OPENER_SOURCE_DIR = r"C:\Users\cody\Desktop\tmp files\C1S7&独立包 开场白"

def parse_opener_file(file_path):
    """Parse an opener file and extract the opener lines."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    lines = content.split('\n')
    openers = []

    for line in lines:
        # Remove numbering (e.g., "1.", "2.") at the beginning of lines
        cleaned_line = re.sub(r'^\d+\.\s*', '', line.strip())
        if cleaned_line:  # Only add non-empty lines
            openers.append(cleaned_line)

    return openers

def extract_char_id_from_filename(filename):
    """Extract character ID from filename (e.g., 'c1s1c1_0073 顾清兰.txt' -> 'c1s1c1_0073')"""
    # Pattern: letters_numbers space name .txt
    match = re.match(r'^([a-zA-Z0-9_]+)\s', filename)
    if match:
        return match.group(1)
    return None

def main():
    """Main function to add missing character openers to character_openers.json."""
    print("Loading character_openers.json...")
    with open(OPENERS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Get all txt files from the opener source directory
    source_path = Path(OPENER_SOURCE_DIR)
    opener_files = sorted(source_path.glob('*.txt'))

    print(f"Found {len(opener_files)} opener files")

    # Identify missing openers
    missing_openers = []
    for opener_file in opener_files:
        filename = opener_file.name
        char_id = extract_char_id_from_filename(filename)

        if char_id and char_id not in data:
            missing_openers.append((opener_file, char_id))
            print(f"Missing opener: {char_id} - {filename}")

    print(f"\nFound {len(missing_openers)} missing openers")

    # Add missing openers
    for opener_file, char_id in missing_openers:
        try:
            openers = parse_opener_file(opener_file)
            if openers:
                data[char_id] = openers
                print(f"Added opener: {char_id} ({len(openers)} lines)")
            else:
                print(f"No openers found for: {char_id}")
        except Exception as e:
            print(f"Error adding opener {char_id}: {e}")

    # Save updated character_openers.json
    print("\nSaving updated character_openers.json...")
    with open(OPENERS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Missing openers added: {len(missing_openers)}")

    # Show all new opener IDs
    new_ids = [char_id for _, char_id in missing_openers]
    if new_ids:
        print(f"\nNew opener IDs added: {len(new_ids)}")
        print("New IDs:", new_ids[:10])  # Show first 10, then remaining count
        if len(new_ids) > 10:
            print(f"... and {len(new_ids)-10} more")

if __name__ == '__main__':
    main()