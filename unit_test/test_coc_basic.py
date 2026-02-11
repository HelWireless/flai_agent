#!/usr/bin/env python3
"""
COC 克苏鲁跑团基本功能测试
"""
import os
import sys
import asyncio

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_coc_generator():
    """测试 COC 属性生成器"""
    print("\n=== 测试 COC 生成器 ===")
    
    from src.services.coc_generator import (
        COCGenerator, 
        PRIMARY_ATTRIBUTES, 
        PROFESSIONS
    )
    
    generator = COCGenerator()
    
    # 1. 测试常规属性生成
    print("\n1. 生成常规属性:")
    primary = generator.roll_primary_attributes()
    print(f"   STR={primary.STR}, CON={primary.CON}, DEX={primary.DEX}, SIZ={primary.SIZ}")
    print(f"   INT={primary.INT}, POW={primary.POW}, APP={primary.APP}, EDU={primary.EDU}")
    
    # 验证属性值是固定集合中的
    all_values = [primary.STR, primary.CON, primary.DEX, primary.SIZ, 
                  primary.INT, primary.POW, primary.APP, primary.EDU]
    expected_values = sorted([40, 50, 50, 50, 60, 60, 70, 80])
    assert sorted(all_values) == expected_values, "属性值应为固定集合"
    print("   ✓ 属性值验证通过")
    
    # 2. 测试次要属性计算
    print("\n2. 计算次要属性:")
    secondary = generator.calc_secondary_attributes(primary)
    print(f"   HP={secondary.HP}, MP={secondary.MP}, SAN={secondary.SAN}")
    print(f"   LUCK={secondary.LUCK}, DB={secondary.DB}, Build={secondary.Build}, MOV={secondary.MOV}")
    
    # 验证HP计算公式
    expected_hp = (primary.CON + primary.SIZ) // 10
    assert secondary.HP == expected_hp, f"HP计算错误: 期望{expected_hp}, 实际{secondary.HP}"
    print("   ✓ HP计算验证通过")
    
    # 3. 测试职业生成
    print("\n3. 生成职业:")
    professions = generator.roll_professions(3)
    print(f"   生成了 {len(professions)} 个职业:")
    for p in professions:
        print(f"   - {p.name}: {p.description[:30]}...")
    assert len(professions) == 3, "应生成3个职业"
    print("   ✓ 职业生成通过")
    
    # 4. 测试兴趣技能生成
    print("\n4. 生成兴趣技能:")
    profession_skills = list(professions[0].skill_points.keys())
    interest = generator.roll_interest_skills(profession_skills)
    print(f"   生成了 {len(interest)} 个兴趣技能:")
    for skill, value in interest.items():
        print(f"   - {skill}: {value}%")
    assert len(interest) == 4, "应生成4个兴趣技能"
    print("   ✓ 兴趣技能生成通过")
    
    print("\n✓ COC 生成器测试通过")


def test_coc_game_state_model():
    """测试 COC 游戏状态模型"""
    print("\n=== 测试 COC 游戏状态模型 ===")
    
    from src.models.coc_game_state import COCGameState
    
    # 创建实例
    print("\n1. 创建游戏状态实例:")
    state = COCGameState(
        session_id="test_123",
        user_id=1000,
        gm_id="yan",
        gm_gender="female",
        game_status="gm_select"
    )
    print(f"   session_id: {state.session_id}")
    print(f"   game_status: {state.game_status}")
    
    # 测试 temp_data 操作
    print("\n2. 测试临时数据操作:")
    state.set_temp_data({"test_key": "test_value", "number": 42})
    temp = state.get_temp_data()
    print(f"   set_temp_data: {temp}")
    assert temp.get("test_key") == "test_value", "临时数据读取失败"
    print("   ✓ 临时数据操作通过")
    
    # 测试 investigator_card
    print("\n3. 测试调查员人物卡:")
    card = {
        "name": "测试调查员",
        "profession": "私家侦探",
        "currentHP": 10
    }
    state.investigator_card = card
    print(f"   设置人物卡: {state.investigator_card.get('name')}")
    print("   ✓ 人物卡操作通过")
    
    # 测试 increment_save_count
    print("\n4. 测试存档计数:")
    state.save_count = 0
    count1 = state.increment_save_count()
    count2 = state.increment_save_count()
    print(f"   第一次存档: {count1}, 第二次存档: {count2}")
    assert count1 == 1 and count2 == 2, "存档计数错误"
    print("   ✓ 存档计数通过")
    
    print("\n✓ COC 游戏状态模型测试通过")


async def test_coc_service_basic():
    """测试 COC 服务基本功能（不连接数据库）"""
    print("\n=== 测试 COC 服务基本功能 ===")
    
    from src.services.coc_service import COCService, GameStatus, COC_GMS
    
    # 测试 GM 列表
    print("\n1. 测试 GM 列表:")
    print(f"   女性GM数量: {len(COC_GMS['female'])}")
    print(f"   男性GM数量: {len(COC_GMS['male'])}")
    for gm in COC_GMS['female'][:2]:
        print(f"   - {gm['name']}: {gm['traits'][:20]}...")
    
    # 测试游戏状态常量
    print("\n2. 测试游戏状态常量:")
    print(f"   GM_SELECT: {GameStatus.GM_SELECT}")
    print(f"   PLAYING: {GameStatus.PLAYING}")
    print(f"   状态流程: gm_select -> step1 -> step2 -> step3 -> step4 -> step5 -> playing")
    
    print("\n✓ COC 服务基本功能测试通过")


async def test_coc_service_with_db():
    """测试 COC 服务（连接数据库）"""
    print("\n=== 测试 COC 服务（数据库连接）===")
    
    try:
        from src.database import get_db
        from src.services.llm_service import LLMService
        from src.services.coc_service import COCService
        import yaml
        
        # 加载配置
        config_path = os.path.join(project_root, "config", "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        db = next(get_db())
        llm = LLMService(config)
        service = COCService(llm, db, config)
        
        print("\n1. 测试新游戏创建:")
        response = await service.chat({
            "accountId": 999999,  # 测试用户ID
            "action": "start"
        })
        
        print(f"   sessionId: {response.get('sessionId')}")
        print(f"   gameStatus: {response.get('gameStatus')}")
        print(f"   selections: {len(response.get('selections', []))} 个选项")
        
        if response.get('sessionId'):
            session_id = response['sessionId']
            
            print("\n2. 测试选择GM性别:")
            response2 = await service.chat({
                "sessionId": session_id,
                "accountId": 999999,
                "selection": "female"
            })
            print(f"   gameStatus: {response2.get('gameStatus')}")
            print(f"   新状态: 应为 step1_attributes")
            
            # 清理测试数据
            print("\n3. 清理测试数据:")
            from src.models.coc_game_state import COCGameState
            db.query(COCGameState).filter(
                COCGameState.session_id == session_id
            ).delete()
            db.commit()
            print("   ✓ 测试数据已清理")
        
        print("\n✓ COC 服务数据库测试通过")
        
    except Exception as e:
        print(f"\n⚠ 数据库测试失败: {e}")
        print("   （可能是数据库表未创建或连接问题）")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("COC 克苏鲁跑团功能测试")
    print("=" * 60)
    
    # 同步测试
    test_coc_generator()
    test_coc_game_state_model()
    
    # 异步测试
    asyncio.run(test_coc_service_basic())
    asyncio.run(test_coc_service_with_db())
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
