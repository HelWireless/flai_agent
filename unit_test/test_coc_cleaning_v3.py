
import re
import json

def clean_turn_header(content: str) -> str:
    turn_pattern = r'\*{0,2}【\s*\d{1,2}\s*轮\s*/\s*\d{1,2}\s*回合\s*】\*{0,2}\s*\n*'
    return re.sub(turn_pattern, '', content).strip()

def extract_selections_and_format_status(content: str):
    # 1. 提取选项 (A. B. C. D. E.)
    # 匹配 A. xxx 或 A、xxx 或 A: xxx
    option_pattern = r'(?m)^([A-E])[\.、:：\s]+(.*?)$'
    options = re.findall(option_pattern, content)
    
    selections = []
    for opt_id, opt_text in options:
        selections.append({
            "id": opt_id.lower(),
            "text": f"{opt_id}. {opt_text.strip()}"
        })
    
    # 从正文中删除选项行
    cleaned_content = re.sub(option_pattern, '', content).strip()
    
    # 2. 格式化状态行 (生命/魔法/理智)
    # 确保状态行前有换行
    status_pattern = r'(❤\s*生命.*?💎\s*魔法.*?🧠\s*理智.*)'
    if re.search(status_pattern, cleaned_content):
        # 如果找到了状态行，确保它前面有两个换行符（或者至少一个）
        # 我们先去掉它周围的多余换行，然后统一添加
        cleaned_content = re.sub(r'\n*' + status_pattern + r'\n*', r'\n\n\1', cleaned_content)
    
    return cleaned_content.strip(), selections

def test_full_cleaning():
    test_content = """**【01轮 / 01回合】**

这是一个测试剧情。
A. 选项A的内容
B. 选项B的内容
C. 选项C的内容【补充】

选项C的内容【补充】

❤ 生命 10   💎 魔法 10   🧠 理智 50"""

    print("Original Content:")
    print(repr(test_content))
    print("\n" + "="*30 + "\n")
    
    # 1. 清理标题
    content = clean_turn_header(test_content)
    
    # 2. 提取选项和处理状态行
    content, selections = extract_selections_and_format_status(content)
    
    print("Cleaned Content:")
    print(repr(content))
    print("\nSelections:")
    print(json.dumps(selections, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    test_full_cleaning()
