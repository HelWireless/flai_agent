
import re
from typing import List, Dict, Any, Tuple

def _clean_turn_header(content: str) -> str:
    turn_pattern = r'\*{0,2}【\s*\d{1,2}\s*轮\s*/\s*\d{1,2}\s*回合\s*】\*{0,2}\s*\n*'
    matches = list(re.finditer(turn_pattern, content))
    if len(matches) > 1:
        first_match = matches[0]
        result = content[:first_match.end()] + re.sub(turn_pattern, '', content[first_match.end():])
    else:
        result = content
    result = result.lstrip('\n\r')
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result

def _extract_selections_and_format_status(content: str) -> Tuple[str, List[Dict[str, Any]]]:
    option_pattern = r'(?m)^([A-E])[\.、:：\s]+(.*?)$'
    options = re.findall(option_pattern, content)
    selections = []
    seen_options = set()
    for opt_id, opt_text in options:
        opt_id_upper = opt_id.upper()
        if opt_id_upper not in seen_options:
            selections.append({
                "id": opt_id_upper.lower(),
                "text": f"{opt_id_upper}. {opt_text.strip()}"
            })
            seen_options.add(opt_id_upper)
    
    cleaned_content = content.strip()
    status_pattern = r'(❤\s*生命.*?💎\s*魔法.*?🧠\s*理智.*)'
    status_match = re.search(status_pattern, cleaned_content)
    if status_match:
        status_line = status_match.group(1)
        cleaned_content = re.sub(r'\n*' + status_pattern + r'\n*', '\n\n', cleaned_content).strip()
        cleaned_content = f"{cleaned_content}\n\n{status_line}"
    cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
    return cleaned_content.strip(), selections

def test_final_verification():
    # 模拟 LLM 输出
    llm_output = """**【01轮 / 01回合】**

剧情：你进入了房间。
A. 搜索床底
B. 检查窗户
C. 尝试开门
**【01轮 / 01回合】**
❤ 生命 10   💎 魔法 10   🧠 理智 50"""

    print("--- Original ---")
    print(repr(llm_output))

    # 1. 清理标题 (应该只保留第一个)
    content = _clean_turn_header(llm_output)
    print("\n--- After Clean Header ---")
    print(repr(content))
    
    # 验证只保留一个标题
    matches = re.findall(r'【\s*\d{1,2}\s*轮\s*/\s*\d{1,2}\s*回合\s*】', content)
    assert len(matches) == 1, f"Expected 1 header, found {len(matches)}"

    # 2. 提取选项和格式化 (状态行应该在选项之后)
    content, selections = _extract_selections_and_format_status(content)
    print("\n--- After Extraction & Formatting ---")
    print(repr(content))
    
    # 验证选项还在文本中
    assert "A. 搜索床底" in content, "Options should remain in text"
    # 验证状态行在最后
    lines = content.split('\n')
    assert "❤ 生命" in lines[-1], "Status line should be the last line"
    assert "A. 搜索床底" in content and content.find("A. 搜索床底") < content.find("❤ 生命"), "Status line should be after options"

    print("\nVerification successful!")

if __name__ == "__main__":
    test_final_verification()
