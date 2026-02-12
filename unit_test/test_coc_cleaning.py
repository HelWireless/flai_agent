#!/usr/bin/env python3
"""
测试 COC 轮数标题清理逻辑
"""
import os
import sys
import re

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def _clean_turn_header(content: str, keep_last: bool = False) -> str:
    """复制自 src/services/coc_service.py 的清理逻辑"""
    # 匹配轮数标题模式：【XX轮 / YY回合】（支持加粗格式，支持各种换行和空格）
    # 优化正则：匹配可能存在的重复、嵌套或连续的轮次标注
    turn_pattern = r'(\*{0,2}【\d{1,2}轮\s*/\s*\d{1,2}回合】\*{0,2}\s*\n*)+'
    
    if keep_last:
        # 找到所有匹配
        matches = list(re.finditer(turn_pattern, content))
        if len(matches) > 1:
            # 保留最后一个，移除其他
            result = content
            # 从后往前删除，避免索引变化
            for match in reversed(matches[:-1]):
                start = match.start()
                end = match.end()
                result = result[:start] + result[end:]
            content = result
        
        # 针对单个匹配中可能包含的重复（由正则表达式中的 + 捕获）
        # 再次确保只有一个标注
        match = re.search(turn_pattern, content)
        if match:
            # 提取最后一个具体的标注
            single_pattern = r'\*{0,2}【\d{1,2}轮\s*/\s*\d{1,2}回合】\*{0,2}'
            sub_matches = re.findall(single_pattern, match.group())
            if len(sub_matches) > 1:
                last_one = sub_matches[-1]
                content = content[:match.start()] + last_one + "\n\n" + content[match.end():]
        
        result = content
    else:
        # 移除所有轮数标题
        result = re.sub(turn_pattern, '', content)
    
    # 清理开头的空行
    result = result.lstrip('\n\r')
    # 清理多余的空行
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result

def test_cleaning():
    test_cases = [
        # 1. 正常的重复输出
        {
            "name": "正常重复输出",
            "input": "**【06轮 / 01回合】**\n\n【09轮 / 01回合】\n\n故事内容...",
            "keep_last": False,
            "expected": "故事内容..."
        },
        # 2. 带有 keep_last=True (用于历史对话清理)
        {
            "name": "历史对话保留最后一个",
            "input": "**【06轮 / 01回合】**\n\n【09轮 / 01回合】\n\n故事内容...",
            "keep_last": True,
            "expected": "【09轮 / 01回合】\n\n故事内容..."
        },
        # 3. 极端的嵌套重复
        {
            "name": "极端嵌套重复",
            "input": "**【01轮 / 01回合】****【01轮 / 01回合】**\n【01轮 / 01回合】\n\n内容",
            "keep_last": True,
            "expected": "【01轮 / 01回合】\n\n内容"
        },
        # 4. 正常不重复
        {
            "name": "正常不重复",
            "input": "**【01轮 / 01回合】**\n\n正常内容",
            "keep_last": True,
            "expected": "**【01轮 / 01回合】**\n\n正常内容"
        }
    ]

    print("=== 开始测试 COC 标题清理逻辑 ===")
    for case in test_cases:
        actual = _clean_turn_header(case["input"], case["keep_last"])
        # 简单处理下空白符对比
        actual_stripped = actual.strip()
        expected_stripped = case["expected"].strip()
        
        if actual_stripped == expected_stripped:
            print(f"✓ {case['name']} 通过")
        else:
            print(f"✗ {case['name']} 失败")
            print(f"  输入: {repr(case['input'])}")
            print(f"  期望: {repr(case['expected'])}")
            print(f"  实际: {repr(actual)}")
    print("=== 测试结束 ===")

if __name__ == "__main__":
    test_cleaning()
