"""
测试 COC 跑团对话流程 - 验证历史对话是否正确工作，剧情是否能推动
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.services.coc_service import COCService
from src.services.llm_service import LLMService
from src.schemas import IWChatRequest


async def test_coc_dialogue_flow():
    """测试 COC 10 轮对话"""
    
    # 数据库配置
    host = '81.68.235.167'
    username = 'pillow'
    password = '1234QWERasdf!@#$'
    database_name = 'pillow_customer_test'
    
    encoded_password = urllib.parse.quote(password)
    DATABASE_URI = f'mysql+pymysql://{username}:{encoded_password}@{host}/{database_name}'
    engine = create_engine(DATABASE_URI, pool_recycle=3600, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    # 加载配置
    import yaml
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 初始化服务
    llm_service = LLMService(config)
    coc_service = COCService(llm_service, db, config)
    
    # 使用已存在的会话（有历史对话的）
    test_session_id = "RvqqtAKiSVTRejrr"
    user_id = "1000003"
    
    print("=" * 70)
    print("【COC 对话流程测试 - 验证历史对话是否正常工作】")
    print("=" * 70)
    print(f"Session ID: {test_session_id}")
    print(f"User ID: {user_id}")
    
    # 先查看当前历史对话数量
    history = coc_service._get_dialogue_history(test_session_id)
    print(f"\n当前历史对话数量: {len(history)} 条")
    
    # 显示最近 5 条历史
    print("\n【最近 5 条历史对话】")
    print("-" * 50)
    for msg in history[-5:]:
        role = msg['role']
        content = msg['content'][:60] if msg['content'] else '(空)'
        print(f"[{role}]: {content}...")
    
    # 模拟的玩家行动
    player_actions = [
        "A",  # 选择选项 A
        "我仔细观察周围的环境",
        "B",  # 选择选项 B  
        "我搜索房间里有什么线索",
        "我尝试打开那扇门",
        "A",
        "我检查一下自己的装备",
        "我向前走去",
        "B",
        "我大声呼喊看看有没有人回应",
    ]
    
    print("\n" + "=" * 70)
    print("【开始 10 轮对话测试】")
    print("=" * 70)
    
    for i, action in enumerate(player_actions, 1):
        print(f"\n{'='*70}")
        print(f"【第 {i} 轮】玩家输入: {action}")
        print("=" * 70)
        
        # 构建请求
        request = IWChatRequest(
            user_id=user_id,
            world_id="trpg_01",
            session_id=test_session_id,
            gm_id="gm_02",
            step="6",
            message=action,
            stream=False
        )
        
        # 调用非流式接口
        try:
            response = await coc_service.process_request(request)
            content = response.get("content", "")
            
            # 显示响应（限制长度）
            print(f"\n【GM 响应】")
            if len(content) > 500:
                print(content[:500] + "...(省略)")
            else:
                print(content)
                
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            break
        
        # 每轮之间稍微等待
        await asyncio.sleep(1)
    
    # 测试完成后查看历史对话变化
    print("\n" + "=" * 70)
    print("【测试完成 - 检查历史对话】")
    print("=" * 70)
    
    # 注意：由于对话是 Java 端写入的，Python 端调用后不会自动写入
    # 这里只是验证读取历史对话的功能是否正常
    
    db.close()
    print("\n测试结束。")


if __name__ == "__main__":
    asyncio.run(test_coc_dialogue_flow())
