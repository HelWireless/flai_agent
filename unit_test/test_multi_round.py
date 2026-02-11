"""
通过 API 测试多轮对话，验证总结触发
"""
import requests
import time
import urllib
from sqlalchemy import create_engine, text

# 数据库配置
host = '81.68.235.167'
username = 'pillow'
password = '1234QWERasdf!@#$'
database_name = 'pillow_customer_test'
encoded_password = urllib.parse.quote(password)
DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
engine = create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)


def get_session_status(session_id: str):
    """获取会话状态"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT turn_number, LENGTH(dialogue_summary) as summary_len
            FROM t_coc_game_state WHERE session_id = :sid
        """), {"sid": session_id})
        row = result.fetchone()
        if row:
            return {"turn": row[0], "summary_len": row[1] or 0}
        return None


def send_message(session_id: str, user_id: str, message: str):
    """发送消息（处理 SSE 流式响应）"""
    resp = requests.post(
        "http://localhost:8000/pillow/coc/chat",
        json={
            "userId": user_id,
            "worldId": "trpg_01",
            "sessionId": session_id,
            "message": message,
            "step": "6"
        },
        timeout=90,
        stream=True
    )
    
    # 读取 SSE 流
    content = ""
    for line in resp.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                import json
                try:
                    data = json.loads(line_str[6:])
                    if data.get("type") == "done":
                        break
                except:
                    pass
    
    return "OK"


def main():
    session_id = "RvqqtAKiSVTRejrr"
    user_id = "1000003"
    
    status = get_session_status(session_id)
    print(f"初始状态: turn={status['turn']}, summary_len={status['summary_len']}")
    
    target_turn = ((status['turn'] // 15) + 1) * 15  # 下一个触发点
    rounds_needed = target_turn - status['turn']
    
    print(f"目标轮数: {target_turn}, 需要进行 {rounds_needed} 轮")
    
    messages = [
        "我仔细观察周围", "我检查门是否能打开", "我听一听有什么声音",
        "我往前走几步", "我查看地上的痕迹", "我检查自己的装备",
        "我尝试回忆之前发生了什么", "我大声呼喊看有没有人回应",
        "我检查墙上的符号", "我用听诊器探测声音", "我翻看手札",
        "我准备好武器", "我小心地推开门"
    ]
    
    for i in range(min(rounds_needed + 2, 15)):  # 最多 15 轮
        msg = messages[i % len(messages)]
        print(f"\n--- 发送第 {i+1}/{rounds_needed+2} 条消息 ---")
        print(f"消息: {msg}")
        
        try:
            resp = send_message(session_id, user_id, msg)
            print(f"响应: {resp[:100]}...")
        except Exception as e:
            print(f"错误: {e}")
            continue
        
        # 检查状态
        time.sleep(3)  # 等待异步处理
        status = get_session_status(session_id)
        print(f"当前状态: turn={status['turn']}, summary_len={status['summary_len']}")
        
        if status['summary_len'] > 0:
            print("\n*** 总结已生成! ***")
            break
    
    # 最终状态
    print("\n=== 最终状态 ===")
    status = get_session_status(session_id)
    print(f"turn={status['turn']}, summary_len={status['summary_len']}")


if __name__ == "__main__":
    main()
