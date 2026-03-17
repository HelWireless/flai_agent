"""
为世界生成符合特色的姓氏和名字数据
支持：
1. 按世界主题生成（暗湖酒馆 - 西方奇幻风）
2. 姓氏池 + 名字池（1 字/2 字）
3. 性别倾向
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.database import SessionLocal
from src.models.world_preset_data_optimized import WorldSurname, WorldGivenName

def generate_world_01_names():
    """
    为 world_01（暗湖酒馆·永夜歌谣）生成名字数据
    风格：西方奇幻 + 深渊神秘风
    """
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("为 world_01（暗湖酒馆）生成姓氏和名字...")
        print("=" * 60)
        
        # ========== 姓氏池（西方奇幻风） ==========
        surnames = [
            # 经典西式姓氏
            ("艾德", "西方"), ("路德", "西方"), ("西蒙", "西方"),
            ("维克", "西方"), ("卡伦", "西方"), ("雷恩", "西方"),
            ("诺瓦", "西方"), ("塞拉", "西方"), ("艾伦", "西方"),
            ("亚瑟", "西方"), ("罗兰", "西方"), ("艾瑞克", "西方"),
            
            # 神秘/深渊风格
            ("夜影", "神秘"), ("风语", "神秘"), ("星痕", "神秘"),
            ("月歌", "神秘"), ("霜华", "神秘"), ("炎舞", "神秘"),
            ("雷震", "神秘"), ("水镜", "神秘"), ("暗夜", "神秘"),
            ("晨曦", "神秘"), ("黄昏", "神秘"), ("午夜", "神秘"),
            
            # 贵族/古老风格
            ("冯·克里格", "贵族"), ("德·拉克鲁瓦", "贵族"),
            ("范·霍恩", "贵族"), ("冯·施特劳斯", "贵族"),
            ("德拉库尔", "贵族"), ("莫尔甘纳", "贵族"),
            
            # 深渊/水下风格
            ("深海", "深渊"), ("幽渊", "深渊"), ("潜渊", "深渊"),
            ("海歌", "深渊"), ("潮声", "深渊"), ("浪迹", "深渊"),
        ]
        
        print(f"\n插入 {len(surnames)} 个姓氏...")
        for i, (surname, style) in enumerate(surnames):
            record = WorldSurname(
                world_id='world_01',
                surname=surname,
                style=style,
                status=1,
                sort_order=i
            )
            db.add(record)
        
        # ========== 名字池（分 1 字和 2 字） ==========
        given_names_1char = [
            # 男性倾向（1 字）
            ("杰", "男性", "阳刚"), ("勇", "男性", "阳刚"), ("毅", "男性", "坚毅"),
            ("锋", "男性", "锐利"), ("烈", "男性", "霸气"), ("战", "男性", "霸气"),
            ("冥", "男性", "神秘"), ("夜", "男性", "神秘"), ("影", "男性", "神秘"),
            
            # 女性倾向（1 字）
            ("雅", "女性", "优雅"), ("柔", "女性", "温柔"), ("婉", "女性", "优雅"),
            ("梦", "女性", "梦幻"), ("诗", "女性", "文艺"), ("雪", "女性", "清冷"),
            ("月", "女性", "神秘"), ("灵", "女性", "灵动"), ("歌", "女性", "艺术"),
            
            # 中性（1 字）
            ("云", "中性", "飘逸"), ("风", "中性", "自由"), ("雨", "中性", "清新"),
            ("星", "中性", "神秘"), ("辰", "中性", "宏大"), ("岚", "中性", "诗意"),
        ]
        
        given_names_2char = [
            # 男性倾向（2 字）
            ("子轩", "男性", "文雅"), ("浩然", "男性", "大气"), ("宇轩", "男性", "不凡"),
            ("博文", "男性", "儒雅"), ("志远", "男性", "志向"), ("明哲", "男性", "睿智"),
            ("天翊", "男性", "翱翔"), ("鸿煊", "男性", "光明"), ("嘉懿", "男性", "美好"),
            
            # 女性倾向（2 字）
            ("若兰", "女性", "高洁"), ("思琪", "女性", "聪慧"), ("梦瑶", "女性", "美好"),
            ("雨桐", "女性", "清新"), ("诗涵", "女性", "文艺"), ("雅婷", "女性", "优雅"),
            ("婉儿", "女性", "温柔"), ("雪凝", "女性", "清冷"), ("月华", "女性", "皎洁"),
            
            # 中性（2 字）
            ("星辰", "中性", "浩瀚"), ("风云", "中性", "变幻"), ("烟雨", "中性", "朦胧"),
            ("梦蝶", "中性", "奇幻"), ("流苏", "中性", "飘逸"), ("清歌", "中性", "悠扬"),
            
            # 深渊/神秘风格
            ("幽夜", "中性", "神秘"), ("冥河", "中性", "深邃"), ("深渊", "中性", "黑暗"),
            ("海妖", "中性", "魅惑"), ("潮汐", "中性", "律动"), ("暗涌", "中性", "流动"),
        ]
        
        print(f"插入 {len(given_names_1char)} 个 1 字名字...")
        offset = 0
        for i, (name, gender, style) in enumerate(given_names_1char):
            record = WorldGivenName(
                world_id='world_01',
                given_name=name,
                character_count=1,
                gender_tendency=gender,
                style=style,
                status=1,
                sort_order=offset + i
            )
            db.add(record)
        
        offset += len(given_names_1char)
        
        print(f"插入 {len(given_names_2char)} 个 2 字名字...")
        for i, (name, gender, style) in enumerate(given_names_2char):
            record = WorldGivenName(
                world_id='world_01',
                given_name=name,
                character_count=2,
                gender_tendency=gender,
                style=style,
                status=1,
                sort_order=offset + i
            )
            db.add(record)
        
        db.commit()
        
        total_names = len(given_names_1char) + len(given_names_2char)
        print(f"\n[SUCCESS] 名字数据插入成功！")
        print(f"\n已插入:")
        print(f"  - {len(surnames)} 个姓氏")
        print(f"  - {len(given_names_1char)} 个 1 字名字")
        print(f"  - {len(given_names_2char)} 个 2 字名字")
        print(f"  - 总计可组合：{len(surnames) * total_names} 个完整姓名")
        print("\n" + "=" * 60)
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] 插入失败：{e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    generate_world_01_names()
