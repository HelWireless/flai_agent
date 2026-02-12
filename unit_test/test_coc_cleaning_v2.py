
import re

def clean_turn_header(content: str) -> str:
    # 更加鲁棒的正则，匹配各种可能的轮数/回合标记
    # 匹配: **【01轮 / 01回合】**, 【1轮/1回合】, **【1 轮 / 1 回合】** 等
    turn_pattern = r'\*{0,2}【\s*\d{1,2}\s*轮\s*/\s*\d{1,2}\s*回合\s*】\*{0,2}\s*\n*'
    
    # 直接删除所有匹配到的标题，因为后端会统一添加
    cleaned_content = re.sub(turn_pattern, '', content)
    return cleaned_content.strip()

def test_cleaning():
    test_cases = [
        "**【01轮 / 01回合】**\n\n你好",
        "【1轮/1回合】你好",
        "**【01轮 / 01回合】**\n文本\n**【02轮 / 01回合】**\n更多文本",
        "你好\n**【01轮 / 01回合】**",
    ]
    
    for i, case in enumerate(test_cases):
        cleaned = clean_turn_header(case)
        print(f"Case {i+1}:")
        print(f"Original: {repr(case)}")
        print(f"Cleaned:  {repr(cleaned)}")
        print("-" * 20)

if __name__ == "__main__":
    test_cleaning()
