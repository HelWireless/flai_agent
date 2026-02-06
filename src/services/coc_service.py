"""
克苏鲁跑团(COC)服务 - 处理跑团游戏的核心业务逻辑
"""
import json
import uuid
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from ..schemas import IWChatRequest, IWChatResponse
from ..custom_logger import custom_logger
from ..models.coc_game_state import COCGameState
from ..models.instance_world import FreakWorldDialogue
from .llm_service import LLMService
from .instance_world_prompts import get_gm_config
from .coc_generator import (
    COCGenerator, PrimaryAttributes, SecondaryAttributes, Profession,
    PRIMARY_ATTRIBUTES, PROFESSIONS
)


# COC step 常量（对应 IWChatRequest.step）
# GM 由用户提前选择（gmId 参数），action=start 直接进入属性分配
class COCStep:
    CHAR_CREATE = "0"         # 已废弃：GM 由用户提前选择
    STEP1_ATTRIBUTES = "1"    # 常规属性分配（action=start 的首个响应）
    STEP2_SECONDARY = "2"     # 次要属性确认
    STEP3_PROFESSION = "3"    # 职业选择
    STEP4_BACKGROUND = "4"    # 背景确认
    STEP5_SUMMARY = "5"       # 人物卡总结
    PLAYING = "6"             # 游戏进行中（返回 markdown）
    ENDED = "7"               # 游戏结束


# =====================================================
# 游戏状态常量
# =====================================================

class GameStatus:
    """游戏状态枚举"""
    GM_SELECT = "gm_select"
    STEP1_ATTRIBUTES = "step1_attributes"
    STEP2_SECONDARY = "step2_secondary"
    STEP3_PROFESSION = "step3_profession"
    STEP4_BACKGROUND = "step4_background"
    STEP5_SUMMARY = "step5_summary"
    PLAYING = "playing"
    ENDED = "ended"


# GM列表（后续从数据库读取）
COC_GMS = {
    "female": [
        {"id": "li", "name": "璃", "traits": "冷静中带着利落感，说话逻辑清晰、不拖沓；气质凝练如淬过的银刃，自带距离感却不冷漠"},
        {"id": "yan", "name": "焰", "traits": "自信飒爽，行事干脆利落；大气温柔，待人有包容感；聪慧机敏"},
        {"id": "dong", "name": "鸫", "traits": "说话元气满满，热情得会主动分享小细节，眼睛像含着光；清纯感体现在语气的无防备"},
        {"id": "ai", "name": "霭", "traits": "神秘深邃，成熟娴静，说话语速偏慢，像裹着一层薄雾；魅惑感体现在低柔的语调"},
        {"id": "su", "name": "苏", "traits": "青春四射，清纯活泼，说话会有点结巴或小声；羞涩时会有一些小动作"},
    ],
    "male": [
        {"id": "zhu", "name": "筑", "traits": "气质沉静，稳重成熟，说话语调平稳；会主动说'有我在''别担心'，传递可靠感"},
        {"id": "huai", "name": "淮", "traits": "潇洒风流，放荡不羁，大气随性，说话带江湖气，像仗剑走天涯的侠客"},
        {"id": "duo", "name": "铎", "traits": "阳光活力，纯情温和，干劲满满，说话像刚晒过太阳，带着暖意"},
    ]
}


class COCService:
    """克苏鲁跑团业务服务"""
    
    # 存档触发密钥
    SAVE_KEY = "73829104碧鹿孽心0109要去坐标BBT进行存档"
    LOAD_KEY = "73829104碧鹿孽心0109要去坐标BBT进行读档"
    
    def __init__(self, llm_service: LLMService, db: Session, config: Dict):
        """
        初始化COC服务
        
        Args:
            llm_service: LLM 服务
            db: 数据库会话
            config: 应用配置
        """
        self.llm = llm_service
        self.db = db
        self.config = config
        self.generator = COCGenerator()
    
    # ==================== 工具方法 ====================
    
    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        return f"coc_{uuid.uuid4().hex[:12]}"
    
    def _get_random_gm(self, gender: str) -> Dict[str, str]:
        """随机选择一个GM"""
        gms = COC_GMS.get(gender, COC_GMS["female"])
        return random.choice(gms)
    
    # ==================== 数据库操作 ====================
    
    def _create_session_db(self, account_id: int, gm_gender: Optional[str] = None, session_id: Optional[str] = None) -> COCGameState:
        """创建新游戏状态
        
        Args:
            account_id: 用户ID
            gm_gender: GM性别
            session_id: 会话ID（可选，不传则自动生成）
        """
        session = COCGameState(
            session_id=session_id or self._generate_session_id(),
            account_id=account_id,
            gm_gender=gm_gender,
            game_status=GameStatus.GM_SELECT,
            del_=0
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        custom_logger.info(f"Created new COC game state: {session.session_id}")
        return session
    
    def _get_session_db(self, session_id: str) -> Optional[COCGameState]:
        """获取游戏状态"""
        return self.db.query(COCGameState).filter(
            and_(
                COCGameState.session_id == session_id,
                COCGameState.del_ == 0
            )
        ).first()
    
    def _update_session_db(self, session: COCGameState):
        """更新游戏状态"""
        self.db.commit()
        self.db.refresh(session)
    
    def _get_dialogue_history(self, session_id: int) -> List[Dict[str, str]]:
        """获取对话历史（从 t_freak_world_dialogue 读取）"""
        dialogues = self.db.query(FreakWorldDialogue).filter(
            and_(
                FreakWorldDialogue.session_id == session_id,
                FreakWorldDialogue.del_ == 0
            )
        ).order_by(FreakWorldDialogue.id.asc()).all()
        
        messages = []
        for d in dialogues:
            messages.extend(d.to_messages())
        return messages
    
    # ==================== 主入口 ====================
    
    async def chat(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        单一入口，根据游戏状态分发到不同的处理器
        
        Args:
            request: 请求数据
                - sessionId: 会话ID（可选，新游戏不传）
                - accountId: 用户ID
                - action: 动作类型 (start, confirm, reroll, select, input, load)
                - message: 玩家输入
                - selection: 选择的选项ID
                - saveData: 存档数据（action=load时需要）
                
        Returns:
            响应数据
        """
        session_id = request.get("sessionId")
        account_id = request.get("accountId")
        gm_id = request.get("gmId")  # GM 由用户选择
        action = request.get("action", "input")
        message = request.get("message", "")
        selection = request.get("selection")
        save_data = request.get("saveData")
        
        # 处理读档请求
        if action == "load" and save_data:
            return await self.load_game(account_id, save_data)
        
        # 检查读档密钥
        if message == self.LOAD_KEY and save_data:
            return await self.load_game(account_id, save_data)
        
        # 获取或创建会话
        if action == "start":
            # action=start 表示新游戏
            if session_id:
                session = self._get_session_db(session_id)
                if not session:
                    session = self._create_session_db(account_id, session_id=session_id)
                # 如果 session 已存在但要重新开始，重置状态
                else:
                    session.investigator_card = None
                    session.temp_data = None
            else:
                session = self._create_session_db(account_id)
            
            # GM 已由用户选择，直接进入属性分配阶段
            if gm_id and gm_id != "0":
                session.gm_id = gm_id
                session.game_status = GameStatus.STEP1_ATTRIBUTES
                
                # 获取 GM 配置
                gm_config = get_gm_config(gm_id)
                gm_name = gm_config.get("name", "GM")
                gm_traits = gm_config.get("traits", "")
                
                # 初始化属性
                self.generator = COCGenerator()
                primary = self.generator.roll_primary_attributes()
                session.set_temp_data({
                    "primary_attributes": primary.to_dict(),
                    "gm_name": gm_name,
                    "gm_traits": gm_traits
                })
                self._update_session_db(session)
                
                # 返回属性分配响应
                intro = f"（{gm_name}微微颔首）\n\n"
                intro += f"你好，我是{gm_name}，将作为你的Game Master陪伴你完成这次《克苏鲁的呼唤》冒险。\n\n"
                intro += "接下来，让我们开始创建你的调查员角色。\n\n"
                intro += "**第一步：常规属性分配**\n\n"
                intro += "以下是你随机分配的8个常规属性值："
                
                return self._build_response(
                    session,
                    content=intro,
                    structured_data={
                        "title": "第一步：常规属性分配结果",
                        "attributes": primary.to_display_list()
                    },
                    selections=[
                        {"id": "confirm", "text": "确认属性"},
                        {"id": "reroll", "text": "重新随机"}
                    ]
                )
            else:
                # 没有 gm_id，进入 GM 选择阶段（兼容旧逻辑）
                session.game_status = GameStatus.GM_SELECT
                self._update_session_db(session)
        elif session_id:
            session = self._get_session_db(session_id)
            if not session:
                # session_id 由 Java 层创建但本地无记录，创建新会话
                custom_logger.info(f"Session {session_id} not found, creating new session")
                session = self._create_session_db(account_id, session_id=session_id)
        else:
            # 无 session_id，创建新会话
            session = self._create_session_db(account_id)
        
        # 状态处理器映射
        handlers = {
            GameStatus.GM_SELECT: self._handle_gm_select,
            GameStatus.STEP1_ATTRIBUTES: self._handle_step1_attributes,
            GameStatus.STEP2_SECONDARY: self._handle_step2_secondary,
            GameStatus.STEP3_PROFESSION: self._handle_step3_profession,
            GameStatus.STEP4_BACKGROUND: self._handle_step4_background,
            GameStatus.STEP5_SUMMARY: self._handle_step5_summary,
            GameStatus.PLAYING: self._handle_playing,
            GameStatus.ENDED: self._handle_ended,
        }
        
        handler = handlers.get(session.game_status, self._handle_error)
        return await handler(session, action, message, selection)
    
    # ==================== 阶段处理器 ====================
    
    async def _handle_gm_select(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理GM选择阶段"""
        
        if action == "start" or not selection:
            # 初始状态，显示性别选择
            return self._build_response(
                session,
                content="欢迎来到《克苏鲁的呼唤》跑团游戏！\n\n请选择你希望的引导者（Game Master）性别：",
                structured_data={
                    "title": "选择GM性别",
                    "description": "GM将陪伴你完成整个冒险旅程"
                },
                selections=[
                    {"id": "female", "text": "女性GM"},
                    {"id": "male", "text": "男性GM"}
                ]
            )
        
        # 玩家选择了性别
        gender = selection if selection in ["male", "female"] else "female"
        gm = self._get_random_gm(gender)
        
        session.gm_gender = gender
        session.gm_id = gm["id"]
        session.game_status = GameStatus.STEP1_ATTRIBUTES
        
        # 随机生成初始属性
        self.generator = COCGenerator()  # 新的随机实例
        primary = self.generator.roll_primary_attributes()
        session.set_temp_data({
            "primary_attributes": primary.to_dict(),
            "gm_name": gm["name"],
            "gm_traits": gm["traits"]
        })
        self._update_session_db(session)
        
        # 构建GM自我介绍
        intro = f"（{gm['name']}微微颔首，{gm['traits'][:20]}...）\n\n"
        intro += f"你好，我是{gm['name']}，将作为你的Game Master陪伴你完成这次《克苏鲁的呼唤》冒险。\n\n"
        intro += "接下来，让我们开始创建你的调查员角色。\n\n"
        intro += "**第一步：常规属性分配**\n\n"
        intro += "以下是你随机分配的8个常规属性值："
        
        return self._build_response(
            session,
            content=intro,
            structured_data={
                "title": "第一步：常规属性分配结果",
                "attributes": primary.to_display_list()
            },
            selections=[
                {"id": "confirm", "text": "确认属性"},
                {"id": "reroll", "text": "重新随机"}
            ]
        )
    
    async def _handle_step1_attributes(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理常规属性分配阶段"""
        
        temp = session.get_temp_data()
        primary_dict = temp.get("primary_attributes", {})
        gm_name = temp.get("gm_name", "GM")
        
        if selection == "reroll" or action == "reroll":
            # 重新随机
            self.generator = COCGenerator()
            primary = self.generator.roll_primary_attributes()
            temp["primary_attributes"] = primary.to_dict()
            session.set_temp_data(temp)
            self._update_session_db(session)
            
            content = f"（{gm_name}点点头）好的，为你重新分配属性。\n\n**新的属性分配：**"
            return self._build_response(
                session,
                content=content,
                structured_data={
                    "title": "第一步：常规属性分配结果（重新随机）",
                    "attributes": primary.to_display_list()
                },
                selections=[
                    {"id": "confirm", "text": "确认属性"},
                    {"id": "reroll", "text": "重新随机"}
                ]
            )
        
        if selection == "confirm" or action == "confirm":
            # 确认属性，进入下一步
            session.game_status = GameStatus.STEP2_SECONDARY
            
            # 计算次要属性
            primary = PrimaryAttributes(**primary_dict)
            secondary = self.generator.calc_secondary_attributes(primary)
            temp["secondary_attributes"] = secondary.to_dict()
            session.set_temp_data(temp)
            self._update_session_db(session)
            
            content = f"（{gm_name}记录下你的属性）\n\n"
            content += "很好，属性已确认。现在根据你的常规属性，计算出以下次要属性：\n\n"
            content += "**第二步：次要属性计算**"
            
            return self._build_response(
                session,
                content=content,
                structured_data={
                    "title": "第二步：次要属性计算",
                    "attributes": secondary.to_display_list(primary)
                },
                selections=[
                    {"id": "confirm", "text": "确认次要属性"},
                    {"id": "back", "text": "返回修改常规属性"}
                ]
            )
        
        # 默认显示当前状态
        primary = PrimaryAttributes(**primary_dict)
        return self._build_response(
            session,
            content="请确认或重新随机你的常规属性：",
            structured_data={
                "title": "第一步：常规属性分配结果",
                "attributes": primary.to_display_list()
            },
            selections=[
                {"id": "confirm", "text": "确认属性"},
                {"id": "reroll", "text": "重新随机"}
            ]
        )
    
    async def _handle_step2_secondary(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理次要属性确认阶段"""
        
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        
        if selection == "back":
            # 返回修改常规属性
            session.game_status = GameStatus.STEP1_ATTRIBUTES
            self._update_session_db(session)
            
            primary = PrimaryAttributes(**temp.get("primary_attributes", {}))
            return self._build_response(
                session,
                content=f"（{gm_name}）好的，让我们重新调整常规属性。",
                structured_data={
                    "title": "第一步：常规属性分配结果",
                    "attributes": primary.to_display_list()
                },
                selections=[
                    {"id": "confirm", "text": "确认属性"},
                    {"id": "reroll", "text": "重新随机"}
                ]
            )
        
        if selection == "confirm" or action == "confirm":
            # 确认次要属性，进入职业选择
            session.game_status = GameStatus.STEP3_PROFESSION
            
            # 随机生成3个职业
            professions = self.generator.roll_professions(3)
            temp["professions"] = [p.to_dict() for p in professions]
            session.set_temp_data(temp)
            self._update_session_db(session)
            
            content = f"（{gm_name}满意地点头）\n\n"
            content += "次要属性已确定。现在让我们为你的调查员选择一个职业。\n\n"
            content += "**第三步：职业与技能生成**\n\n"
            content += "以下是随机生成的3个职业供你选择："
            
            # 构建职业选项
            profession_data = []
            selections = []
            for i, p in enumerate(professions):
                profession_data.append(p.to_display_dict())
                selections.append({"id": f"prof_{i}", "text": f"选择 {p.name}"})
            
            selections.append({"id": "reroll", "text": "重新随机3个职业"})
            
            return self._build_response(
                session,
                content=content,
                structured_data={
                    "title": "第三步：职业与技能生成",
                    "professions": profession_data
                },
                selections=selections
            )
        
        # 默认显示当前次要属性
        primary = PrimaryAttributes(**temp.get("primary_attributes", {}))
        secondary = SecondaryAttributes(**temp.get("secondary_attributes", {}))
        return self._build_response(
            session,
            content="请确认次要属性：",
            structured_data={
                "title": "第二步：次要属性计算",
                "attributes": secondary.to_display_list(primary)
            },
            selections=[
                {"id": "confirm", "text": "确认次要属性"},
                {"id": "back", "text": "返回修改常规属性"}
            ]
        )
    
    async def _handle_step3_profession(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理职业选择阶段"""
        
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        professions_data = temp.get("professions", [])
        
        if selection == "reroll":
            # 重新随机职业
            professions = self.generator.roll_professions(3)
            temp["professions"] = [p.to_dict() for p in professions]
            session.set_temp_data(temp)
            self._update_session_db(session)
            
            profession_data = [p.to_display_dict() for p in professions]
            selections = []
            for i, p in enumerate(professions):
                selections.append({"id": f"prof_{i}", "text": f"选择 {p.name}"})
            selections.append({"id": "reroll", "text": "重新随机3个职业"})
            
            return self._build_response(
                session,
                content=f"（{gm_name}）好的，为你重新生成职业选项：",
                structured_data={
                    "title": "第三步：职业与技能生成（重新随机）",
                    "professions": profession_data
                },
                selections=selections
            )
        
        if selection and selection.startswith("prof_"):
            # 选择了某个职业
            try:
                prof_idx = int(selection.split("_")[1])
                selected_profession = professions_data[prof_idx]
            except (ValueError, IndexError):
                return self._error_response("无效的职业选择")
            
            # 生成兴趣技能
            interest_skills = self.generator.roll_interest_skills(
                selected_profession.get("skills", [])
            )
            
            temp["selected_profession"] = selected_profession
            temp["interest_skills"] = interest_skills
            session.game_status = GameStatus.STEP4_BACKGROUND
            session.set_temp_data(temp)
            self._update_session_db(session)
            
            content = f"（{gm_name}记录下你的选择）\n\n"
            content += f"你选择了 **{selected_profession['name']}** 作为职业。\n\n"
            content += "**兴趣技能**（每项20%）：\n"
            for skill in interest_skills.keys():
                content += f"- {skill}\n"
            content += "\n**第四步：角色背景与装备**\n\n"
            content += "接下来，我将为你的调查员生成背景故事和初始装备。请稍候..."
            
            # 调用LLM生成背景故事
            background_result = await self._generate_background(
                session, selected_profession, temp
            )
            
            return background_result
        
        # 默认显示职业选项
        profession_data = []
        selections = []
        for i, p_data in enumerate(professions_data):
            profession_data.append({
                "name": p_data.get("name"),
                "description": p_data.get("description"),
                "skills": [
                    {"name": k, "value": v, "display": f"{k}: {v}%"}
                    for k, v in p_data.get("skillPoints", {}).items()
                ]
            })
            selections.append({"id": f"prof_{i}", "text": f"选择 {p_data.get('name')}"})
        selections.append({"id": "reroll", "text": "重新随机3个职业"})
        
        return self._build_response(
            session,
            content="请选择一个职业：",
            structured_data={
                "title": "第三步：职业与技能生成",
                "professions": profession_data
            },
            selections=selections
        )
    
    async def _generate_background(
        self, 
        session: COCGameState, 
        profession: Dict, 
        temp: Dict
    ) -> Dict[str, Any]:
        """调用LLM生成角色背景和装备"""
        
        gm_name = temp.get("gm_name", "GM")
        primary = temp.get("primary_attributes", {})
        secondary = temp.get("secondary_attributes", {})
        
        # 构建prompt
        prompt = f"""你是一个克苏鲁跑团游戏的角色生成器。请为以下调查员生成背景故事和装备。

职业：{profession['name']}
职业技能：{', '.join(profession.get('skills', []))}

常规属性：
- 力量(STR): {primary.get('STR')}
- 体质(CON): {primary.get('CON')}
- 敏捷(DEX): {primary.get('DEX')}
- 体型(SIZ): {primary.get('SIZ')}
- 智力(INT): {primary.get('INT')}
- 意志(POW): {primary.get('POW')}
- 外貌(APP): {primary.get('APP')}
- 教育(EDU): {primary.get('EDU')}

请生成：
1. 姓名（中文名）
2. 性别
3. 年龄（25-45岁之间）
4. 背景故事（100-150字，包含成长地点、家庭情况、个性特点）
5. 装备列表（不超过5件，与职业相关）

请以JSON格式返回：
{{
  "name": "姓名",
  "gender": "男/女",
  "age": 数字,
  "background": "背景故事",
  "equipment": ["装备1", "装备2", ...]
}}
只返回JSON，不要其他内容。"""

        try:
            response = await self.llm.chat_completion_async([
                {"role": "user", "content": prompt}
            ])
            
            # 解析响应
            content = response.get("content", "")
            # 尝试提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            background_data = json.loads(content.strip())
            
        except Exception as e:
            custom_logger.error(f"Failed to generate background: {e}")
            # 使用默认值
            background_data = {
                "name": "调查员",
                "gender": "男",
                "age": 30,
                "background": f"一名经验丰富的{profession['name']}，性格沉稳，善于观察。",
                "equipment": ["手电筒", "笔记本", "钢笔"]
            }
        
        temp["background_data"] = background_data
        session.set_temp_data(temp)
        self._update_session_db(session)
        
        content = f"（{gm_name}为你构思角色背景）\n\n"
        content += "**角色背景生成完成**\n\n"
        content += f"**姓名**：{background_data.get('name')}\n"
        content += f"**性别**：{background_data.get('gender')}\n"
        content += f"**年龄**：{background_data.get('age')}岁\n\n"
        content += f"**背景故事**：\n{background_data.get('background')}\n\n"
        content += "**初始装备**：\n"
        for item in background_data.get("equipment", []):
            content += f"- {item}\n"
        
        return self._build_response(
            session,
            content=content,
            structured_data={
                "title": "第四步：角色背景与装备",
                "character": background_data
            },
            selections=[
                {"id": "confirm", "text": "确认角色信息"},
                {"id": "regenerate", "text": "重新生成背景"}
            ]
        )
    
    async def _handle_step4_background(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理角色背景确认阶段"""
        
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        background_data = temp.get("background_data", {})
        profession = temp.get("selected_profession", {})
        
        if selection == "regenerate":
            # 重新生成背景
            return await self._generate_background(session, profession, temp)
        
        if selection == "confirm" or action == "confirm":
            # 确认背景，生成最终人物卡
            session.game_status = GameStatus.STEP5_SUMMARY
            
            # 组装完整人物卡
            primary = PrimaryAttributes(**temp.get("primary_attributes", {}))
            secondary = SecondaryAttributes(**temp.get("secondary_attributes", {}))
            interest_skills = temp.get("interest_skills", {})
            
            investigator_card = self.generator.generate_investigator_card(
                primary=primary,
                secondary=secondary,
                profession=Profession(**profession),
                interest_skills=interest_skills,
                name=background_data.get("name", "调查员"),
                gender=background_data.get("gender", "男"),
                age=background_data.get("age", 30),
                background=background_data.get("background", ""),
                equipment=background_data.get("equipment", [])
            )
            
            session.investigator_card = investigator_card
            self._update_session_db(session)
            
            content = f"（{gm_name}整理好所有资料）\n\n"
            content += "**第五步：调查员信息总结**\n\n"
            content += "你的调查员人物卡已生成完毕！\n\n"
            content += f"**【{investigator_card['name']}】**\n"
            content += f"职业：{investigator_card['profession']} | "
            content += f"性别：{investigator_card['gender']} | "
            content += f"年龄：{investigator_card['age']}岁\n\n"
            content += "**常规属性**：\n"
            for attr, value in investigator_card["primaryAttributes"].items():
                info = self.generator.get_attribute_info(attr)
                content += f"- {info['name']}({attr}): {value}\n"
            content += "\n**次要属性**：\n"
            content += f"- 生命值(HP): {investigator_card['secondaryAttributes']['HP']}\n"
            content += f"- 魔法值(MP): {investigator_card['secondaryAttributes']['MP']}\n"
            content += f"- 理智值(SAN): {investigator_card['secondaryAttributes']['SAN']}\n"
            content += f"- 幸运值(LUCK): {investigator_card['secondaryAttributes']['LUCK']}\n"
            
            return self._build_response(
                session,
                content=content,
                structured_data={
                    "title": "第五步：调查员信息总结",
                    "investigatorCard": investigator_card
                },
                selections=[
                    {"id": "start_game", "text": "开始游戏"},
                    {"id": "back", "text": "返回修改"}
                ]
            )
        
        # 默认显示当前背景
        content = "请确认角色信息：\n\n"
        content += f"**姓名**：{background_data.get('name')}\n"
        content += f"**性别**：{background_data.get('gender')}\n"
        content += f"**年龄**：{background_data.get('age')}岁\n\n"
        content += f"**背景故事**：\n{background_data.get('background')}\n\n"
        content += "**初始装备**：\n"
        for item in background_data.get("equipment", []):
            content += f"- {item}\n"
        
        return self._build_response(
            session,
            content=content,
            structured_data={
                "title": "第四步：角色背景与装备",
                "character": background_data
            },
            selections=[
                {"id": "confirm", "text": "确认角色信息"},
                {"id": "regenerate", "text": "重新生成背景"}
            ]
        )
    
    async def _handle_step5_summary(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理人物卡总结阶段"""
        
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        
        if selection == "back":
            # 返回修改背景
            session.game_status = GameStatus.STEP4_BACKGROUND
            self._update_session_db(session)
            return await self._handle_step4_background(session, "", "", None)
        
        if selection == "start_game" or action == "start_game":
            # 开始游戏
            session.game_status = GameStatus.PLAYING
            session.turn_number = 1
            session.round_number = 1
            self._update_session_db(session)
            
            investigator = session.investigator_card or {}
            
            content = f"（{gm_name}的眼中闪过一丝期待）\n\n"
            content += f"**【01轮 / 01回合】**\n\n"
            content += "调查员创建完成，游戏正式开始！\n\n"
            content += "人类从未真正掌控宇宙——那些怪异的异星生物、神祗般的存在，正以冷漠的目光注视着这个世界。\n\n"
            content += f"作为{investigator.get('profession', '调查员')}的你，将踏入被遗忘的角落，揭开藏在迷雾后的谜团...\n\n"
            content += f"❤ 生命 {investigator.get('currentHP', 0)}   "
            content += f"💎 魔法 {investigator.get('currentMP', 0)}   "
            content += f"🧠 理智 {investigator.get('currentSAN', 0)}\n\n"
            content += "请输入你的行动或对话："
            
            return self._build_response(
                session,
                content=content,
                structured_data={
                    "title": "游戏开始",
                    "turn": session.turn_number,
                    "round": session.round_number,
                    "status": {
                        "HP": investigator.get("currentHP"),
                        "MP": investigator.get("currentMP"),
                        "SAN": investigator.get("currentSAN")
                    }
                },
                selections=[]  # 自由输入
            )
        
        # 显示人物卡
        investigator = session.investigator_card or {}
        return self._build_response(
            session,
            content="人物卡已生成，是否开始游戏？",
            structured_data={
                "title": "第五步：调查员信息总结",
                "investigatorCard": investigator
            },
            selections=[
                {"id": "start_game", "text": "开始游戏"},
                {"id": "back", "text": "返回修改"}
            ]
        )
    
    async def _handle_playing(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理正常游戏阶段"""
        
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        investigator = session.investigator_card or {}
        
        # 检查存档密钥
        if message == self.SAVE_KEY:
            return await self._handle_save(session)
        
        # 增加轮数
        session.turn_number += 1
        
        # 构建系统prompt
        system_prompt = self._build_game_system_prompt(session, investigator, temp)
        
        # 获取对话历史
        history = self._get_dialogue_history(session.id) if session.id else []
        
        # 构建消息
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-20:])  # 最近20条
        messages.append({"role": "user", "content": message})
        
        try:
            response = await self.llm.chat_completion_async(messages)
            ai_content = response.get("content", "")
        except Exception as e:
            custom_logger.error(f"LLM call failed: {e}")
            ai_content = f"（{gm_name}皱眉）抱歉，系统暂时无法响应，请稍后再试。"
        
        self._update_session_db(session)
        
        # 构建状态显示
        status_line = f"❤ 生命 {investigator.get('currentHP', '?')}   "
        status_line += f"💎 魔法 {investigator.get('currentMP', '?')}   "
        status_line += f"🧠 理智 {investigator.get('currentSAN', '?')}"
        
        content = f"**【{session.turn_number:02d}轮 / {session.round_number:02d}回合】**\n\n"
        content += ai_content
        content += f"\n\n{status_line}"
        
        return self._build_response(
            session,
            content=content,
            structured_data={
                "turn": session.turn_number,
                "round": session.round_number,
                "status": {
                    "HP": investigator.get("currentHP"),
                    "MP": investigator.get("currentMP"),
                    "SAN": investigator.get("currentSAN")
                }
            },
            selections=[]
        )
    
    def _build_game_system_prompt(
        self, 
        session: COCGameState, 
        investigator: Dict, 
        temp: Dict
    ) -> str:
        """构建游戏阶段的系统prompt"""
        
        gm_name = temp.get("gm_name", "GM")
        gm_traits = temp.get("gm_traits", "")
        
        prompt = f"""你是克苏鲁跑团游戏的Game Master，扮演名为"{gm_name}"的电子精灵。
你的性格特质：{gm_traits}

【调查员信息】
姓名：{investigator.get('name')}
职业：{investigator.get('profession')}
背景：{investigator.get('background')}

【当前状态】
- 生命值(HP): {investigator.get('currentHP')}/{investigator.get('secondaryAttributes', {}).get('HP')}
- 魔法值(MP): {investigator.get('currentMP')}/{investigator.get('secondaryAttributes', {}).get('MP')}
- 理智值(SAN): {investigator.get('currentSAN')}/{investigator.get('secondaryAttributes', {}).get('SAN')}

【技能】
{json.dumps(investigator.get('skills', {}), ensure_ascii=False, indent=2)}

【装备】
{', '.join(investigator.get('equipment', []))}

【游戏规则】
1. 每轮生成300-500字
2. 需要进行技能检定时，你来掷骰(1-100)，结果≤技能值为成功
3. 遭遇恐怖事物时进行理智检定，失败扣除理智值
4. 用"()"描写GM的动作神态，体现你的人设
5. 每轮结束给出2-3个行动选项供玩家选择

当前轮数：{session.turn_number}
当前回合：{session.round_number}
"""
        return prompt
    
    async def _handle_save(self, session: COCGameState) -> Dict[str, Any]:
        """处理存档"""
        save_number = session.increment_save_count()
        self._update_session_db(session)
        
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        investigator = session.investigator_card or {}
        
        # 生成完整存档数据
        save_data = self._generate_save_data(session)
        
        content = f"（{gm_name}点点头）\n\n"
        content += f"**【存档 {save_number:03d}】**\n\n"
        content += f"调查员：{investigator.get('name')}\n"
        content += f"职业：{investigator.get('profession')}\n"
        content += f"当前轮数：{session.turn_number} / 回合：{session.round_number}\n"
        content += f"状态：HP {investigator.get('currentHP')} / MP {investigator.get('currentMP')} / SAN {investigator.get('currentSAN')}\n\n"
        content += "存档已保存。"
        
        return self._build_response(
            session,
            content=content,
            structured_data={
                "saveNumber": save_number,
                "saveData": save_data,
                "investigator": investigator,
                "turn": session.turn_number,
                "round": session.round_number
            },
            selections=[]
        )
    
    def _generate_save_data(self, session: COCGameState) -> Dict[str, Any]:
        """生成完整存档数据（按04-总结存档模板格式）"""
        temp = session.get_temp_data()
        investigator = session.investigator_card or {}
        
        return {
            "saveNumber": session.save_count,
            "gmId": session.gm_id,
            "gmName": temp.get("gm_name"),
            "gmGender": session.gm_gender,
            "investigator": {
                "name": investigator.get("name"),
                "gender": investigator.get("gender"),
                "age": investigator.get("age"),
                "profession": investigator.get("profession"),
                "primaryAttributes": investigator.get("primaryAttributes"),
                "secondaryAttributes": investigator.get("secondaryAttributes"),
                "skills": investigator.get("skills"),
                "equipment": investigator.get("equipment"),
                "background": investigator.get("background"),
                "currentHP": investigator.get("currentHP"),
                "currentMP": investigator.get("currentMP"),
                "currentSAN": investigator.get("currentSAN"),
            },
            "gameProgress": {
                "roundNumber": session.round_number,
                "turnNumber": session.turn_number,
                "gameStatus": session.game_status,
            },
            "tempData": temp,
            "savedAt": datetime.now().isoformat()
        }
    
    async def load_game(self, account_id: int, save_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从存档数据加载游戏
        
        Args:
            account_id: 用户ID
            save_data: 存档数据
            
        Returns:
            响应数据
        """
        # 创建新会话
        session = self._create_session_db(account_id)
        
        # 恢复GM信息
        session.gm_id = save_data.get("gmId")
        session.gm_gender = save_data.get("gmGender")
        
        # 恢复调查员人物卡
        investigator_data = save_data.get("investigator", {})
        session.investigator_card = {
            "name": investigator_data.get("name"),
            "gender": investigator_data.get("gender"),
            "age": investigator_data.get("age"),
            "profession": investigator_data.get("profession"),
            "primaryAttributes": investigator_data.get("primaryAttributes"),
            "secondaryAttributes": investigator_data.get("secondaryAttributes"),
            "skills": investigator_data.get("skills"),
            "equipment": investigator_data.get("equipment"),
            "background": investigator_data.get("background"),
            "currentHP": investigator_data.get("currentHP"),
            "currentMP": investigator_data.get("currentMP"),
            "currentSAN": investigator_data.get("currentSAN"),
        }
        
        # 恢复游戏进度
        progress = save_data.get("gameProgress", {})
        session.round_number = progress.get("roundNumber", 1)
        session.turn_number = progress.get("turnNumber", 0)
        session.game_status = progress.get("gameStatus", GameStatus.PLAYING)
        session.save_count = save_data.get("saveNumber", 0)
        
        # 恢复临时数据
        temp_data = save_data.get("tempData", {})
        temp_data["gm_name"] = save_data.get("gmName")
        session.set_temp_data(temp_data)
        
        self._update_session_db(session)
        
        investigator = session.investigator_card
        gm_name = temp_data.get("gm_name", "GM")
        
        content = f"（{gm_name}翻开记录本）\n\n"
        content += f"**【读档成功 - 存档 {session.save_count:03d}】**\n\n"
        content += f"欢迎回来，{investigator.get('name')}。\n\n"
        content += f"**【{session.turn_number:02d}轮 / {session.round_number:02d}回合】**\n\n"
        content += f"❤ 生命 {investigator.get('currentHP')}   "
        content += f"💎 魔法 {investigator.get('currentMP')}   "
        content += f"🧠 理智 {investigator.get('currentSAN')}\n\n"
        content += "距离100轮的死线还剩余 " + str(100 - session.turn_number) + " 轮。\n\n"
        content += "请继续你的冒险："
        
        return self._build_response(
            session,
            content=content,
            structured_data={
                "loaded": True,
                "saveNumber": session.save_count,
                "turn": session.turn_number,
                "round": session.round_number,
                "status": {
                    "HP": investigator.get("currentHP"),
                    "MP": investigator.get("currentMP"),
                    "SAN": investigator.get("currentSAN")
                }
            },
            selections=[]
        )
    
    async def _handle_ended(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理游戏结束状态"""
        return self._build_response(
            session,
            content="游戏已结束。",
            structured_data={"ended": True},
            selections=[
                {"id": "new_game", "text": "开始新游戏"}
            ]
        )
    
    async def _handle_error(
        self, 
        session: COCGameState, 
        action: str, 
        message: str, 
        selection: Optional[str]
    ) -> Dict[str, Any]:
        """处理未知状态"""
        return self._error_response(f"未知的游戏状态: {session.game_status}")
    
    # ==================== 响应构建 ====================
    
    def _build_response(
        self,
        session: COCGameState,
        content: str,
        structured_data: Dict[str, Any] = None,
        selections: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """构建标准响应"""
        return {
            "sessionId": session.session_id,
            "gameStatus": session.game_status,
            "content": content,
            "structuredData": structured_data or {},
            "selections": selections or [],
            "investigatorCard": session.investigator_card,
            "turn": session.turn_number,
            "round": session.round_number
        }
    
    def _error_response(self, message: str) -> Dict[str, Any]:
        """构建错误响应"""
        return {
            "sessionId": "",
            "gameStatus": "error",
            "content": message,
            "structuredData": {"error": True},
            "selections": [],
            "investigatorCard": None,
            "turn": 0,
            "round": 0
        }
    
    # ==================== 新接口（统一格式）====================
    
    def _game_status_to_step(self, game_status: str) -> str:
        """将内部 game_status 转换为 step"""
        mapping = {
            GameStatus.GM_SELECT: COCStep.CHAR_CREATE,  # GM选择阶段 → 角色创建（GM由后端分配）
            GameStatus.STEP1_ATTRIBUTES: COCStep.STEP1_ATTRIBUTES,
            GameStatus.STEP2_SECONDARY: COCStep.STEP2_SECONDARY,
            GameStatus.STEP3_PROFESSION: COCStep.STEP3_PROFESSION,
            GameStatus.STEP4_BACKGROUND: COCStep.STEP4_BACKGROUND,
            GameStatus.STEP5_SUMMARY: COCStep.STEP5_SUMMARY,
            GameStatus.PLAYING: COCStep.PLAYING,
            GameStatus.ENDED: COCStep.ENDED,
        }
        return mapping.get(game_status, COCStep.CHAR_CREATE)
    
    def _convert_to_iw_response(self, old_response: Dict[str, Any], gm_id: str = "0") -> IWChatResponse:
        """
        将旧格式响应转换为 IWChatResponse
        
        - 选择阶段（step 0-5）：content 为 JSON 结构化数据
        - playing 阶段（step 6）：content 为 markdown 纯文本
        """
        text_content = old_response.get("content", "")
        structured_data = old_response.get("structuredData", {})
        selections = old_response.get("selections", [])
        game_status = old_response.get("gameStatus", "")
        
        # playing 阶段返回 markdown 纯文本
        if game_status == GameStatus.PLAYING:
            content = text_content
        else:
            # 选择阶段返回 JSON 结构化数据
            content = {
                "title": structured_data.get("title", ""),
                "description": text_content,
                "selections": selections
            }
            # 添加属性数据
            if "attributes" in structured_data:
                content["attributes"] = structured_data["attributes"]
            # 添加职业数据
            if "professions" in structured_data:
                content["professions"] = structured_data["professions"]
            # 添加人物卡数据
            if "investigatorCard" in structured_data:
                content["investigatorCard"] = structured_data["investigatorCard"]
            # 添加角色数据
            if "character" in structured_data:
                content["character"] = structured_data["character"]
        
        return IWChatResponse(
            session_id=old_response.get("sessionId") or "",
            gm_id=gm_id,
            step=self._game_status_to_step(game_status),
            content=content,
            complete=game_status == GameStatus.ENDED,
            save_id=None,
            ext_data={
                "investigatorCard": old_response.get("investigatorCard"),
                "turn": old_response.get("turn", 0),
                "round": old_response.get("round", 0)
            }
        )
    
    def _iw_request_to_old_format(self, request: IWChatRequest) -> Dict[str, Any]:
        """将 IWChatRequest 转换为旧格式请求"""
        ext_param = request.ext_param or {}
        return {
            "sessionId": request.session_id if request.session_id else None,
            "accountId": int(request.user_id),
            "gmId": request.gm_id,  # 传递 GM ID
            "action": ext_param.get("action", "input"),
            "message": request.message,
            "selection": ext_param.get("selection"),
            "saveData": ext_param.get("save_data") if request.save_id else None
        }
    
    async def process_request(self, request: IWChatRequest) -> IWChatResponse:
        """
        处理请求（入口方法 - 同步模式，使用新的统一格式）
        
        Args:
            request: IWChatRequest 请求
        
        Returns:
            IWChatResponse 响应
        """
        custom_logger.info(
            f"Processing COC request (new format): user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, step={request.step}"
        )
        
        try:
            # 转换为旧格式并调用原有逻辑
            old_request = self._iw_request_to_old_format(request)
            old_response = await self.chat(old_request)
            
            # 转换响应为新格式
            return self._convert_to_iw_response(old_response, request.gm_id or "0")
            
        except Exception as e:
            custom_logger.error(f"Error processing COC request: {e}")
            self.db.rollback()
            return IWChatResponse(
                session_id=request.session_id or "",
                gm_id=request.gm_id or "0",
                step=request.step or COCStep.GM_SELECT,
                content=f"处理请求时发生错误：{str(e)}",
                complete=True
            )
    
    async def stream_chat(
        self,
        request: IWChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式对话（SSE 模式）
        
        COC 游戏逻辑复杂，暂不支持真正的流式输出，
        直接返回完整结果
        
        Args:
            request: 请求
        
        Yields:
            SSE 事件数据
        """
        custom_logger.info(
            f"Stream COC request: user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, step={request.step}"
        )
        
        try:
            # 调用同步处理
            response = await self.process_request(request)
            
            content = response.content
            
            # 选择阶段 content 是 dict，直接发送完整结果
            # playing 阶段 content 是 string，模拟流式发送
            if isinstance(content, str):
                # 将内容作为 delta 事件发送（模拟流式）
                chunk_size = 50  # 每次发送的字符数
                for i in range(0, len(content), chunk_size):
                    yield {
                        "type": "delta",
                        "content": content[i:i+chunk_size]
                    }
            
            # 发送完成事件
            yield {
                "type": "done",
                "complete": True,
                "result": {
                    "sessionId": response.session_id,
                    "gmId": response.gm_id,
                    "step": response.step,
                    "content": response.content,
                    "complete": response.complete,
                    "saveId": response.save_id,
                    "extData": response.ext_data
                }
            }
            
        except Exception as e:
            custom_logger.error(f"Error in COC stream_chat: {e}")
            self.db.rollback()
            yield {
                "type": "error",
                "complete": True,
                "message": str(e)
            }
