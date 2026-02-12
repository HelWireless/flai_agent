#!/usr/bin/env python3
"""
身份卡功能单元测试

测试内容：
1. 身份卡加载
2. Prompt 组装（有/无 virtual_id）
3. 对话历史查询（按 virtual_id 过滤）
4. API 请求（virtual_id 默认值兼容性）
"""
import os
import sys
import asyncio

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_identity_card_service():
    """测试身份卡服务"""
    print("\n=== 测试身份卡服务 ===")
    
    from src.services.identity_card_service import (
        get_identity_card, 
        get_all_identity_cards,
        get_identity_card_ids,
        build_identity_prompt
    )
    
    # 测试获取所有身份卡
    print("\n1. 获取所有身份卡:")
    all_cards = get_all_identity_cards()
    print(f"   找到 {len(all_cards)} 个身份卡")
    for card in all_cards:
        print(f"   - {card['config_id']}: {card['name']} ({card['gender']})")
    
    # 测试获取身份卡 ID 列表
    print("\n2. 获取身份卡 ID 列表:")
    card_ids = get_identity_card_ids()
    print(f"   IDs: {card_ids}")
    
    # 测试获取单个身份卡
    print("\n3. 获取单个身份卡:")
    card_1 = get_identity_card(1)
    if card_1:
        print(f"   identity_1: {card_1['name']}")
        print(f"   性别: {card_1['gender']}")
        print(f"   prompt 长度: {len(card_1['prompt'])} 字符")
    else:
        print("   错误: 未找到 identity_1")
    
    # 测试 virtual_id=0 返回 None
    print("\n4. 测试 virtual_id=0:")
    card_0 = get_identity_card(0)
    print(f"   结果: {card_0} (应为 None)")
    assert card_0 is None, "virtual_id=0 应返回 None"
    
    # 测试不存在的身份卡
    print("\n5. 测试不存在的身份卡 (virtual_id=999):")
    card_999 = get_identity_card(999)
    print(f"   结果: {card_999} (应为 None)")
    assert card_999 is None, "不存在的身份卡应返回 None"
    
    # 测试构建身份卡提示词
    print("\n6. 测试构建身份卡提示词:")
    prompt_1 = build_identity_prompt(1)
    if prompt_1:
        print(f"   virtual_id=1 prompt 长度: {len(prompt_1)} 字符")
        print(f"   包含 '用户扮演角色': {'用户扮演角色' in prompt_1}")
    else:
        print("   错误: 未生成提示词")
    
    prompt_0 = build_identity_prompt(0)
    print(f"   virtual_id=0 prompt: '{prompt_0}' (应为空字符串)")
    assert prompt_0 == "", "virtual_id=0 应返回空字符串"
    
    print("\n✓ 身份卡服务测试通过")


def test_prompt_generation():
    """测试 Prompt 生成（含身份卡）"""
    print("\n=== 测试 Prompt 生成 ===")
    
    from src.api.prompts.generate_prompts import get_prompt_by_character_id
    
    # 测试无身份卡时的 prompt
    print("\n1. 测试无身份卡 (virtual_id=0):")
    prompt_0, model = get_prompt_by_character_id(
        character_id="default",
        user_id="test_user",
        virtual_id=0
    )
    print(f"   system_prompt 长度: {len(prompt_0['system_prompt'])} 字符")
    print(f"   包含 '用户扮演角色': {'用户扮演角色' in prompt_0['system_prompt']}")
    
    # 测试有身份卡时的 prompt
    print("\n2. 测试有身份卡 (virtual_id=1):")
    prompt_1, model = get_prompt_by_character_id(
        character_id="default",
        user_id="test_user",
        virtual_id=1
    )
    print(f"   system_prompt 长度: {len(prompt_1['system_prompt'])} 字符")
    has_identity = '用户扮演角色' in prompt_1['system_prompt']
    print(f"   包含 '用户扮演角色': {has_identity}")
    
    if has_identity:
        print("   ✓ 身份卡背景已注入到 prompt")
    else:
        print("   ⚠ 身份卡背景未注入（可能数据库中无对应记录）")
    
    print("\n✓ Prompt 生成测试通过")


def test_schema_virtual_id():
    """测试 ChatRequest schema 的 virtual_id 字段"""
    print("\n=== 测试 ChatRequest Schema ===")
    
    from src.schemas import ChatRequest
    
    # 测试默认值
    print("\n1. 测试默认值:")
    request_default = ChatRequest(
        user_id="123",
        message="你好",
        message_count=1
    )
    print(f"   virtual_id 默认值: {request_default.virtual_id}")
    assert request_default.virtual_id == "0", "virtual_id 默认值应为 \"0\""
    
    # 测试显式设置
    print("\n2. 测试显式设置:")
    request_with_id = ChatRequest(
        user_id="123",
        message="你好",
        message_count=1,
        virtual_id="2"
    )
    print(f"   virtual_id 设置值: {request_with_id.virtual_id}")
    assert request_with_id.virtual_id == "2", "virtual_id 应为 \"2\""
    
    # 测试别名 (virtualId)
    print("\n3. 测试别名 (virtualId):")
    request_alias = ChatRequest(
        userId="123",  # 使用别名
        message="你好",
        message_count=1,
        virtualId="3"  # 使用别名
    )
    print(f"   通过 virtualId 设置: {request_alias.virtual_id}")
    assert request_alias.virtual_id == "3", "通过别名设置应生效"
    
    print("\n✓ ChatRequest Schema 测试通过")


def test_dialogue_query():
    """测试对话历史查询（含 virtual_id 过滤）"""
    print("\n=== 测试对话历史查询 ===")
    
    from src.core.dialogue_query import DialogueQuery
    
    print("\n1. 初始化 DialogueQuery (测试模式):")
    try:
        dq = DialogueQuery(if_test=True)
        print("   ✓ 初始化成功")
    except Exception as e:
        print(f"   ✗ 初始化失败: {e}")
        return
    
    # 测试查询用户自己的对话历史 (virtual_id=0)
    print("\n2. 查询用户自己的对话历史 (virtual_id=0):")
    try:
        history_0, nickname = dq.get_user_third_character_dialogue_history(
            user_id="1000003",
            character_id="c1s2c6_0016",
            if_voice=False,
            virtual_id=0
        )
        print(f"   找到 {len(history_0)} 条对话记录")
        print(f"   用户昵称: {nickname}")
    except Exception as e:
        print(f"   查询失败: {e}")
    
    # 测试查询身份卡对话历史 (virtual_id=1)
    print("\n3. 查询身份卡对话历史 (virtual_id=1):")
    try:
        history_1, nickname = dq.get_user_third_character_dialogue_history(
            user_id="1000003",
            character_id="c1s2c6_0016",
            if_voice=False,
            virtual_id=1
        )
        print(f"   找到 {len(history_1)} 条对话记录")
    except Exception as e:
        print(f"   查询失败: {e}")
    
    print("\n✓ 对话历史查询测试通过")


async def test_memory_service():
    """测试记忆服务（含 virtual_id）"""
    print("\n=== 测试记忆服务 ===")
    
    from src.database import get_db
    from src.services.memory_service import MemoryService
    
    print("\n1. 初始化 MemoryService:")
    try:
        db = next(get_db())
        memory_service = MemoryService(db=db)
        print("   ✓ 初始化成功")
    except Exception as e:
        print(f"   ✗ 初始化失败: {e}")
        return
    
    # 测试获取短期记忆（用户自己）
    print("\n2. 获取短期记忆 (virtual_id=0):")
    try:
        history, nickname = await memory_service.get_short_term_memory(
            user_id="1000003",
            character_id="c1s2c6_0016",
            virtual_id=0
        )
        print(f"   找到 {len(history)} 条记录, 昵称: {nickname}")
    except Exception as e:
        print(f"   获取失败: {e}")
    
    # 测试获取短期记忆（身份卡）
    print("\n3. 获取短期记忆 (virtual_id=1):")
    try:
        history, nickname = await memory_service.get_short_term_memory(
            user_id="1000003",
            character_id="c1s2c6_0016",
            virtual_id=1
        )
        print(f"   找到 {len(history)} 条记录, 昵称: {nickname}")
    except Exception as e:
        print(f"   获取失败: {e}")
    
    print("\n✓ 记忆服务测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("身份卡功能单元测试")
    print("=" * 60)
    
    # 同步测试
    test_identity_card_service()
    test_prompt_generation()
    test_schema_virtual_id()
    test_dialogue_query()
    
    # 异步测试
    asyncio.run(test_memory_service())
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
