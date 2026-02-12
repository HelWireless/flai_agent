#!/usr/bin/env python3
"""
清理数据库中历史对话的重复轮数标题

对 t_freak_world_dialogue 表中的 assistant_message 字段进行清理：
- 移除所有重复的【XX轮 / YY回合】标注
- 只保留最后一个（如果有的话）
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.models.instance_world import FreakWorldDialogue


def clean_turn_header(content: str, keep_last: bool = True) -> str:
    """清理轮数标题，保留最后一个或全部移除"""
    if not content:
        return content
    
    # 匹配轮数标题模式：【XX轮 / YY回合】（支持加粗格式）
    turn_pattern = r'\*{0,2}【\d{1,2}轮\s*/\s*\d{1,2}回合】\*{0,2}\s*\n*'
    
    matches = list(re.finditer(turn_pattern, content))
    
    if len(matches) <= 1:
        return content  # 0或1个，不需要清理
    
    if keep_last:
        # 保留最后一个，移除其他
        result = content
        for match in reversed(matches[:-1]):
            start = match.start()
            end = match.end()
            result = result[:start] + result[end:]
    else:
        # 移除所有
        result = re.sub(turn_pattern, '', content)
    
    # 清理开头的空行
    result = result.lstrip('\n\r')
    
    # 清理多余的空行
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result


def main():
    db = SessionLocal()
    
    try:
        # 查询所有对话记录
        dialogues = db.query(FreakWorldDialogue).filter(
            FreakWorldDialogue.del_ == 0
        ).all()
        
        print(f"找到 {len(dialogues)} 条对话记录")
        
        updated_count = 0
        
        for dialogue in dialogues:
            original = dialogue.text  # 返回内容字段是 text
            if not original:
                continue
            
            # 清理轮数标题（保留最后一个）
            cleaned = clean_turn_header(original, keep_last=True)
            
            if cleaned != original:
                dialogue.text = cleaned
                updated_count += 1
                print(f"  清理对话 ID={dialogue.id}, session={dialogue.session_id}")
        
        if updated_count > 0:
            db.commit()
            print(f"\n已更新 {updated_count} 条记录")
        else:
            print("\n没有需要清理的记录")
        
    except Exception as e:
        print(f"错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
