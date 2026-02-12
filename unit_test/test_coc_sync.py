import re
from unittest.mock import MagicMock

class GameStatus:
    PLAYING = "playing"
    ENDED = "ended"

def _sync_investigator_status(session, content):
    """从 coc_service.py 复制的逻辑用于测试"""
    if not content or not session.investigator_card:
        return

    # 正则匹配状态行
    pattern = r'❤\s*生命\s*(\d+)\s*💎\s*魔法\s*(\d+)\s*🧠\s*理智\s*(\d+)'
    match = re.search(pattern, content)
    
    if match:
        try:
            hp = int(match.group(1))
            mp = int(match.group(2))
            san = int(match.group(3))
            
            card = session.investigator_card
            card['currentHP'] = hp
            card['currentMP'] = mp
            card['currentSAN'] = san
            
            if hp <= 0 or san <= 0:
                session.game_status = GameStatus.ENDED
            else:
                session.game_status = GameStatus.PLAYING
                
        except (ValueError, IndexError):
            pass

def test_status_sync():
    # 模拟 session 对象
    class Session:
        def __init__(self):
            self.investigator_card = {'currentHP': 10, 'currentMP': 10, 'currentSAN': 50}
            self.game_status = GameStatus.PLAYING

    # 测试用例 1: 正常数值更新
    s1 = Session()
    content1 = "故事内容...\n\n❤ 生命 8   💎 魔法 7   🧠 理智 45"
    _sync_investigator_status(s1, content1)
    assert s1.investigator_card['currentHP'] == 8
    assert s1.investigator_card['currentSAN'] == 45
    assert s1.game_status == GameStatus.PLAYING
    print("Test 1 passed: Normal sync")

    # 测试用例 2: 生命值为 0 触发结束
    s2 = Session()
    content2 = "你倒在了血泊中。\n\n❤ 生命 0   💎 魔法 5   🧠 理智 30"
    _sync_investigator_status(s2, content2)
    assert s2.investigator_card['currentHP'] == 0
    assert s2.game_status == GameStatus.ENDED
    print("Test 2 passed: HP 0 ends game")

    # 测试用例 3: 理智值为 0 触发结束
    s3 = Session()
    content3 = "你彻底疯了。\n\n❤ 生命 10   💎 魔法 5   🧠 理智 0"
    _sync_investigator_status(s3, content3)
    assert s3.investigator_card['currentSAN'] == 0
    assert s3.game_status == GameStatus.ENDED
    print("Test 3 passed: SAN 0 ends game")

    # 测试用例 4: 格式略有差异（空格/换行）
    s4 = Session()
    content4 = "❤生命12💎魔法9🧠理智38"
    _sync_investigator_status(s4, content4)
    assert s4.investigator_card['currentHP'] == 12
    assert s4.investigator_card['currentSAN'] == 38
    print("Test 4 passed: Compact format sync")

if __name__ == "__main__":
    test_status_sync()
