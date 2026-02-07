"""
克苏鲁跑团(COC)服务 - 处理跑团游戏的核心业务逻辑

游戏流程（一来一回，请求带 step，响应不返回 step）：

                     ┌─重roll─┐       ┌─重roll─┐
                     │        │       │        │
    step=0 → step=1 → step=2 → step=3 → step=4 → step=5 → 持续对话
    背景      属性      次级属性   职业      人物卡     游戏开始
    (md)     (JSON)    (JSON)   (JSON)    (JSON)     (md)

- 进入下一个 step = 确认上一步
- 重roll = 再次发送当前 step
- 存档/读档通过 extParam.action 控制，不需要 step
- 响应不返回 step 字段
"""
import json
import uuid
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import and_, desc

from ..schemas import IWChatRequest
from ..custom_logger import custom_logger
from ..models.coc_game_state import COCGameState
from ..models.coc_save_slot import COCSaveSlot
from ..models.instance_world import FreakWorldDialogue
from .llm_service import LLMService
from .instance_world_prompts import get_gm_config
from .coc_generator import (
    COCGenerator, PrimaryAttributes, SecondaryAttributes, Profession,
    PRIMARY_ATTRIBUTES, PROFESSIONS
)


# =====================================================
# 内部游戏状态（数据库存储，用于状态跟踪）
# =====================================================

class GameStatus:
    """游戏状态枚举"""
    STEP0_INTRO = "step0_intro"
    STEP1_ATTRIBUTES = "step1_attributes"
    STEP2_SECONDARY = "step2_secondary"
    STEP3_PROFESSION = "step3_profession"
    STEP4_CARD = "step4_card"
    PLAYING = "playing"
    ENDED = "ended"
    # 兼容旧数据
    GM_SELECT = "gm_select"


class COCService:
    """克苏鲁跑团业务服务"""

    # 存档触发密钥
    SAVE_KEY = "73829104碧鹿孽心0109要去坐标BBT进行存档"
    LOAD_KEY = "73829104碧鹿孽心0109要去坐标BBT进行读档"

    def __init__(self, llm_service: LLMService, db: Session, config: Dict):
        self.llm = llm_service
        self.db = db
        self.config = config
        self.generator = COCGenerator()

    # ==================== 工具方法 ====================

    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        return f"coc_{uuid.uuid4().hex[:12]}"

    # ==================== 数据库操作 ====================

    def _create_session_db(
        self,
        account_id: int,
        session_id: Optional[str] = None,
        gm_id: Optional[str] = None
    ) -> COCGameState:
        """创建新游戏状态"""
        session = COCGameState(
            session_id=session_id or self._generate_session_id(),
            account_id=account_id,
            gm_id=gm_id,
            game_status=GameStatus.STEP0_INTRO,
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
        flag_modified(session, "temp_data")
        flag_modified(session, "investigator_card")
        self.db.commit()
        self.db.refresh(session)

    def _get_dialogue_history(self, session_id: int) -> List[Dict[str, str]]:
        """获取对话历史（从 t_freak_world_dialogue 读取）"""
        try:
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
        except Exception as e:
            custom_logger.warning(f"Failed to get dialogue history: {e}")
            return []

    # ==================== 会话管理 ====================

    def _get_or_create_session(self, request: IWChatRequest) -> COCGameState:
        """获取或创建会话"""
        if request.session_id:
            session = self._get_session_db(request.session_id)
            if session:
                return session
            # session_id 由 Java 层创建但本地无记录，创建新会话
            custom_logger.info(f"Session {request.session_id} not found, creating new")
            session = self._create_session_db(
                account_id=int(request.user_id),
                session_id=request.session_id,
                gm_id=request.gm_id if request.gm_id != "0" else None
            )
        else:
            session = self._create_session_db(
                account_id=int(request.user_id),
                gm_id=request.gm_id if request.gm_id != "0" else None
            )

        # 初始化 GM 信息
        self._init_gm_info(session, request.gm_id)
        return session

    def _init_gm_info(self, session: COCGameState, gm_id: str):
        """初始化 GM 信息（仅在尚未设置时）"""
        temp = session.get_temp_data()
        if temp.get("gm_name"):
            return  # 已有 GM 信息

        if gm_id and gm_id != "0":
            gm_config = get_gm_config(gm_id)
            session.gm_id = gm_id
            temp["gm_name"] = gm_config.get("name", "GM")
            temp["gm_traits"] = gm_config.get("traits", "神秘深邃")
        else:
            temp["gm_name"] = "GM"
            temp["gm_traits"] = "神秘深邃"

        session.set_temp_data(temp)
        self._update_session_db(session)

    # ==================== 响应构建 ====================

    def _build_response(
        self,
        session: COCGameState,
        content: Any,
        complete: bool = False,
        save_id: Optional[str] = None,
        ext_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """构建 COC 响应（不含 step 字段）"""
        return {
            "sessionId": session.session_id,
            "gmId": session.gm_id or "0",
            "content": content,
            "complete": complete,
            "saveId": save_id,
            "extData": ext_data or {
                "investigatorCard": session.investigator_card,
                "turn": session.turn_number,
                "round": session.round_number
            }
        }

    def _error_response(
        self,
        message: str,
        session_id: str = "",
        gm_id: str = "0"
    ) -> Dict[str, Any]:
        """构建错误响应"""
        return {
            "sessionId": session_id,
            "gmId": gm_id,
            "content": message,
            "complete": True,
            "saveId": None,
            "extData": None
        }

    # ==================== 主入口 ====================

    async def process_request(self, request: IWChatRequest) -> Dict[str, Any]:
        """
        处理 COC 请求（step 驱动）

        请求的 step 决定当前阶段：
        - step=0: 开始游戏，返回背景
        - step=1: 属性分配（重发=重roll）
        - step=2: 确认常规属性，返回次级属性
        - step=3: 确认次级属性，返回职业（重发=重roll职业）
        - step=4: 选择职业（message=职业名），返回人物卡
        - step=5: 确认人物卡/游戏对话

        存档/读档通过 extParam.action 控制，不需要 step。
        """
        ext_param = request.ext_param or {}
        action = ext_param.get("action", "")
        step = request.step

        custom_logger.info(
            f"Processing COC request: user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, "
            f"step={step}, action={action}"
        )

        try:
            # 存档/读档不需要 step
            if action == "save":
                return await self._handle_save_action(request)
            if action == "load" or request.save_id:
                return await self._handle_load_action(request)

            # 获取或创建会话
            session = self._get_or_create_session(request)

            # 确保 GM 信息已设置
            self._init_gm_info(session, request.gm_id)

            # Step 驱动分发
            if step == "0":
                return await self._step0_background(session, request)
            elif step == "1":
                return await self._step1_attributes(session, request)
            elif step == "2":
                return await self._step2_secondary(session, request)
            elif step == "3":
                return await self._step3_profession(session, request)
            elif step == "4":
                return await self._step4_character_card(session, request)
            elif step == "5":
                return await self._step5_playing(session, request)
            else:
                return self._error_response(
                    f"无效的游戏阶段: {step}",
                    request.session_id or "",
                    request.gm_id or "0"
                )

        except Exception as e:
            custom_logger.error(f"Error processing COC request: {e}", exc_info=True)
            self.db.rollback()
            return self._error_response(
                f"处理请求时发生错误：{str(e)}",
                request.session_id or "",
                request.gm_id or "0"
            )

    # ==================== Step 0: 背景介绍 ====================

    async def _step0_background(
        self,
        session: COCGameState,
        request: IWChatRequest
    ) -> Dict[str, Any]:
        """
        Step 0: 开始游戏，返回背景介绍 (markdown)
        """
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        gm_traits = temp.get("gm_traits", "神秘深邃")

        # 重置游戏状态（支持重新开始）
        session.game_status = GameStatus.STEP0_INTRO
        session.investigator_card = None
        session.turn_number = 0
        session.round_number = 1
        # 保留 GM 信息，清空角色数据
        kept_keys = {"gm_name", "gm_traits"}
        new_temp = {k: v for k, v in temp.items() if k in kept_keys}
        session.set_temp_data(new_temp)
        self._update_session_db(session)

        intro = f"""（{gm_name}{gm_traits[:15]}...）

你好，我是{gm_name}，将作为你的 Game Master 陪伴你完成这次《克苏鲁的呼唤》冒险。

---

**克苏鲁的呼唤**

人类从未真正掌控宇宙——那些怪异的异星生物、神祗般的存在，正以冷漠的目光注视着这个世界。

在这个世界中，你将扮演一名**调查员**，深入那些被常人遗忘的角落，揭开藏在迷雾后的可怖谜团。你可能是一名记者、侦探、学者，或任何被命运卷入神秘事件的普通人。

你的理智将面临考验，你的生命悬于一线。但真相，正在黑暗中等待着你。

---

准备好了吗？让我们开始创建你的调查员角色。"""

        return self._build_response(session, content=intro)

    # ==================== Step 1: 常规属性分配 ====================

    async def _step1_attributes(
        self,
        session: COCGameState,
        request: IWChatRequest
    ) -> Dict[str, Any]:
        """
        Step 1: 属性分配（每次请求都重新 roll）

        前端发送 step=1 即触发 roll：
        - 首次进入 step=1：roll 属性
        - 再次发送 step=1：重roll 属性
        """
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")

        # 每次请求 step=1 都重新 roll
        self.generator = COCGenerator()
        primary = self.generator.roll_primary_attributes()
        temp["primary_attributes"] = primary.to_dict()
        session.game_status = GameStatus.STEP1_ATTRIBUTES
        session.set_temp_data(temp)
        self._update_session_db(session)

        content = {
            "title": "常规属性分配结果",
            "description": f"（{gm_name}）以下是你随机分配的8个常规属性值：",
            "attributes": primary.to_display_list(),
            "selections": [
                {"id": "confirm", "text": "确认属性"},
                {"id": "reroll", "text": "重新随机"}
            ]
        }

        return self._build_response(session, content=content)

    # ==================== Step 2: 次级属性确认 ====================

    async def _step2_secondary(
        self,
        session: COCGameState,
        request: IWChatRequest
    ) -> Dict[str, Any]:
        """
        Step 2: 确认常规属性，计算并返回次级属性

        前端发送 step=2 表示确认了 step=1 的常规属性。
        如果想重roll，前端应发送 step=1。
        """
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        primary_dict = temp.get("primary_attributes")

        if not primary_dict:
            return self._error_response(
                "请先完成属性分配（发送 step=1）",
                session.session_id, session.gm_id or "0"
            )

        # 计算次级属性
        primary = PrimaryAttributes(**primary_dict)
        self.generator = COCGenerator()
        secondary = self.generator.calc_secondary_attributes(primary)
        temp["secondary_attributes"] = secondary.to_dict()
        session.game_status = GameStatus.STEP2_SECONDARY
        session.set_temp_data(temp)
        self._update_session_db(session)

        content = {
            "title": "次级属性计算结果",
            "description": f"（{gm_name}记录下你的属性）很好，属性已确认。根据常规属性计算出以下次级属性：",
            "attributes": secondary.to_display_list(primary),
            "selections": [
                {"id": "confirm", "text": "确认次级属性"},
                {"id": "reroll", "text": "返回重新分配常规属性"}
            ]
        }

        return self._build_response(session, content=content)

    # ==================== Step 3: 职业选择 ====================

    async def _step3_profession(
        self,
        session: COCGameState,
        request: IWChatRequest
    ) -> Dict[str, Any]:
        """
        Step 3: 确认次级属性，返回职业选项（每次请求都重新 roll 职业）

        前端发送 step=3 表示确认了次级属性。
        再次发送 step=3 = 重roll 职业。
        """
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")

        if not temp.get("primary_attributes") or not temp.get("secondary_attributes"):
            return self._error_response(
                "请先完成属性分配（step=1 → step=2）",
                session.session_id, session.gm_id or "0"
            )

        # 每次请求 step=3 都重新 roll 职业
        self.generator = COCGenerator()
        professions = self.generator.roll_professions(3)
        temp["professions"] = [p.to_dict() for p in professions]
        session.game_status = GameStatus.STEP3_PROFESSION
        session.set_temp_data(temp)
        self._update_session_db(session)

        # 构建职业展示数据
        profession_data = [p.to_display_dict() for p in professions]

        # 构建选择项（职业名称作为 id）
        selections = []
        for p in professions:
            selections.append({"id": p.name, "text": f"选择 {p.name}"})
        selections.append({"id": "reroll", "text": "重新随机职业"})

        content = {
            "title": "职业选择",
            "description": f"（{gm_name}满意地点头）次级属性已确定。以下是随机生成的3个职业供你选择：",
            "professions": profession_data,
            "selections": selections
        }

        return self._build_response(session, content=content)

    # ==================== Step 4: 人物卡总结 ====================

    async def _step4_character_card(
        self,
        session: COCGameState,
        request: IWChatRequest
    ) -> Dict[str, Any]:
        """
        Step 4: 选择职业（message=职业名），返回人物卡总结

        前端在 message 中传入选择的职业名称。
        如果想重roll职业，前端应发送 step=3。
        """
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        professions_data = temp.get("professions", [])
        profession_name = request.message.strip()

        if not profession_name:
            # 如果 message 为空，尝试从 extParam 读取
            ext_param = request.ext_param or {}
            profession_name = ext_param.get("selection", "").strip()

        if not profession_name:
            names = [p.get("name", "") for p in professions_data]
            return self._error_response(
                f"请在 message 中传入选择的职业名称，可选：{', '.join(names)}",
                session.session_id, session.gm_id or "0"
            )

        # 查找匹配的职业（精确匹配 → 包含匹配 → 全局查找）
        selected_profession = None

        # 1. 从 step=3 给出的职业中精确匹配
        for p in professions_data:
            if p.get("name") == profession_name:
                selected_profession = p
                break

        # 2. 包含匹配
        if not selected_profession:
            for p in professions_data:
                if profession_name in p.get("name", "") or p.get("name", "") in profession_name:
                    selected_profession = p
                    break

        # 3. 从所有职业中查找
        if not selected_profession and profession_name in PROFESSIONS:
            self.generator = COCGenerator()
            prof = self.generator.get_profession_by_name(profession_name)
            if prof:
                selected_profession = prof.to_dict()

        if not selected_profession:
            names = [p.get("name", "") for p in professions_data]
            return self._error_response(
                f"未找到职业 '{profession_name}'，可选职业：{', '.join(names)}",
                session.session_id, session.gm_id or "0"
            )

        # 生成兴趣技能
        self.generator = COCGenerator()
        interest_skills = self.generator.roll_interest_skills(
            selected_profession.get("skills", [])
        )

        temp["selected_profession"] = selected_profession
        temp["interest_skills"] = interest_skills

        # 调用 LLM 生成角色背景故事
        background_data = await self._generate_background_data(
            session, selected_profession, temp
        )
        temp["background_data"] = background_data

        # 组装完整人物卡
        primary = PrimaryAttributes(**temp.get("primary_attributes", {}))
        secondary = SecondaryAttributes(**temp.get("secondary_attributes", {}))

        investigator_card = self.generator.generate_investigator_card(
            primary=primary,
            secondary=secondary,
            profession=Profession.from_dict(selected_profession),
            interest_skills=interest_skills,
            name=background_data.get("name", "调查员"),
            gender=background_data.get("gender", "男"),
            age=background_data.get("age", 30),
            background=background_data.get("background", ""),
            equipment=background_data.get("equipment", [])
        )

        session.investigator_card = investigator_card
        session.game_status = GameStatus.STEP4_CARD
        session.set_temp_data(temp)
        self._update_session_db(session)

        content = {
            "title": "调查员人物卡总结",
            "description": f"（{gm_name}整理好所有资料）你的调查员人物卡已生成完毕！",
            "investigatorCard": investigator_card,
            "selections": [
                {"id": "confirm", "text": "确认人物卡，开始游戏"},
                {"id": "reroll", "text": "重新选择职业"}
            ]
        }

        return self._build_response(session, content=content)

    # ==================== Step 5: 游戏对话 ====================

    async def _step5_playing(
        self,
        session: COCGameState,
        request: IWChatRequest
    ) -> Dict[str, Any]:
        """
        Step 5: 确认人物卡并开始游戏 / 持续游戏对话 (markdown)

        - 首次发送 step=5（game_status != playing）：开始游戏，返回第一个对话
        - 后续发送 step=5 + message：继续游戏对话
        """
        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        investigator = session.investigator_card or {}

        # 首次进入游戏
        if session.game_status != GameStatus.PLAYING:
            if not investigator:
                return self._error_response(
                    "请先完成角色创建（step=1 到 step=4）",
                    session.session_id, session.gm_id or "0"
                )

            session.game_status = GameStatus.PLAYING
            session.turn_number = 1
            session.round_number = 1
            self._update_session_db(session)

            content = f"""（{gm_name}的眼中闪过一丝期待）

**游戏正式开始！**

调查员 **{investigator.get('name', '调查员')}**（{investigator.get('profession', '职业')}）准备踏入未知的世界。

人类从未真正掌控宇宙——那些怪异的异星生物、神祗般的存在，正以冷漠的目光注视着这个世界。

作为{investigator.get('profession', '调查员')}的你，将深入被遗忘的角落，揭开藏在迷雾后的谜团...

❤ 生命 {investigator.get('currentHP', 0)}   💎 魔法 {investigator.get('currentMP', 0)}   🧠 理智 {investigator.get('currentSAN', 0)}

请输入你的行动或对话："""

            return self._build_response(session, content=content)

        # ---- 已在游戏中，处理玩家输入 ----

        message = request.message.strip()
        if not message:
            return self._build_response(
                session,
                content="请输入你的行动或对话。"
            )

        # 检查存档密钥
        if message == self.SAVE_KEY:
            return await self._handle_save_internal(session)

        # 增加轮数
        session.turn_number += 1

        # 构建系统 prompt
        system_prompt = self._build_game_system_prompt(session, investigator, temp)

        # 获取对话历史
        history = self._get_dialogue_history(session.id) if session.id else []

        # 构建消息
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-20:])  # 最近 20 条
        messages.append({"role": "user", "content": message})

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_32b_custom", "qwen_max", "deepseek"],
                parse_json=False,
                response_format="text"
            )
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

        return self._build_response(session, content=content)

    # ==================== 存档/读档 ====================

    def _generate_save_id(self) -> str:
        """生成存档 ID"""
        return f"save_{uuid.uuid4().hex[:12]}"

    def _get_save_slot(self, save_id: str) -> Optional[COCSaveSlot]:
        """根据 save_id 查询存档"""
        return self.db.query(COCSaveSlot).filter(
            and_(
                COCSaveSlot.save_id == save_id,
                COCSaveSlot.del_ == 0
            )
        ).first()

    def _create_save_slot(self, session: COCGameState) -> COCSaveSlot:
        """将当前 session 快照写入存档表"""
        save_slot = COCSaveSlot(
            save_id=self._generate_save_id(),
            session_id=session.session_id,
            account_id=session.account_id,
            gm_id=session.gm_id,
            game_status=session.game_status,
            investigator_card=session.investigator_card,
            round_number=session.round_number,
            turn_number=session.turn_number,
            temp_data=session.get_temp_data(),
            del_=0
        )
        self.db.add(save_slot)
        self.db.commit()
        self.db.refresh(save_slot)
        custom_logger.info(f"Created save slot: {save_slot.save_id} for session {session.session_id}")
        return save_slot

    async def _handle_save_action(self, request: IWChatRequest) -> Dict[str, Any]:
        """处理存档请求（extParam.action = "save"）"""
        session = self._get_session_db(request.session_id)
        if not session:
            return self._error_response(
                "会话不存在，无法存档",
                request.session_id or "", request.gm_id or "0"
            )
        return await self._handle_save_internal(session)

    async def _handle_save_internal(self, session: COCGameState) -> Dict[str, Any]:
        """存档内部逻辑：将快照写入 t_coc_save_slot 表"""
        # 增加存档计数
        save_number = session.increment_save_count()
        self._update_session_db(session)

        # 写入存档表
        save_slot = self._create_save_slot(session)

        temp = session.get_temp_data()
        gm_name = temp.get("gm_name", "GM")
        investigator = session.investigator_card or {}

        content = f"（{gm_name}点点头）\n\n"
        content += f"**【存档 {save_number:03d}】**\n\n"
        content += f"调查员：{investigator.get('name', '未知')}\n"
        content += f"职业：{investigator.get('profession', '未知')}\n"
        content += f"当前轮数：{session.turn_number} / 回合：{session.round_number}\n"
        content += f"状态：HP {investigator.get('currentHP')} / "
        content += f"MP {investigator.get('currentMP')} / "
        content += f"SAN {investigator.get('currentSAN')}\n\n"
        content += "存档已保存。"

        return self._build_response(
            session,
            content=content,
            save_id=save_slot.save_id
        )

    async def _handle_load_action(self, request: IWChatRequest) -> Dict[str, Any]:
        """
        处理读档请求

        前端只需传 saveId，后端自行查表恢复：
        1. 根据 saveId 查 t_coc_save_slot
        2. 创建新 session，恢复人物卡/进度/GM
        3. 构建 system prompt + 存档进度
        4. 调用 LLM 生成"继续冒险"对话
        """
        # 从 request.save_id 或 extParam 获取 saveId
        save_id = request.save_id
        if not save_id:
            ext_param = request.ext_param or {}
            save_id = ext_param.get("saveId") or ext_param.get("save_id")

        if not save_id:
            return self._error_response(
                "缺少存档ID（saveId）",
                request.session_id or "", request.gm_id or "0"
            )

        # 查询存档
        save_slot = self._get_save_slot(save_id)
        if not save_slot:
            return self._error_response(
                f"未找到存档: {save_id}",
                request.session_id or "", request.gm_id or "0"
            )

        # 创建新会话
        session = self._create_session_db(
            account_id=save_slot.account_id,
            session_id=request.session_id if request.session_id else None,
            gm_id=save_slot.gm_id
        )

        # 恢复游戏状态
        session.investigator_card = save_slot.investigator_card
        session.round_number = save_slot.round_number
        session.turn_number = save_slot.turn_number
        session.game_status = save_slot.game_status or GameStatus.PLAYING

        # 恢复临时数据（含 GM 信息）
        temp_data = save_slot.temp_data or {}
        session.set_temp_data(temp_data)
        self._update_session_db(session)

        investigator = session.investigator_card or {}
        gm_name = temp_data.get("gm_name", "GM")
        gm_traits = temp_data.get("gm_traits", "")

        # 构建 system prompt + 对话历史，调用 LLM 生成继续对话
        system_prompt = self._build_game_system_prompt(session, investigator, temp_data)

        # 从原 session 获取对话历史
        history = self._get_dialogue_history(save_slot.session_id)

        resume_msg = (
            f"玩家从存档恢复游戏。当前是第{session.turn_number}轮/第{session.round_number}回合。"
            f"调查员{investigator.get('name', '调查员')}（{investigator.get('profession', '职业')}）"
            f"当前状态：HP={investigator.get('currentHP')}, "
            f"MP={investigator.get('currentMP')}, SAN={investigator.get('currentSAN')}。"
            f"请简短描述当前场景氛围，然后提示玩家继续行动。"
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": resume_msg})

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_32b_custom", "qwen_max", "deepseek"],
                parse_json=False,
                response_format="text"
            )
            ai_content = response.get("content", "")
        except Exception as e:
            custom_logger.error(f"LLM call failed on load: {e}")
            ai_content = (
                f"（{gm_name}翻开记录本）\n\n"
                f"欢迎回来，{investigator.get('name', '调查员')}。"
                f"\n\n请继续你的冒险。"
            )

        # 构建状态行
        status_line = f"❤ 生命 {investigator.get('currentHP', '?')}   "
        status_line += f"💎 魔法 {investigator.get('currentMP', '?')}   "
        status_line += f"🧠 理智 {investigator.get('currentSAN', '?')}"

        content = f"**【读档成功】**\n\n"
        content += f"**【{session.turn_number:02d}轮 / {session.round_number:02d}回合】**\n\n"
        content += ai_content
        content += f"\n\n{status_line}"

        return self._build_response(session, content=content)

    # ==================== LLM 辅助方法 ====================

    async def _generate_background_data(
        self,
        session: COCGameState,
        profession: Dict,
        temp: Dict
    ) -> Dict[str, Any]:
        """调用 LLM 生成角色背景故事和装备"""

        primary = temp.get("primary_attributes", {})

        prompt = f"""你是一个克苏鲁跑团游戏的角色生成器。请为以下调查员生成背景故事和装备。

职业：{profession.get('name', '调查员')}
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
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen3_32b_custom", "qwen_max", "deepseek"],
                parse_json=True,
                response_format="json_object"
            )

            content = response.get("content", "")
            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())

        except Exception as e:
            custom_logger.error(f"Failed to generate background: {e}")
            return {
                "name": "调查员",
                "gender": "男",
                "age": 30,
                "background": f"一名经验丰富的{profession.get('name', '调查员')}，性格沉稳，善于观察。",
                "equipment": ["手电筒", "笔记本", "钢笔"]
            }

    def _build_game_system_prompt(
        self,
        session: COCGameState,
        investigator: Dict,
        temp: Dict
    ) -> str:
        """构建游戏阶段的系统 prompt"""

        gm_name = temp.get("gm_name", "GM")
        gm_traits = temp.get("gm_traits", "")

        return f"""你是克苏鲁跑团游戏的Game Master，扮演名为"{gm_name}"的电子精灵。
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

    # ==================== SSE 流式 ====================

    async def stream_chat(
        self,
        request: IWChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式对话（SSE 模式）

        - 选择阶段（step 1-4）：content 是 JSON，直接发送完整结果
        - markdown 阶段（step 0, 5）：模拟流式发送
        """
        custom_logger.info(
            f"Stream COC request: user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, step={request.step}"
        )

        try:
            # 调用同步处理
            response = await self.process_request(request)
            content = response.get("content", "")

            # 字符串内容（markdown）模拟流式发送
            if isinstance(content, str):
                chunk_size = 50
                for i in range(0, len(content), chunk_size):
                    yield {
                        "type": "delta",
                        "content": content[i:i + chunk_size]
                    }

            # 发送完成事件
            yield {
                "type": "done",
                "complete": True,
                "result": response
            }

        except Exception as e:
            custom_logger.error(f"Error in COC stream_chat: {e}")
            self.db.rollback()
            yield {
                "type": "error",
                "complete": True,
                "message": str(e)
            }
