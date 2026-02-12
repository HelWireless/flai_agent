#!/usr/bin/env python3
"""
副本世界（Freak World）完整流程测试脚本

测试 action=start → step=1(选性别) → step=2(confirm获取角色) → step=2(选角色) → step=3(对话)
每一步打印请求和响应，方便排查问题。

使用方式：
    python scripts/test_freak_world_flow.py

要求服务已启动在 http://127.0.0.1:8000
"""
import json
import time
import sys
import os
import pytest
from fastapi.testclient import TestClient

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.main import app
    client = TestClient(app)
except ImportError:
    client = None

BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "/pillow/freak-world/chat"

# 测试参数
# === 测试参数（可修改） ===
USER_ID = "9999999"
WORLD_ID = "world_10"    # world_01=深渊暗湖 world_04=修仙 world_06=末日 world_10=古风 world_13=仙侠 world_17=蒸汽朋克 world_21=暗黑 world_23=奇幻
GM_ID = "gm_06"          # gm_01=焰(女) gm_02=璃(女) gm_06=筑(男) gm_07=淮(男) gm_08=铎(男)
GENDER = "male"           # male / female
SESSION_ID = ""


def separator(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_request(data: dict):
    print(f"\n📤 请求:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_response(resp, label: str = "响应"):
    print(f"\n📥 {label} (status={resp.status_code}):")
    try:
        body = resp.json()
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return body
    except Exception:
        print(resp.text[:500])
        return None


def print_sse_response(resp, label: str = "SSE 响应"):
    """解析 SSE 流式响应"""
    print(f"\n📥 {label} (status={resp.status_code}):")
    full_content = ""
    result = None
    for line in resp.iter_lines():
        if line.startswith("data: "):
            data_str = line[6:]
            try:
                data = json.loads(data_str)
                if data.get("type") == "delta":
                    full_content += data.get("content", "")
                    # 打印进度点
                    sys.stdout.write(".")
                    sys.stdout.flush()
                elif data.get("type") == "done":
                    result = data.get("result", {})
                    print()  # 换行
                elif data.get("type") == "error":
                    print(f"\n❌ SSE Error: {data.get('message', 'unknown')}")
                    return data
            except json.JSONDecodeError:
                pass

    if full_content:
        print(f"\n完整内容 ({len(full_content)} 字):")
        # 最多打印前 800 字
        if len(full_content) > 800:
            print(full_content[:800] + "\n... (已截断)")
        else:
            print(full_content)

    if result:
        print(f"\n最终结果:")
        # 如果 content 太长，截断显示
        display = dict(result)
        if isinstance(display.get("content"), str) and len(display["content"]) > 500:
            display["content"] = display["content"][:500] + "...(截断)"
        print(json.dumps(display, ensure_ascii=False, indent=2))

    return result


def call_api(data: dict, stream: bool = False):
    """调用 API，支持同步和流式两种模式"""
    print_request(data)
    if client is None:
        print("\n❌ 无法加载 FastAPI app，请确保在项目根目录运行")
        return None
        
    try:
        if stream:
            # TestClient 支持 stream，但解析方式略有不同
            with client.stream("POST", ENDPOINT, json=data) as resp:
                return print_sse_response(resp)
        else:
            resp = client.post(ENDPOINT, json=data)
            return print_response(resp)
    except Exception as e:
        print(f"\n❌ 请求异常: {e}")
        return None


def run_step0_start():
    """Step 0: action=start → 返回 GM 介绍 + 世界背景 + 性别选择"""
    separator("Step 0: action=start (开始游戏)")

    data = {
        "userId": USER_ID,
        "worldId": WORLD_ID,
        "sessionId": SESSION_ID,
        "gmId": GM_ID,
        "step": "0",
        "message": "",
        "extParam": {"action": "start"},
        "stream": False
    }
    result = call_api(data)
    return result

def run_step1_select_gender(session_id: str):
    """Step 1: 选择性别 → 世界叙事 (流式 markdown)"""
    separator(f"Step 1: selection={GENDER} (选择性别，获取世界叙事)")
    data = {
        "userId": USER_ID,
        "worldId": WORLD_ID,
        "sessionId": session_id,
        "gmId": GM_ID,
        "step": "1",
        "message": "",
        "extParam": {"selection": GENDER},
        "stream": False
    }
    result = call_api(data)
    return result

def run_step2_confirm(session_id: str):
    """Step 2: selection=confirm → 获取角色列表 (JSON)"""
    separator("Step 2: selection=confirm (获取角色列表)")
    data = {
        "userId": USER_ID,
        "worldId": WORLD_ID,
        "sessionId": session_id,
        "gmId": GM_ID,
        "step": "2",
        "message": "",
        "extParam": {"selection": "confirm"},
        "stream": False
    }
    result = call_api(data)
    return result

def run_step2_select_char(session_id: str, char_id: str = "char_01"):
    """Step 2: selection=char_XX → 选定角色，进入游戏"""
    separator(f"Step 2: selection={char_id} (选定角色)")
    data = {
        "userId": USER_ID,
        "worldId": WORLD_ID,
        "sessionId": session_id,
        "gmId": GM_ID,
        "step": "2",
        "message": "",
        "extParam": {"selection": char_id},
        "stream": False
    }
    result = call_api(data)
    return result

def run_step3_dialogue(session_id: str, message: str = "你好，我叫小明"):
    """Step 3: 游戏对话"""
    separator(f"Step 3: 游戏对话 (message='{message}')")
    data = {
        "userId": USER_ID,
        "worldId": WORLD_ID,
        "sessionId": session_id,
        "gmId": GM_ID,
        "step": "3",
        "message": message,
        "extParam": {},
        "stream": False
    }
    result = call_api(data)
    return result

@pytest.mark.skip(reason="Integration test requiring complex setup")
def test_freak_world_full_flow():
    """Pytest entry point for full flow"""
    if client is None:
        pytest.skip("FastAPI app not loaded")
    
    session_id = f"fw_test_{int(time.time()) % 100000}"
    
    # Step 0
    res0 = run_step0_start()
    assert res0 is not None
    
    # Step 1
    res1 = run_step1_select_gender(session_id)
    assert res1 is not None
    
    # Step 2 confirm
    res2_list = run_step2_confirm(session_id)
    assert res2_list is not None
    
    # Step 2 select
    res2_select = run_step2_select_char(session_id)
    assert res2_select is not None
    
    # Step 3
    res3 = run_step3_dialogue(session_id)
    assert res3 is not None


def extract_session_id_from_log():
    """从 step0 结果中无法直接获取 session_id，需要复用"""
    # step0 不返回 session_id，需要从数据库或日志获取
    # 这里我们用一个固定的 session_id 来测试
    return f"fw_test_{int(time.time())}"


def main():
    print("=" * 70)
    print("  副本世界（Freak World）完整流程测试")
    print(f"  服务地址: {BASE_URL}")
    print(f"  用户: {USER_ID}, 世界: {WORLD_ID}, GM: {GM_ID}")
    print("=" * 70)

    # 使用固定 session_id 方便追踪
    session_id = f"fw_test_{int(time.time()) % 100000}"
    print(f"\n🔑 使用 session_id: {session_id}")

    # Step 0: 开始游戏
    step0_result = run_step0_start()
    if not step0_result:
        print("\n❌ Step 0 失败，终止测试")
        return

    # 短暂等待
    time.sleep(1)

    # Step 1: 选择性别 → 世界叙事
    # 注意：step0 没有返回 session_id，需要用请求时传入的
    # 第一次请求如果 session_id 为空，后端会自动创建
    # 后续请求需要用后端创建的 session_id，但我们无法从响应中获取
    # 所以我们用固定 session_id 重新走流程
    print(f"\n💡 注意: action=start 不返回 session_id，使用新 session_id: {session_id}")

    # 先用新 session_id 开始
    data_start = {
        "userId": USER_ID,
        "worldId": WORLD_ID,
        "sessionId": session_id,
        "gmId": GM_ID,
        "step": "0",
        "message": "",
        "extParam": {"action": "start"},
        "stream": False
    }
    print(f"\n🔄 用新 session_id 重新 start...")
    start_result = call_api(data_start)
    time.sleep(1)

    # Step 1: 选性别
    step1_result = run_step1_select_gender(session_id)
    time.sleep(1)

    # Step 2: 获取角色列表
    step2_list = run_step2_confirm(session_id)
    time.sleep(1)

    if step2_list:
        content = step2_list.get("content", {})
        if isinstance(content, dict):
            selections = content.get("selections", [])
            if selections:
                char_id = selections[0].get("id", "char_01")
                char_name = selections[0].get("text", "?")
                print(f"\n💡 将选择第一个角色: {char_name} ({char_id})")

                # Step 2: 选定角色
                step2_select = run_step2_select_char(session_id, char_id)
                time.sleep(1)

                # Step 3: 对话
                run_step3_dialogue(session_id, "你好，我叫小明")

    # 总结
    separator("测试总结")
    print("""
已知问题分析:

1. Step 0 (action=start) 背景太少
   - 当前: 只返回 GM 名字 + traits 拼接字符串，没有调用 LLM
   - 期望: 应该调用 LLM，让 GM 执行完整引导（自我介绍 → 新沪市 → 通道 → 世界核心 → 确认性别）
   - 或者: 至少用丰富的预设文案替代简单拼接

2. Step 1 (selection=female) 世界叙事
   - 当前: 只发 "我期待见到的原住民是女性。" 给 LLM，无 prior 对话
   - 问题: LLM 看到 system prompt 中的 GM 引导步骤(2.1-2.7)，试图从头开始
   - 期望: 应该在 messages 中注入 GM 引导对话作为上下文，让 LLM 从世界叙事(1.1)开始

3. Step 1 → Step 2 上下文断裂
   - step2 的角色生成使用了独立的 prompt（不含 system prompt），与游戏主线脱节
   - 进入游戏后的 step2 选角色，注入的假历史太简略
""")


if __name__ == "__main__":
    main()
