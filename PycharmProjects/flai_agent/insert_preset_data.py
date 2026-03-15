"""
插入预制数据到数据库
"""
import sys
from pathlib import Path

# 将项目根目录添加到 python 路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.database import SessionLocal
from src.models.world_preset_data import WorldRaceAppearance, WorldGenderPersonality

# 预制数据
RACE_APPEARANCE_DATA = [
    ('world_01', '深渊潜行者', '黑色紧身皮甲裹着修长身形，腰间悬挂着发光的水下呼吸器，眼罩下隐约可见第三只眼的轮廓。'),
    ('world_01', '炼金术士', '白大褂上沾满各色药剂污渍，护目镜推到额头上，手指因长期接触化学试剂而微微泛蓝。'),
    ('world_01', '暗影舞者', '轻纱长裙在黑暗中若隐若现，脚踝系着银铃却无声响，每一步都像是在空气中滑行。'),
    ('world_01', '深渊歌者', '贝壳编织的项链垂至腰间，嗓音带着奇异的共鸣，歌声能让湖水泛起涟漪。'),
    ('world_01', '水下考古学家', '潜水服改装的探险装，背着氧气瓶和采集箱，头盔上装着强光探照灯。'),
    ('world_01', '暗湖渔夫', '蓑衣斗笠，手持特制钓竿，鱼篓里装的不是鱼而是发光的深渊生物。'),
    ('world_01', '深渊商人', '华丽长袍下藏着无数口袋，每个口袋都通向不同的储物空间，眼神精明而警惕。'),
    ('world_01', '灵魂引渡人', '黑袍罩住全身，只露出苍白的下巴，手持一盏永不熄灭的引魂灯。'),
    ('world_01', '深渊铁匠', '肌肉虬结的手臂上布满烫伤疤痕，围裙上挂着各种奇特的工具，能打造水下专用装备。'),
    ('world_01', '暗湖医师', '药箱不离身，白袍上绣着深渊十字，擅长治疗深渊生物造成的特殊伤势。'),
    ('world_01', '深渊学者', '眼镜片厚如瓶底，笔记本从不离手，对深渊的一切都充满狂热的求知欲。'),
    ('world_01', '暗影刺客', '全身笼罩在阴影中，只有眼睛反射着微光，步伐轻盈得如同幽灵。'),
    ('world_01', '深渊酿酒师', '酒葫芦从不离身，身上散发着混合酒香，能酿造让人看见幻觉的特殊酒液。'),
    ('world_01', '水下园丁', '培育着发光的水下植物，指甲缝里永远有泥土，能与植物进行某种交流。'),
    ('world_01', '深渊占卜师', '水晶球在黑暗中发出幽光，眼神迷离，声称能听见深渊的低语。'),
    ('world_01', '暗湖守卫', '重甲覆身，手持三叉戟，眼神坚毅，是酒馆最可靠的守护者。'),
    ('world_01', '深渊厨师', '围裙上沾满各种食材残渣，能烹饪深渊生物制成的美味佳肴。'),
    ('world_01', '水下乐师', '竖琴的琴弦由深渊蛛丝制成，音乐能安抚狂暴的深渊生物。'),
    ('world_01', '深渊信使', '速度极快，能在水下自由穿梭，负责传递各势力之间的秘密信息。'),
    ('world_01', '暗湖炼金师', '专注于研究深渊物质与普通物质的融合，实验室经常传出爆炸声。'),
]

GENDER_PERSONALITY_DATA = [
    # 男性
    ('world_01', '男性', '沉稳内敛，言语不多但每句话都经过深思熟虑，眼神中藏着历经沧桑的疲惫。'),
    ('world_01', '男性', '豪爽直率，喜欢大声说笑，对朋友极其忠诚，但脾气火爆容易冲动。'),
    ('world_01', '男性', '神秘莫测，总是若有所思，很少谈及自己的过去，仿佛背负着沉重的秘密。'),
    ('world_01', '男性', '玩世不恭，表面轻浮爱开玩笑，内心却极度缺乏安全感，用幽默掩饰脆弱。'),
    ('world_01', '男性', '冷酷无情，对敌人毫不留情，但对认定的同伴会默默付出一切。'),
    ('world_01', '男性', '温文尔雅，举止得体，谈吐间透露出良好的教养，但偶尔流露出一丝忧郁。'),
    ('world_01', '男性', '野心勃勃，对力量有着执着的追求，眼神中燃烧着永不熄灭的野心之火。'),
    ('world_01', '男性', '懒散随性，似乎对什么都不在乎，但在关键时刻却意外地可靠。'),
    ('world_01', '男性', '偏执疯狂，对某个目标有着病态的执着，为了达成目的不择手段。'),
    ('world_01', '男性', '正义感强烈，无法容忍任何不公，即使面对强敌也会挺身而出。'),
    # 女性
    ('world_01', '女性', '冷艳高傲，对人保持距离，但偶尔会流露出一丝不易察觉的温柔。'),
    ('world_01', '女性', '活泼开朗，像个小太阳一样温暖着周围的人，但深夜时会独自发呆。'),
    ('world_01', '女性', '神秘优雅，举止间带着说不出的韵味，仿佛知晓世间所有的秘密。'),
    ('world_01', '女性', '倔强固执，认定的事情绝不回头，即使撞得头破血流也要坚持到底。'),
    ('world_01', '女性', '温柔体贴，总是默默照顾着身边的人，但从不诉说自己的辛苦。'),
    ('world_01', '女性', '狡黠聪慧，喜欢捉弄人，但从未真正伤害过任何人，内心其实很善良。'),
    ('world_01', '女性', '独立自主，不依赖任何人，用自己的力量在这个危险的世界生存。'),
    ('world_01', '女性', '多愁善感，容易被美好的事物打动，但也因此常常陷入莫名的忧伤。'),
    ('world_01', '女性', '热情奔放，敢爱敢恨，从不掩饰自己的情感，活得肆意而洒脱。'),
    ('world_01', '女性', '冷静理智，即使在最危险的情况下也能保持清醒，是团队中的智囊。'),
]

def insert_preset_data():
    """插入预制数据"""
    db = SessionLocal()
    try:
        # 清空旧数据
        db.query(WorldRaceAppearance).filter(WorldRaceAppearance.world_id == 'world_01').delete()
        db.query(WorldGenderPersonality).filter(WorldGenderPersonality.world_id == 'world_01').delete()
        
        # 插入 race_appearance
        for i, (world_id, race, appearance) in enumerate(RACE_APPEARANCE_DATA):
            record = WorldRaceAppearance(
                world_id=world_id,
                race=race,
                appearance=appearance,
                status=1,
                sort_order=i
            )
            db.add(record)
        
        # 插入 gender_personality
        for i, (world_id, gender, personality) in enumerate(GENDER_PERSONALITY_DATA):
            record = WorldGenderPersonality(
                world_id=world_id,
                gender=gender,
                personality=personality,
                status=1,
                sort_order=i
            )
            db.add(record)
        
        db.commit()
        print(f"✅ 成功插入 {len(RACE_APPEARANCE_DATA)} 条 race_appearance 数据")
        print(f"✅ 成功插入 {len(GENDER_PERSONALITY_DATA)} 条 gender_personality 数据")
        print("✅ 世界 world_01 预制数据插入完成！")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 插入失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    insert_preset_data()
