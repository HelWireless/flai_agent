#!/usr/bin/env python3
"""
COC 克苏鲁跑团完整流程测试脚本

测试流程:
  action=start → action=select_character(step1 属性) → step1 confirm(step2 次级属性)
  → step2 confirm(step3 职业) → step3 选职业(step4 角色确认) → step4 confirm(step5 装备)
  → step5 confirm(step6 游戏) → step6 对话 → action=save 存档 → action=load 读档

使用方式:
    python scripts/test_coc_flow.py

要求服务已启动在 http://127.0.0.1:8000
"""
import json
import time
import sys
import httpx

BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = f"{BASE_URL}/pillow/coc/chat"

# === 测试参数 ===
USER_ID = "9999998"
WORLD_ID = "trpg_01"
GM_ID = "gm_02"      # 璃
SESSION_ID = ""
SAVE_ID = f"test_save_{int(time.time()) % 100000}"


def separator(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_request(data: dict):
    # 精简打印
    compact = {k: v for k, v in data.items() if v or k in ("message", "step")}
    print(f"\n  >>> {json.dumps(compact, ensure_ascii=False)}")


def call_api(data: dict):
    """调用 API（同步模式）"""
    print_request(data)
    try:
        resp = httpx.post(ENDPOINT, json=data, timeout=180)
        body = resp.json()

        content = body.get("content", "")
        if isinstance(content, dict):
            # JSON 响应：打印关键字段
            desc = content.get("description", content.get("title", ""))
            if desc:
                print(f"  description: {str(desc)[:120]}")
            # 打印 selections
            sels = content.get("selections", [])
            if sels:
                sel_text = ", ".join([f"{s['id']}={s['text']}" for s in sels[:6]])
                print(f"  selections: [{sel_text}]")
            # 打印 attributes
            attrs = content.get("attributes", [])
            if attrs:
                attr_text = ", ".join([f"{a['key']}={a['value']}" for a in attrs[:8]])
                print(f"  attributes: [{attr_text}]")
            # 打印 professions
            profs = content.get("professions", [])
            if profs:
                for p in profs:
                    print(f"  {p['id']}: {p['name']} - {p.get('description', '')[:40]}")
            # 打印 investigatorCard
            card = content.get("investigatorCard", {})
            if card:
                print(f"  investigatorCard: {card.get('name', '?')} {card.get('gender', '?')} {card.get('age', '?')}岁 {card.get('profession', '?')}")
            # 打印 equipmentList
            equip = content.get("equipmentList", {})
            if equip and equip.get("equipment"):
                eq_names = [e["name"] for e in equip["equipment"][:5]]
                print(f"  equipment: {eq_names}")
        elif isinstance(content, str):
            # markdown 响应：截断打印
            text = content[:200] + ("..." if len(content) > 200 else "")
            print(f"  content ({len(content)}字): {text}")
        else:
            print(f"  content: {str(content)[:200]}")

        return body
    except httpx.ConnectError:
        print("\n  !!! 无法连接到服务器")
        sys.exit(1)
    except Exception as e:
        print(f"\n  !!! 请求异常: {e}")
        return None


def main():
    separator("COC 完整流程测试")
    print(f"  服务: {BASE_URL}  用户: {USER_ID}  GM: {GM_ID}  存档ID: {SAVE_ID}")

    session_id = f"coc_test_{int(time.time()) % 100000}"

    # ========== Step 0: 开始游戏 ==========
    separator("Step 0: action=start (背景介绍)")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "0", "message": "",
        "extParam": {"action": "start"}, "stream": False
    })
    if not r:
        return
    time.sleep(1)

    # ========== Step 1: 进入角色创建 → 属性分配 ==========
    separator("Step 1: action=select_character (属性分配)")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "1", "message": "",
        "extParam": {"action": "select_character"}, "stream": False
    })
    if not r:
        return
    time.sleep(1)

    # ========== Step 1 → Step 2: 确认属性 → 次级属性 ==========
    separator("Step 1 confirm → Step 2 (次级属性)")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "1", "message": "",
        "extParam": {"selection": "confirm"}, "stream": False
    })
    if not r:
        return
    time.sleep(1)

    # ========== Step 2 → Step 3: 确认次级属性 → 职业选择 ==========
    separator("Step 2 confirm → Step 3 (职业选择)")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "2", "message": "",
        "extParam": {"selection": "confirm"}, "stream": False
    })
    if not r:
        return

    # 找到第一个职业 ID
    content = r.get("content", {})
    profs = content.get("professions", []) if isinstance(content, dict) else []
    prof_id = profs[0]["id"] if profs else "prof_01"
    prof_name = profs[0]["name"] if profs else "?"
    print(f"\n  >>> 将选择职业: {prof_name} ({prof_id})")
    time.sleep(1)

    # ========== Step 3: 选择职业 → Step 4 角色确认 ==========
    separator(f"Step 3 select {prof_id} → Step 4 (角色确认)")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "3", "message": "",
        "extParam": {"selection": prof_id}, "stream": False
    })
    if not r:
        return
    time.sleep(1)

    # ========== Step 4: 确认角色 → Step 5 装备 ==========
    separator("Step 4 confirm → Step 5 (装备+属性摘要)")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "4", "message": "",
        "extParam": {"selection": "confirm"}, "stream": False
    })
    if not r:
        return
    time.sleep(1)

    # ========== Step 5: 确认装备 → Step 6 开始游戏 ==========
    separator("Step 5 confirm → Step 6 (游戏开始)")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "5", "message": "",
        "extParam": {"selection": "confirm"}, "stream": False
    })
    if not r:
        return
    time.sleep(1)

    # ========== Step 6: 游戏对话 ==========
    separator("Step 6: 游戏对话")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "6", "message": "我环顾四周，观察这个房间",
        "extParam": {}, "stream": False
    })
    if not r:
        return
    time.sleep(1)

    # ========== 存档 ==========
    separator(f"存档: saveId={SAVE_ID}")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": session_id,
        "gmId": GM_ID, "step": "6", "message": "",
        "extParam": {"action": "save", "saveId": SAVE_ID}, "stream": False
    })
    if not r:
        return

    save_ok = r.get("content", "")
    if "存档已保存" in str(save_ok):
        print("\n  +++ 存档成功!")
    else:
        print(f"\n  --- 存档可能失败: {str(save_ok)[:100]}")
    time.sleep(1)

    # ========== 读档 ==========
    separator(f"读档: saveId={SAVE_ID}")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": "",
        "gmId": GM_ID, "step": "0", "message": "",
        "extParam": {"action": "load", "saveId": SAVE_ID}, "stream": False
    })
    if not r:
        return

    load_content = str(r.get("content", ""))
    if "读档成功" in load_content:
        print("\n  +++ 读档成功!")
    else:
        print(f"\n  --- 读档结果: {load_content[:150]}")

    # ========== 也测试 integer saveId（模拟前端传 int） ==========
    separator(f"读档(int saveId): saveId={SAVE_ID} as concept / 用数字99999测试报错")
    r = call_api({
        "userId": USER_ID, "worldId": WORLD_ID, "sessionId": "",
        "gmId": GM_ID, "step": "0", "message": "",
        "extParam": {"action": "load", "saveId": 99999}, "stream": False
    })
    if r:
        load_content = str(r.get("content", ""))
        if "未找到存档" in load_content:
            print("\n  +++ int saveId 正确处理（未找到 → 说明查询没报错，类型转换OK）")
        else:
            print(f"\n  --- 结果: {load_content[:150]}")

    separator("测试完成")


if __name__ == "__main__":
    main()
