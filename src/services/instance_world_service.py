"""
副本世界服务 - 处理文字副本游戏的核心业务逻辑

游戏流程（extParam.action + step + extParam.selection 驱动）：

    action=start → step=1 → step=2 → step=3 → 持续对话
    背景+性别选择   世界叙事   角色列表   游戏对话
    (JSON)        (md,流式)  (JSON)   (md,流式)

前端交互方式：
- extParam.action="start" → 开始游戏，返回 GM 介绍 + 世界背景 + 性别选择器
- step=1 + extParam.selection=male/female → LLM 生成世界叙事（流式 markdown）
- step=2 + extParam.selection=confirm → 返回角色列表（JSON，同 COC 选职业）
- step=2 + extParam.selection=char_01~char_N → 选定角色，进入游戏
- step=3 → 游戏对话（真流式）
- extParam.action="change_char" → 换人（发送换人密钥，LLM 返回角色列表 markdown）
- extParam.action="save" → 存档
- extParam.action="load" → 读档
- 响应不返回 step 字段（同 COC 模式）
"""
import json
import uuid
import random
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..schemas import IWChatRequest
from ..models.instance_world import FreakWorldGameState, FreakWorldDialogue
from ..custom_logger import custom_logger
from .llm_service import LLMService
from .instance_world_prompts import (
    build_system_prompt, get_gm_config, get_world_config,
    load_world_setting, get_gm_ids, get_enabled_gms,
    get_iw_prompt_saving
)


# =====================================================
# 内部游戏状态
# =====================================================

class GameStatus:
    """游戏状态枚举"""
    INTRO = "intro"                       # 背景介绍 + 性别选择
    NARRATIVE = "narrative"               # 世界叙事（LLM 大段文字）
    CHARACTER_SELECT = "character_select"  # 角色列表
    PLAYING = "playing"                   # 游戏进行中
    ENDED = "ended"                       # 游戏正常结束
    DEATH = "death"                       # 角色死亡


class FreakWorldService:
    """副本世界业务服务"""

    # 存档触发密钥
    SAVE_KEY = "73829104碧鹿孽心0109要去坐标BBT进行退出并存档"
    # 换人密钥
    SWITCH_KEY = "73829104核子松鼠0114在哈尔滨错过0117皇上的婚礼所以需要更换交谈角色"

    def __init__(self, llm_service: LLMService, db: Session, config: Dict):
        self.llm = llm_service
        self.db = db
        self.config = config
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_path = os.path.dirname(os.path.dirname(current_dir))

    # ==================== 工具方法 ====================

    def _generate_session_id(self) -> str:
        return f"fw_{uuid.uuid4().hex[:13]}"

    def _generate_save_id(self) -> str:
        return f"save_{uuid.uuid4().hex[:12]}"

    def _get_random_gm_id(self) -> str:
        gm_ids = get_gm_ids()
        return random.choice(gm_ids) if gm_ids else "gm_01"

    # ==================== 数据库操作 ====================

    def _create_session_db(
        self,
        account_id: int,
        freak_world_id: int,
        gm_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> FreakWorldGameState:
        session = FreakWorldGameState(
            session_id=session_id or self._generate_session_id(),
            account_id=account_id,
            freak_world_id=freak_world_id,
            gm_id=gm_id or self._get_random_gm_id(),
            game_status=GameStatus.INTRO,
            del_=0
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        custom_logger.info(f"Created new FW game state: {session.session_id}")
        return session

    def _get_session_db(self, session_id: str) -> Optional[FreakWorldGameState]:
        if not session_id:
            return None
        return self.db.query(FreakWorldGameState).filter(
            FreakWorldGameState.session_id == session_id
        ).first()

    def _update_session_db(self, session: FreakWorldGameState):
        self.db.commit()
        self.db.refresh(session)

    def _get_dialogue_history(self, session_id) -> List[Dict[str, str]]:
        try:
            dialogues = self.db.query(FreakWorldDialogue).filter(
                and_(
                    FreakWorldDialogue.session_id == session_id,
                    FreakWorldDialogue.del_ == 0
                )
            ).order_by(FreakWorldDialogue.create_time.asc()).all()
            messages = []
            for d in dialogues:
                messages.extend(d.to_messages())
            return messages
        except Exception as e:
            custom_logger.warning(f"Failed to get dialogue history: {e}")
            return []

    # ==================== 会话管理 ====================

    def _get_or_create_session(self, request: IWChatRequest) -> FreakWorldGameState:
        if request.session_id:
            session = self._get_session_db(request.session_id)
            if session:
                return session
            custom_logger.info(f"Session {request.session_id} not found, creating new")

        gm_id = request.gm_id if request.gm_id and request.gm_id != "0" else self._get_random_gm_id()
        return self._create_session_db(
            account_id=int(request.user_id),
            freak_world_id=int(request.world_id) if request.world_id.isdigit() else 1,
            gm_id=gm_id,
            session_id=request.session_id if request.session_id else None
        )

    # ==================== 响应构建 ====================

    def _build_response(self, content: Any, complete: bool = False) -> Dict[str, Any]:
        return {"content": content, "complete": complete}

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {"content": message, "complete": True}

    # ==================== 主入口 ====================

    async def process_request(self, request: IWChatRequest) -> Dict[str, Any]:
        """
        处理副本世界请求

        - action=start: 背景+性别选择
        - step=1 + selection=male/female: 世界叙事（同步模式）
        - step=2 + selection=confirm: 角色列表
        - step=2 + selection=char_XX: 选定角色，进入游戏
        - step=3: 游戏对话
        - action=save/load: 存档/读档
        """
        ext_param = request.ext_param or {}
        action = ext_param.get("action", "")
        selection = ext_param.get("selection", "")
        step = request.step

        custom_logger.info(
            f"Processing IW request: user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, "
            f"step={step}, action={action}, selection={selection}"
        )

        try:
            # extParam.action 驱动
            if action == "start":
                session = self._get_or_create_session(request)
                return await self._step0_intro(session, request)
            if action == "change_char":
                return await self._handle_change_char(request)
            if action == "save":
                return await self._handle_save_action(request)
            if action == "load":
                return await self._handle_load_action(request)

            # 获取或创建会话
            session = self._get_or_create_session(request)

            # Step + Selection 分发
            if step == "1":
                return await self._handle_step1(session, request, selection)
            elif step == "2":
                return await self._handle_step2(session, request, selection)
            elif step == "3":
                return await self._step3_playing(session, request)
            else:
                return self._error_response(f"无效的游戏阶段: {step}")

        except Exception as e:
            custom_logger.error(f"Error processing IW request: {e}", exc_info=True)
            self.db.rollback()
            return self._error_response(f"处理请求时发生错误：{str(e)}")

    # ==================== Step 0: 背景介绍 + 性别选择 ====================

    async def _step0_intro(
        self, session: FreakWorldGameState, request: IWChatRequest
    ) -> Dict[str, Any]:
        """action=start: 返回 GM 介绍 + 世界背景 + 性别选择器（JSON）"""
        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")
        gm_traits = gm_config.get("traits", "")

        world_config = get_world_config(str(session.freak_world_id))
        world_name = world_config.get("name", "未知世界")
        world_theme = world_config.get("theme", "")
        world_description = world_config.get("description", "")

        session.game_status = GameStatus.INTRO
        session.gender_preference = None
        session.current_character_id = None
        session.characters = None
        self._update_session_db(session)

        content = {
            "description": f"（{gm_name}，{gm_traits}）",
            "worldInfo": {
                "title": world_name,
                "theme": world_theme,
                "background": world_description
            },
            "selections": [
                {"id": "male", "text": "男性"},
                {"id": "female", "text": "女性"}
            ]
        }
        return self._build_response(content=content)

    # ==================== Step 1: 世界叙事（流式 markdown）====================

    async def _handle_step1(
        self, session: FreakWorldGameState, request: IWChatRequest, selection: str
    ) -> Dict[str, Any]:
        """
        step=1 + selection=male/female → 调 LLM 生成世界叙事（同步模式返回完整文本）
        """
        if selection not in ("male", "female"):
            return self._error_response("请在 extParam.selection 中传入性别选择（male/female）")

        # 保存性别偏好
        session.gender_preference = selection
        session.game_status = GameStatus.NARRATIVE
        self._update_session_db(session)

        # 构建 system prompt，调用 LLM 生成世界叙事
        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=str(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        gender_text = "男性" if selection == "male" else "女性"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"我期待见到的原住民是{gender_text}。"}
        ]

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096,
                parse_json=False,
                response_format="text"
            )
            ai_content = self._clean_llm_content(response.get("content", ""))
        except Exception as e:
            custom_logger.error(f"LLM narrative call failed: {e}")
            ai_content = "欢迎来到这个世界..."

        return self._build_response(content=ai_content)

    # ==================== Step 2: 角色列表 / 选定角色 ====================

    async def _handle_step2(
        self, session: FreakWorldGameState, request: IWChatRequest, selection: str
    ) -> Dict[str, Any]:
        """
        step=2:
        - selection=confirm → 调 LLM 生成角色列表（JSON）
        - selection=char_XX → 选定角色，进入游戏
        """
        if selection == "confirm":
            return await self._step2_character_list(session, request)
        elif selection and selection.startswith("char_"):
            return await self._step2_select_character(session, request, selection)
        else:
            # 没有 selection，如果已有角色列表则展示
            if session.characters:
                return self._show_character_list(session)
            return self._error_response("请传入 extParam.selection: confirm（获取角色列表）或 char_XX（选择角色）")

    async def _step2_character_list(
        self, session: FreakWorldGameState, request: IWChatRequest
    ) -> Dict[str, Any]:
        """step=2 + confirm: 调用 LLM 生成角色列表，返回 JSON（同 COC 选职业格式）"""
        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")

        world_setting = load_world_setting(str(session.freak_world_id), self.base_path)
        gender_text = "男性" if session.gender_preference == "male" else "女性"

        session.game_status = GameStatus.CHARACTER_SELECT
        self._update_session_db(session)

        # 调用 LLM 生成角色
        prompt = f"""你是一个副本世界游戏的角色生成器。

世界设定：
{world_setting[:2000]}

请根据以上世界设定，生成 3-5 个{gender_text}角色供玩家选择。

每个角色需要包含：
- name: 角色名字（至少两个字，符合世界观，禁止使用"林飒"）
- gender: 性别（{gender_text}）
- race: 种族/势力/职业
- appearance: 外貌描述（一句话）
- personality: 个性描述（一句话）
- status: 当前状态与心情（一句话）

要求：
- 角色来自至少两个不同群体（种族/势力/职业）
- 外貌、个性、年龄均不重复
- 不得出现年长或外表老态的角色
- 每个角色都要有鲜明特色

请以JSON格式返回：
{{
  "characters": [
    {{"name": "角色名", "gender": "{gender_text}", "race": "种族/势力", "appearance": "外貌", "personality": "个性", "status": "当前状态"}}
  ],
  "description": "（{gm_name}的旁白，介绍这些角色，50字以内）"
}}
只返回JSON，不要其他内容。"""

        try:
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen3_max"],
                parse_json=False,
                response_format="text"
            )
            content = response.get("content", "")
            custom_logger.info(f"LLM characters response (first 200): {str(content)[:200]}")

            if isinstance(content, dict):
                result = content
            else:
                if not content or not content.strip():
                    raise ValueError("LLM returned empty content")
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                result = json.loads(content.strip())

            characters = result.get("characters", [])
            description = result.get("description", f"（{gm_name}向你介绍了几位原住民）")

        except Exception as e:
            custom_logger.error(f"Failed to generate characters: {e}")
            characters = [
                {"name": "旅人", "gender": gender_text, "race": "旅者", "appearance": "风尘仆仆的旅人", "personality": "沉默寡言", "status": "正在休息"},
                {"name": "商人", "gender": gender_text, "race": "商贩", "appearance": "精明干练的商人", "personality": "热情健谈", "status": "正在整理货物"},
                {"name": "守卫", "gender": gender_text, "race": "守卫", "appearance": "身材魁梧的守卫", "personality": "严肃认真", "status": "正在巡逻"}
            ]
            description = f"（{gm_name}向你介绍了几位原住民）"

        # 保存角色列表
        session.characters = characters
        self._update_session_db(session)

        # 构建角色展示（同 COC 选职业格式）
        characters_display = []
        selections = []
        for i, char in enumerate(characters):
            char_id = f"char_{i + 1:02d}"
            characters_display.append({
                "id": char_id,
                "name": char.get("name", ""),
                "gender": char.get("gender", ""),
                "race": char.get("race", ""),
                "appearance": char.get("appearance", ""),
                "personality": char.get("personality", ""),
                "status": char.get("status", "")
            })
            selections.append({"id": char_id, "text": char.get("name", "")})

        content = {
            "description": description,
            "characters": characters_display,
            "selections": selections
        }
        return self._build_response(content=content)

    def _show_character_list(self, session: FreakWorldGameState) -> Dict[str, Any]:
        """重新展示已有的角色列表"""
        characters = session.characters or []
        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")

        characters_display = []
        selections = []
        for i, char in enumerate(characters):
            char_id = f"char_{i + 1:02d}"
            characters_display.append({
                "id": char_id,
                "name": char.get("name", ""),
                "gender": char.get("gender", ""),
                "race": char.get("race", ""),
                "appearance": char.get("appearance", ""),
                "personality": char.get("personality", ""),
                "status": char.get("status", "")
            })
            selections.append({"id": char_id, "text": char.get("name", "")})

        content = {
            "description": f"（{gm_name}等待你的选择）",
            "characters": characters_display,
            "selections": selections
        }
        return self._build_response(content=content)

    async def _step2_select_character(
        self, session: FreakWorldGameState, request: IWChatRequest, char_id: str
    ) -> Dict[str, Any]:
        """step=2 + char_XX: 选定角色，进入游戏"""
        characters = session.characters or []

        selected_char = None
        if char_id.startswith("char_"):
            try:
                idx = int(char_id.replace("char_", "")) - 1
                if 0 <= idx < len(characters):
                    selected_char = characters[idx]
            except (ValueError, IndexError):
                pass

        if not selected_char:
            ids = [f"char_{i + 1:02d}" for i in range(len(characters))]
            return self._error_response(f"未找到角色 '{char_id}'，可选：{', '.join(ids)}")

        # 保存选定角色，进入游戏
        session.current_character_id = selected_char.get("name", "")
        session.game_status = GameStatus.PLAYING
        self._update_session_db(session)

        # 构建对话上下文，调用 LLM
        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=str(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        char_name = selected_char.get("name", "角色")
        gender_text = "男性" if session.gender_preference == "male" else "女性"

        # 注入角色上下文
        char_list_text = "\n".join([
            f"- {c.get('name')}（{c.get('race', '')}）：{c.get('appearance', '')}，{c.get('personality', '')}，{c.get('status', '')}"
            for c in characters
        ])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"我期待见到的原住民是{gender_text}。"},
            {"role": "assistant", "content": f"以下是你将遇到的原住民：\n\n{char_list_text}\n\n你想和谁交谈？"},
            {"role": "user", "content": f"我选择和{char_name}交谈。"}
        ]

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                parse_json=False,
                response_format="text",
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096
            )
            ai_content = self._clean_llm_content(response.get("content", ""))
        except Exception as e:
            custom_logger.error(f"LLM call failed on character select: {e}")
            ai_content = f"{char_name}抬起头，目光落在你身上。"

        return self._build_response(content=ai_content)

    # ==================== Step 3: 游戏对话 ====================

    async def _step3_playing(
        self, session: FreakWorldGameState, request: IWChatRequest
    ) -> Dict[str, Any]:
        """Step 3: 游戏对话（同步模式）"""
        if session.game_status in (GameStatus.ENDED, GameStatus.DEATH):
            return self._error_response("游戏已结束，请开始新的副本。")
        if session.game_status != GameStatus.PLAYING:
            return self._error_response("请先完成角色选择（step=2）")

        message = request.message.strip()
        if not message:
            return self._build_response(content="请输入你的对话或行动。")

        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=str(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        history = self._get_dialogue_history(session.session_id) if session.session_id else []
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": message})

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                parse_json=False,
                response_format="text",
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096
            )
            ai_content = self._clean_llm_content(response.get("content", ""))
        except Exception as e:
            custom_logger.error(f"LLM call failed: {e}")
            ai_content = "抱歉，系统暂时无法响应，请稍后再试。"

        return self._build_response(content=ai_content)

    # ==================== 换人 ====================

    async def _handle_change_char(self, request: IWChatRequest) -> Dict[str, Any]:
        """
        action=change_char: 发送换人密钥给 LLM，返回角色列表（markdown）。
        已在游戏中，所以返回 markdown 而非 JSON。
        """
        session = self._get_session_db(request.session_id)
        if not session:
            return self._error_response("会话不存在，无法换人")

        if session.game_status != GameStatus.PLAYING:
            return self._error_response("请先进入游戏后再换人")

        # 构建对话历史 + 换人密钥
        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=str(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        history = self._get_dialogue_history(session.session_id) if session.session_id else []
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-20:])
        # 发送换人密钥，LLM 会展示角色列表
        messages.append({"role": "user", "content": self.SWITCH_KEY})

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                parse_json=False,
                response_format="text",
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096
            )
            ai_content = self._clean_llm_content(response.get("content", ""))
        except Exception as e:
            custom_logger.error(f"LLM change_char call failed: {e}")
            ai_content = "换人请求失败，请稍后再试。"

        return self._build_response(content=ai_content)

    # ==================== 存档/读档 ====================

    async def _handle_save_action(self, request: IWChatRequest) -> Dict[str, Any]:
        session = self._get_session_db(request.session_id)
        if not session:
            return self._error_response("会话不存在，无法存档")

        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=str(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )
        history = self._get_dialogue_history(session.session_id) if session.session_id else []
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": self.SAVE_KEY})

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                parse_json=False,
                response_format="text"
            )
            save_content = response.get("content", "存档已保存。")
        except Exception as e:
            custom_logger.error(f"Save LLM call failed: {e}")
            save_content = "存档已保存。"

        return self._build_response(content=save_content)

    async def _handle_load_action(self, request: IWChatRequest) -> Dict[str, Any]:
        ext_param = request.ext_param or {}
        save_data = ext_param.get("save_data")
        if not save_data:
            return self._error_response("缺少存档数据（extParam.save_data）")

        gm_id = save_data.get("gm_id", "0")
        session = self._get_or_create_session(request)
        session.game_status = save_data.get("game_status", GameStatus.PLAYING)
        session.current_character_id = save_data.get("current_character_id")
        session.gm_id = gm_id
        self._update_session_db(session)

        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=str(session.freak_world_id),
            is_loading=True,
            base_path=self.base_path
        )
        save_content_str = json.dumps(save_data, ensure_ascii=False, indent=2)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"【副本存档内容】\n{save_content_str}"}
        ]

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                parse_json=False,
                response_format="text",
                temperature=0.9,
                max_tokens=4096
            )
            ai_content = self._clean_llm_content(response.get("content", ""))
        except Exception as e:
            custom_logger.error(f"Load LLM call failed: {e}")
            ai_content = "存档加载成功，继续你的冒险。"

        return self._build_response(content=ai_content)

    # ==================== LLM 辅助方法 ====================

    @staticmethod
    def _clean_llm_content(content: str) -> str:
        if not content:
            return ""
        content = content.strip()
        try:
            if content.startswith('{') and content.endswith('}'):
                parsed = json.loads(content)
                return parsed.get("content", content)
        except (json.JSONDecodeError, Exception):
            pass
        return content

    # ==================== SSE 流式 ====================

    async def stream_chat(
        self, request: IWChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式对话（SSE 模式）

        - step=1 世界叙事：真流式 LLM
        - step=3 游戏对话：真流式 LLM
        - 其他 step：同步处理后发送
        """
        custom_logger.info(
            f"Stream IW request: user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, step={request.step}"
        )

        ext_param = request.ext_param or {}
        action = ext_param.get("action", "")
        selection = ext_param.get("selection", "")
        step = request.step

        try:
            # step=1 世界叙事 → 真流式
            if step == "1" and selection in ("male", "female") and not action:
                async for chunk in self._stream_narrative(request, selection):
                    yield chunk
                return

            # step=3 游戏对话 → 真流式
            if step == "3" and not action:
                async for chunk in self._stream_playing(request):
                    yield chunk
                return

            # 其他 step → 同步处理后发送
            response = await self.process_request(request)
            content = response.get("content", "")

            if isinstance(content, str):
                chunk_size = 50
                for i in range(0, len(content), chunk_size):
                    yield {"type": "delta", "content": content[i:i + chunk_size]}

            yield {"type": "done", "complete": True, "result": response}

        except Exception as e:
            custom_logger.error(f"Error in IW stream_chat: {e}")
            self.db.rollback()
            yield {"type": "error", "complete": True, "message": str(e)}

    async def _stream_narrative(
        self, request: IWChatRequest, gender: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Step 1 世界叙事的真流式处理"""
        try:
            session = self._get_or_create_session(request)

            session.gender_preference = gender
            session.game_status = GameStatus.NARRATIVE
            self._update_session_db(session)

            system_prompt = build_system_prompt(
                gm_id=session.gm_id,
                world_id=str(session.freak_world_id),
                is_loading=False,
                base_path=self.base_path
            )

            gender_text = "男性" if gender == "male" else "女性"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"我期待见到的原住民是{gender_text}。"}
            ]

            full_content = ""
            async for chunk in self.llm.stream_chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096
            ):
                if chunk.get("type") == "delta":
                    full_content += chunk["content"]
                    yield {"type": "delta", "content": chunk["content"]}
                elif chunk.get("type") == "error":
                    yield {"type": "error", "complete": True, "message": chunk.get("message", "LLM 调用失败")}
                    return

            cleaned = self._clean_llm_content(full_content)
            yield {"type": "done", "complete": True, "result": {"content": cleaned, "complete": False}}

        except Exception as e:
            custom_logger.error(f"Error in _stream_narrative: {e}", exc_info=True)
            self.db.rollback()
            yield {"type": "error", "complete": True, "message": str(e)}

    async def _stream_playing(
        self, request: IWChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Step 3 游戏对话的真流式处理"""
        try:
            session = self._get_or_create_session(request)

            if session.game_status in (GameStatus.ENDED, GameStatus.DEATH):
                yield {"type": "error", "complete": True, "message": "游戏已结束，请开始新的副本。"}
                return
            if session.game_status != GameStatus.PLAYING:
                yield {"type": "error", "complete": True, "message": "请先完成角色选择（step=2）"}
                return

            message = request.message.strip() if request.message else ""
            if not message:
                yield {"type": "delta", "content": "请输入你的对话或行动。"}
                yield {"type": "done", "complete": True, "result": {"content": "请输入你的对话或行动。", "complete": False}}
                return

            system_prompt = build_system_prompt(
                gm_id=session.gm_id,
                world_id=str(session.freak_world_id),
                is_loading=False,
                base_path=self.base_path
            )

            history = self._get_dialogue_history(session.session_id) if session.session_id else []
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history[-20:])
            messages.append({"role": "user", "content": message})

            full_content = ""
            async for chunk in self.llm.stream_chat_completion(
                messages=messages,
                model_pool=["qwen3_max"],
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096
            ):
                if chunk.get("type") == "delta":
                    full_content += chunk["content"]
                    yield {"type": "delta", "content": chunk["content"]}
                elif chunk.get("type") == "error":
                    yield {"type": "error", "complete": True, "message": chunk.get("message", "LLM 调用失败")}
                    return

            cleaned = self._clean_llm_content(full_content)
            yield {"type": "done", "complete": True, "result": {"content": cleaned, "complete": False}}

        except Exception as e:
            custom_logger.error(f"Error in _stream_playing: {e}", exc_info=True)
            self.db.rollback()
            yield {"type": "error", "complete": True, "message": str(e)}
