"""
测试对话总结触发机制

模拟 16 轮和 31 轮对话，验证总结是否在第 15/30 轮后生成
"""
import asyncio
import urllib
import sys
import os
import time
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.llm_service import LLMService
from src.services.coc_service import COCService
from src.schemas import IWChatRequest

# 加载配置
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.yaml")
with open(config_path, "r", encoding="utf-8") as f:
    app_config = yaml.safe_load(f)

# 数据库配置
host = '81.68.235.167'
username = 'pillow'
password = '1234QWERasdf!@#$'
database_name = 'pillow_customer_test'

encoded_password = urllib.parse.quote(password)
DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
engine = create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_session_info(session_id: str):
    """获取会话信息"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT turn_number, LENGTH(dialogue_summary) as summary_len, dialogue_summary
            FROM t_coc_game_state
            WHERE session_id = :sid
        """), {"sid": session_id})
        row = result.fetchone()
        if row:
            return {
                "turn_number": row[0],
                "summary_len": row[1] or 0,
                "has_summary": row[2] is not None and len(row[2] or "") > 0,
                "summary_preview": (row[2] or "")[:200] if row[2] else None
            }
        return None


async def test_summary_trigger():
    """测试总结触发"""
    db = SessionLocal()
    llm = LLMService(app_config)
    config = app_config
    
    try:
        service = COCService(llm, db, config)
        
        # 找一个已经在 playing 状态且轮数接近 15 或 30 的会话
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT session_id, user_id, turn_number
                FROM t_coc_game_state
                WHERE game_status = 'playing' AND del = 0
                ORDER BY turn_number DESC
                LIMIT 5
            """))
            sessions = result.fetchall()
        
        if not sessions:
            print("没有找到活跃的 COC 会话")
            return
        
        print("\n=== 可用的测试会话 ===")
        for s in sessions:
            print(f"  session_id: {s[0]}, user_id: {s[1]}, turn: {s[2]}")
        
        # 选择一个会话进行测试
        test_session = sessions[0]
        session_id = test_session[0]
        user_id = test_session[1]
        current_turn = test_session[2]
        
        print(f"\n=== 选择测试会话: {session_id} ===")
        print(f"当前轮数: {current_turn}")
        
        # 检查当前是否已有总结
        info = get_session_info(session_id)
        print(f"当前总结状态: {'有' if info['has_summary'] else '无'} (长度: {info['summary_len']})")
        
        # 计算需要进行多少轮才能触发总结
        next_trigger = ((current_turn // 15) + 1) * 15
        rounds_needed = next_trigger - current_turn
        
        print(f"下一个总结触发点: 第 {next_trigger} 轮")
        print(f"需要进行 {rounds_needed} 轮对话才能触发")
        
        if rounds_needed > 5:
            print(f"\n距离下次触发还需要 {rounds_needed} 轮，测试将进行 3 轮演示...")
            rounds_to_test = 3
        else:
            print(f"\n将进行 {rounds_needed + 1} 轮对话以触发总结...")
            rounds_to_test = rounds_needed + 1
        
        # 测试对话
        test_messages = [
            "我环顾四周，观察周围的环境",
            "我检查一下自己身上有什么物品",
            "我尝试回忆一下来到这里之前发生了什么",
            "我小心翼翼地向前走几步",
            "我仔细听一听周围有没有什么声音",
            "我检查一下门是否能打开",
        ]
        
        for i in range(rounds_to_test):
            msg = test_messages[i % len(test_messages)]
            print(f"\n--- 第 {current_turn + i + 1} 轮 ---")
            print(f"玩家: {msg[:30]}...")
            
            request = IWChatRequest(
                user_id=str(user_id),
                world_id="trpg_01",
                session_id=session_id,
                message=msg,
                step="6",  # 直接设置 step
                ext_param={}
            )
            
            try:
                response = await service.process_request(request)
                content = response.get("content", "")[:100]
                print(f"GM: {content}...")
            except Exception as e:
                print(f"错误: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # 等待异步总结生成
            await asyncio.sleep(2)
        
        # 检查总结是否生成
        print("\n=== 等待异步总结生成 (5秒) ===")
        await asyncio.sleep(5)
        
        info = get_session_info(session_id)
        print(f"\n=== 最终状态 ===")
        print(f"当前轮数: {info['turn_number']}")
        print(f"总结状态: {'有' if info['has_summary'] else '无'} (长度: {info['summary_len']})")
        
        if info['summary_preview']:
            print(f"\n总结预览:\n{info['summary_preview']}...")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("对话总结触发测试")
    print("=" * 60)
    asyncio.run(test_summary_trigger())
