
import re
from typing import List, Dict, Any, Tuple

def _clean_turn_header(content: str, keep_last: bool = False) -> str:
    turn_pattern = r'\*{0,2}【\s*\d{1,2}\s*轮\s*/\s*\d{1,2}\s*回合\s*】\*{0,2}\s*\n*'
    if keep_last:
        matches = list(re.finditer(turn_pattern, content))
        if len(matches) > 1:
            result = content
            for match in reversed(matches[:-1]):
                start = match.start()
                end = match.end()
                result = result[:start] + result[end:]
            content = result
        result = content
    else:
        result = re.sub(turn_pattern, '', content)
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
    cleaned_content = re.sub(option_pattern, '', content).strip()
    status_pattern = r'(❤\s*生命.*?💎\s*魔法.*?🧠\s*理智.*)'
    if re.search(status_pattern, cleaned_content):
        cleaned_content = re.sub(r'\n*' + status_pattern + r'\n*', r'\n\n\1', cleaned_content)
    cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
    return cleaned_content.strip(), selections

def test_final_verification():
    # 模拟 LLM 输出，包含重复标题、重复选项和状态行
    llm_output = """**【01轮 / 01回合】**

剧情：你进入了房间。
A. 搜索床底
B. 检查窗户
C. 尝试开门

C. 尝试开门

❤ 生命 10   💎 魔法 10   🧠 理智 50"""

    print("--- Original ---")
    print(repr(llm_output))

    # 1. 清理标题
    content = _clean_turn_header(llm_output)
    print("\n--- After Clean Header ---")
    print(repr(content))

    # 2. 提取选项和格式化
    content, selections = _extract_selections_and_format_status(content)
    print("\n--- After Extraction & Formatting ---")
    print(repr(content))
    print("\nSelections:")
    for s in selections:
        print(f"  {s['id']}: {s['text']}")

    # 验证点
    assert "**【01轮 / 01回合】**" not in content, "Should remove header"
    assert "C. 尝试开门" not in content, "Should remove options from content"
    assert len(selections) == 3, "Should extract exactly 3 unique options"
    assert selections[2]['id'] == 'c', "Third option should be 'c'"
    assert "\n\n❤ 生命" in content or content.startswith("❤ 生命"), "Status line should have leading newline"

    print("\nVerification successful!")

if __name__ == "__main__":
    test_final_verification()
