#!/usr/bin/env python3
# -*- coding: utf-8 -*-
print("=== 开始插入预制数据 ===")

import sys
sys.path.insert(0, '.')

try:
    print("1. 导入模块...")
    from src.database import SessionLocal
    from src.models.world_preset_data import WorldRaceAppearance, WorldGenderPersonality
    
    print("2. 连接数据库...")
    db = SessionLocal()
    
    print("3. 清空旧数据...")
    db.query(WorldRaceAppearance).filter(WorldRaceAppearance.world_id == 'world_01').delete()
    db.query(WorldGenderPersonality).filter(WorldGenderPersonality.world_id == 'world_01').delete()
    db.commit()
    print("   已清空旧数据")
    
    print("4. 插入 race_appearance 数据...")
    races = [
        ('深渊潜行者', '黑色紧身皮甲裹着修长身形，腰间悬挂着发光的水下呼吸器。'),
        ('炼金术士', '白大褂上沾满各色药剂污渍，护目镜推到额头上。'),
        ('暗影舞者', '轻纱长裙在黑暗中若隐若现，脚踝系着银铃却无声响。'),
        ('深渊歌者', '贝壳编织的项链垂至腰间，嗓音带着奇异的共鸣。'),
        ('水下考古学家', '潜水服改装的探险装，背着氧气瓶和采集箱。'),
    ]
    
    for i, (race, appearance) in enumerate(races):
        record = WorldRaceAppearance(
            world_id='world_01',
            race=race,
            appearance=appearance,
            status=1,
            sort_order=i
        )
        db.add(record)
    
    db.commit()
    print(f"   已插入 {len(races)} 条 race_appearance 数据")
    
    print("5. 插入 gender_personality 数据...")
    personalities = [
        ('男性', '沉稳内敛，言语不多但每句话都经过深思熟虑。'),
        ('男性', '豪爽直率，喜欢大声说笑，对朋友极其忠诚。'),
        ('女性', '冷艳高傲，对人保持距离，但偶尔流露温柔。'),
        ('女性', '活泼开朗，像个小太阳一样温暖周围的人。'),
    ]
    
    for i, (gender, personality) in enumerate(personalities):
        record = WorldGenderPersonality(
            world_id='world_01',
            gender=gender,
            personality=personality,
            status=1,
            sort_order=i
        )
        db.add(record)
    
    db.commit()
    print(f"   已插入 {len(personalities)} 条 gender_personality 数据")
    
    db.close()
    print("\n=== 预制数据插入完成！ ===")
    
except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
    input("\n按回车键退出...")
