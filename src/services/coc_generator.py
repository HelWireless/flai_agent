"""
克苏鲁跑团(COC)调查员生成器
负责属性随机、次要属性计算、职业技能随机等
"""
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


# =====================================================
# 常量定义
# =====================================================

# 8个常规属性的固定数值组
PRIMARY_ATTRIBUTE_VALUES = [40, 50, 50, 50, 60, 60, 70, 80]

# 8个常规属性名称
PRIMARY_ATTRIBUTES = ["STR", "CON", "DEX", "SIZ", "INT", "POW", "APP", "EDU"]

# 常规属性中文名和说明
PRIMARY_ATTRIBUTE_INFO = {
    "STR": {"name": "力量", "description": "衡量调查员纯粹身体力量"},
    "CON": {"name": "体质", "description": "衡量调查员健康与强韧程度"},
    "DEX": {"name": "敏捷", "description": "衡量调查员身体灵活性与速度"},
    "SIZ": {"name": "体型", "description": "反映调查员身高与体重"},
    "INT": {"name": "智力", "description": "衡量调查员的智慧、洞察与推理能力"},
    "POW": {"name": "意志", "description": "衡量调查员的精神力量与魔法天赋"},
    "APP": {"name": "外貌", "description": "衡量调查员的外表吸引力"},
    "EDU": {"name": "教育", "description": "衡量调查员通过正规教育或社会磨练积累的知识"},
}

# 次要属性中文名和说明
SECONDARY_ATTRIBUTE_INFO = {
    "HP": {"name": "生命值", "description": "调查员能承受的伤害量"},
    "MP": {"name": "魔法值", "description": "意志÷5，用于施法或供能"},
    "SAN": {"name": "理智值", "description": "调查员的心理健康程度，等于意志值"},
    "LUCK": {"name": "幸运值", "description": "调查员的运气，3D6×5随机"},
    "DB": {"name": "伤害加值", "description": "近战伤害加成，基于力量+体型"},
    "Build": {"name": "体格", "description": "力量+体型的总值"},
    "MOV": {"name": "移动速度", "description": "人类固定为8"},
}

# 职业定义
PROFESSIONS = {
    "文物学家": {
        "name": "文物学家",
        "skills": ["估价", "艺术/手艺（鉴定）", "历史", "图书馆使用", "其他语言（拉丁语）", "说服", "侦查", "考古学"],
        "description": "专精于古董鉴定与文物研究"
    },
    "作家": {
        "name": "作家",
        "skills": ["艺术（文学）", "历史", "图书馆使用", "博物学", "其他语言（英语）", "母语", "心理学", "神秘学"],
        "description": "以文字为生，擅长观察与记录"
    },
    "医生": {
        "name": "医生",
        "skills": ["急救", "其他语言（拉丁语）", "医学", "心理学", "科学（生物学）", "科学（药学）", "精神分析", "聆听"],
        "description": "救死扶伤的医疗专家"
    },
    "记者": {
        "name": "记者",
        "skills": ["艺术/手艺（摄影）", "历史", "图书馆使用", "母语", "话术", "心理学", "侦查", "潜行"],
        "description": "追踪新闻线索的调查记者"
    },
    "警探": {
        "name": "警探",
        "skills": ["艺术/手艺（表演）", "射击", "法律", "聆听", "威吓", "心理学", "侦查", "格斗（斗殴）"],
        "description": "执法机关的刑事侦查员"
    },
    "私家侦探": {
        "name": "私家侦探",
        "skills": ["艺术/手艺（摄影）", "乔装", "法律", "图书馆使用", "话术", "心理学", "侦查", "潜行"],
        "description": "游走于灰色地带的调查者"
    },
    "教授": {
        "name": "教授",
        "skills": ["图书馆使用", "其他语言（拉丁语）", "母语", "心理学", "历史", "考古学", "神秘学", "科学（人类学）"],
        "description": "学富五车的学术专家"
    },
    "考古学家": {
        "name": "考古学家",
        "skills": ["考古学", "历史", "图书馆使用", "其他语言（古埃及语）", "侦查", "攀爬", "导航", "科学（地质学）"],
        "description": "探索古代遗迹的冒险学者"
    },
}

# 技能列表（用于兴趣技能随机）
ALL_SKILLS = [
    "会计", "人类学", "估价", "考古学", "艺术/手艺（绘画）", "艺术/手艺（摄影）",
    "魅惑", "攀爬", "信用评级", "乔装", "闪避", "汽车驾驶", "电气维修", "话术",
    "格斗（斗殴）", "射击", "急救", "历史", "其他语言（英语）", "其他语言（拉丁语）",
    "母语", "法律", "图书馆使用", "聆听", "锁匠", "机械维修", "医学", "博物学",
    "导航", "神秘学", "操作重型机械", "说服", "驾驶（汽车）", "精神分析", "心理学",
    "骑术", "科学（生物学）", "科学（化学）", "科学（物理学）", "妙手", "侦查",
    "潜行", "生存（荒野）", "游泳", "投掷", "追踪", "威吓"
]

# 技能点分配规则: 1项70%, 2项60%, 3项50%, 2项40%
SKILL_POINT_DISTRIBUTION = [70, 60, 60, 50, 50, 50, 40, 40]

# 兴趣技能点数
INTEREST_SKILL_POINTS = 20


@dataclass
class PrimaryAttributes:
    """常规属性"""
    STR: int = 0  # 力量
    CON: int = 0  # 体质
    DEX: int = 0  # 敏捷
    SIZ: int = 0  # 体型
    INT: int = 0  # 智力
    POW: int = 0  # 意志
    APP: int = 0  # 外貌
    EDU: int = 0  # 教育

    def to_dict(self) -> Dict[str, int]:
        return {
            "STR": self.STR, "CON": self.CON, "DEX": self.DEX, "SIZ": self.SIZ,
            "INT": self.INT, "POW": self.POW, "APP": self.APP, "EDU": self.EDU
        }
    
    def to_display_list(self) -> List[Dict[str, Any]]:
        """转换为前端展示格式"""
        result = []
        for attr in PRIMARY_ATTRIBUTES:
            value = getattr(self, attr)
            info = PRIMARY_ATTRIBUTE_INFO[attr]
            result.append({
                "key": attr,
                "name": info["name"],
                "value": value,
                "description": info["description"]
            })
        return result


@dataclass
class SecondaryAttributes:
    """次要属性"""
    HP: int = 0       # 生命值
    MP: int = 0       # 魔法值
    SAN: int = 0      # 理智值
    LUCK: int = 0     # 幸运值
    DB: int = 0       # 伤害加值
    Build: int = 0    # 体格
    MOV: int = 8      # 移动速度

    def to_dict(self) -> Dict[str, int]:
        return {
            "HP": self.HP, "MP": self.MP, "SAN": self.SAN, "LUCK": self.LUCK,
            "DB": self.DB, "Build": self.Build, "MOV": self.MOV
        }
    
    def to_display_list(self, primary: PrimaryAttributes) -> List[Dict[str, Any]]:
        """转换为前端展示格式，包含计算说明"""
        return [
            {
                "key": "HP",
                "name": "生命值",
                "value": self.HP,
                "formula": f"(体质{primary.CON} + 体型{primary.SIZ}) ÷ 10 = {self.HP}",
                "description": "调查员能承受的伤害量"
            },
            {
                "key": "MP",
                "name": "魔法值",
                "value": self.MP,
                "formula": f"意志{primary.POW} ÷ 5 = {self.MP}",
                "description": "用于施法或供能。若耗尽，后续消耗将直接从HP中扣除"
            },
            {
                "key": "SAN",
                "name": "理智值",
                "value": self.SAN,
                "formula": f"等于意志值 = {self.SAN}",
                "description": "调查员的心理健康程度"
            },
            {
                "key": "LUCK",
                "name": "幸运值",
                "value": self.LUCK,
                "formula": "3D6 × 5 随机",
                "description": "调查员的运气"
            },
            {
                "key": "DB",
                "name": "伤害加值",
                "value": self.DB,
                "formula": f"力量{primary.STR} + 体型{primary.SIZ} = {primary.STR + primary.SIZ} → DB={self.DB}",
                "description": "近战伤害加成"
            },
            {
                "key": "Build",
                "name": "体格",
                "value": self.Build,
                "formula": f"力量{primary.STR} + 体型{primary.SIZ} = {self.Build}",
                "description": "力量与体型的综合"
            },
            {
                "key": "MOV",
                "name": "移动速度",
                "value": self.MOV,
                "formula": "人类固定为8",
                "description": "行动速度"
            },
        ]


@dataclass
class Profession:
    """职业"""
    name: str
    skills: List[str] = field(default_factory=list)
    skill_points: Dict[str, int] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "skills": self.skills,
            "skillPoints": self.skill_points,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profession":
        """从字典创建 Profession（处理 camelCase -> snake_case）"""
        return cls(
            name=data.get("name", ""),
            skills=data.get("skills", []),
            skill_points=data.get("skillPoints", data.get("skill_points", {})),
            description=data.get("description", "")
        )
    
    def to_display_dict(self) -> Dict[str, Any]:
        """转换为前端展示格式"""
        skill_list = []
        for skill, points in self.skill_points.items():
            skill_list.append({
                "name": skill,
                "value": points,
                "display": f"{skill}: {points}%"
            })
        return {
            "name": self.name,
            "description": self.description,
            "skills": skill_list
        }


class COCGenerator:
    """克苏鲁跑团调查员生成器"""

    def __init__(self, seed: Optional[int] = None):
        """
        初始化生成器
        
        Args:
            seed: 随机种子，用于复现结果
        """
        self.rng = random.Random(seed)
    
    # ==================== 常规属性 ====================
    
    def roll_primary_attributes(self) -> PrimaryAttributes:
        """
        随机分配常规属性
        将8个固定值(40,50,50,50,60,60,70,80)随机分配到8个属性
        
        Returns:
            PrimaryAttributes 对象
        """
        values = PRIMARY_ATTRIBUTE_VALUES.copy()
        self.rng.shuffle(values)
        
        return PrimaryAttributes(
            STR=values[0],
            CON=values[1],
            DEX=values[2],
            SIZ=values[3],
            INT=values[4],
            POW=values[5],
            APP=values[6],
            EDU=values[7]
        )
    
    def swap_attributes(self, attrs: PrimaryAttributes, attr1: str, attr2: str) -> PrimaryAttributes:
        """
        交换两个属性的值
        
        Args:
            attrs: 当前属性
            attr1: 属性1名称
            attr2: 属性2名称
            
        Returns:
            交换后的新 PrimaryAttributes 对象
        """
        if attr1 not in PRIMARY_ATTRIBUTES or attr2 not in PRIMARY_ATTRIBUTES:
            return attrs
        
        new_attrs = PrimaryAttributes(**attrs.to_dict())
        val1 = getattr(new_attrs, attr1)
        val2 = getattr(new_attrs, attr2)
        setattr(new_attrs, attr1, val2)
        setattr(new_attrs, attr2, val1)
        return new_attrs
    
    # ==================== 次要属性 ====================
    
    def calc_secondary_attributes(self, primary: PrimaryAttributes) -> SecondaryAttributes:
        """
        根据常规属性计算次要属性
        
        Rules:
        - HP = (CON + SIZ) ÷ 10 (向下取整)
        - MP = POW ÷ 5 (向下取整)
        - SAN = POW
        - LUCK = 3D6 × 5 (随机)
        - DB: 基于 STR + SIZ 的总值判断
        - Build = STR + SIZ
        - MOV = 8 (人类固定)
        
        Args:
            primary: 常规属性
            
        Returns:
            SecondaryAttributes 对象
        """
        str_siz_total = primary.STR + primary.SIZ
        
        # 计算伤害加值(DB)
        if str_siz_total <= 64:
            db = -2
        elif str_siz_total <= 84:
            db = -1
        elif str_siz_total <= 124:
            db = 0
        elif str_siz_total <= 164:
            db = 1  # 实际应为 1D4，简化为平均值
        else:
            db = 2  # 实际应为 1D6，简化为平均值
        
        # 幸运值: 3D6 × 5
        luck = sum(self.rng.randint(1, 6) for _ in range(3)) * 5
        
        return SecondaryAttributes(
            HP=(primary.CON + primary.SIZ) // 10,
            MP=primary.POW // 5,
            SAN=primary.POW,
            LUCK=luck,
            DB=db,
            Build=str_siz_total,
            MOV=8
        )
    
    # ==================== 职业与技能 ====================
    
    def roll_professions(self, count: int = 3) -> List[Profession]:
        """
        随机生成指定数量的职业及其技能点分配
        
        Args:
            count: 生成职业数量，默认3
            
        Returns:
            Profession 对象列表
        """
        profession_names = list(PROFESSIONS.keys())
        selected = self.rng.sample(profession_names, min(count, len(profession_names)))
        
        result = []
        for name in selected:
            prof_data = PROFESSIONS[name]
            skills = prof_data["skills"].copy()
            
            # 分配技能点: 1项70%, 2项60%, 3项50%, 2项40%
            points = SKILL_POINT_DISTRIBUTION.copy()
            self.rng.shuffle(points)
            
            skill_points = {}
            for i, skill in enumerate(skills[:8]):
                skill_points[skill] = points[i]
            
            result.append(Profession(
                name=name,
                skills=skills,
                skill_points=skill_points,
                description=prof_data["description"]
            ))
        
        return result
    
    def get_profession_by_name(self, name: str) -> Optional[Profession]:
        """
        根据名称获取职业并分配技能点
        
        Args:
            name: 职业名称
            
        Returns:
            Profession 对象，如果找不到返回 None
        """
        if name not in PROFESSIONS:
            return None
        
        prof_data = PROFESSIONS[name]
        skills = prof_data["skills"].copy()
        
        points = SKILL_POINT_DISTRIBUTION.copy()
        self.rng.shuffle(points)
        
        skill_points = {}
        for i, skill in enumerate(skills[:8]):
            skill_points[skill] = points[i]
        
        return Profession(
            name=name,
            skills=skills,
            skill_points=skill_points,
            description=prof_data["description"]
        )
    
    def roll_interest_skills(self, profession_skills: List[str], count: int = 4) -> Dict[str, int]:
        """
        随机生成兴趣技能
        
        Args:
            profession_skills: 已有的职业技能，避免重复
            count: 兴趣技能数量，默认4
            
        Returns:
            兴趣技能字典 {技能名: 点数}
        """
        available = [s for s in ALL_SKILLS if s not in profession_skills]
        selected = self.rng.sample(available, min(count, len(available)))
        
        return {skill: INTEREST_SKILL_POINTS for skill in selected}
    
    # ==================== 人物卡生成 ====================
    
    def generate_investigator_card(
        self,
        primary: PrimaryAttributes,
        secondary: SecondaryAttributes,
        profession: Profession,
        interest_skills: Dict[str, int],
        name: str = "",
        gender: str = "",
        age: int = 0,
        background: str = "",
        equipment: List[str] = None
    ) -> Dict[str, Any]:
        """
        生成完整的调查员人物卡
        
        Args:
            primary: 常规属性
            secondary: 次要属性
            profession: 职业
            interest_skills: 兴趣技能
            name: 姓名
            gender: 性别
            age: 年龄
            background: 背景故事
            equipment: 装备列表
            
        Returns:
            人物卡字典
        """
        # 合并所有技能
        all_skills = {**profession.skill_points, **interest_skills}
        
        return {
            "name": name,
            "gender": gender,
            "age": age,
            "profession": profession.name,
            "professionSkills": profession.skills,
            "interestSkills": list(interest_skills.keys()),
            "primaryAttributes": primary.to_dict(),
            "secondaryAttributes": secondary.to_dict(),
            "skills": all_skills,
            "equipment": equipment or [],
            "background": background,
            # 当前状态（初始值等于最大值）
            "currentHP": secondary.HP,
            "currentMP": secondary.MP,
            "currentSAN": secondary.SAN,
        }
    
    # ==================== 辅助方法 ====================
    
    @staticmethod
    def get_available_professions() -> List[Dict[str, str]]:
        """获取所有可用职业列表"""
        return [
            {"name": name, "description": data["description"]}
            for name, data in PROFESSIONS.items()
        ]
    
    @staticmethod
    def get_attribute_info(attr_key: str) -> Dict[str, str]:
        """获取属性信息"""
        if attr_key in PRIMARY_ATTRIBUTE_INFO:
            return PRIMARY_ATTRIBUTE_INFO[attr_key]
        if attr_key in SECONDARY_ATTRIBUTE_INFO:
            return SECONDARY_ATTRIBUTE_INFO[attr_key]
        return {"name": attr_key, "description": ""}
