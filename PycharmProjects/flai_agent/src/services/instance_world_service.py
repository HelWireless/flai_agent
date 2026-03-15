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
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..schemas import IWChatRequest
from ..models.instance_world import FreakWorldGameState, FreakWorldDialogue
from ..models.coc_save_slot import COCSaveSlot
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
    
    # 对话总结配置
    SUMMARY_INTERVAL = 5   # 每5轮生成一次总结
    HISTORY_WINDOW = 10    # 历史对话窗口大小（5轮 = 10条消息）

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

    @staticmethod
    def _parse_world_id(world_id_raw: str) -> int:
        """将请求中的 world_id（如 'world_10' 或 '10'）解析为 DB 存储的整数"""
        cleaned = world_id_raw.replace("world_", "") if world_id_raw.startswith("world_") else world_id_raw
        try:
            return int(cleaned)
        except (ValueError, TypeError):
            return 1

    @staticmethod
    def _format_world_id(freak_world_id) -> str:
        """将 DB 中的 freak_world_id (int) 转换为配置兼容的 world_id 字符串（如 'world_01'）"""
        return f"world_{int(freak_world_id):02d}"

    # ==================== 数据库操作 ====================

    def _create_session_db(
        self,
        user_id: int,
        freak_world_id: int,
        gm_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> FreakWorldGameState:
        session = FreakWorldGameState(
            session_id=session_id or self._generate_session_id(),
            user_id=user_id,
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
        """获取对话历史，自动清理 assistant 消息中的状态行"""
        try:
            dialogues = self.db.query(FreakWorldDialogue).filter(
                and_(
                    FreakWorldDialogue.session_id == session_id,
                    FreakWorldDialogue.del_ == 0
                )
            ).order_by(FreakWorldDialogue.create_time.asc()).all()
            messages = []
            for d in dialogues:
                for msg in d.to_messages():
                    # 清理 assistant 消息中的状态行
                    if msg.get("role") == "assistant":
                        msg["content"] = self._clean_assistant_message(msg.get("content", ""))
                    messages.append(msg)
            return messages
        except Exception as e:
            custom_logger.warning(f"Failed to get dialogue history: {e}")
            return []

    # ==================== 对话总结 ====================

    def _should_generate_summary(self, turn_number: int) -> bool:
        """判断是否应该生成总结（每15轮触发一次）"""
        return turn_number > 0 and turn_number % self.SUMMARY_INTERVAL == 0

    def _trigger_summary_if_needed(self, session: FreakWorldGameState, history: List[Dict]):
        """在响应后异步触发总结生成"""
        # 使用 characters 列表长度作为轮数计算（副本世界没有 turn_number 字段）
        dialogue_count = len(history) // 2  # 每轮有2条消息
        if self._should_generate_summary(dialogue_count):
            custom_logger.info(f"Triggering summary generation at dialogue round {dialogue_count}")
            asyncio.create_task(self._generate_summary_async(
                session.session_id,
                session.dialogue_summary,
                history
            ))

    async def _generate_summary_async(
        self,
        session_id: str,
        old_summary: Optional[str],
        history: List[Dict]
    ):
        """异步生成对话总结"""
        try:
            # 获取需要总结的对话（历史窗口之外的部分）
            if len(history) > self.HISTORY_WINDOW:
                dialogues_to_summarize = history[:-self.HISTORY_WINDOW]
            else:
                dialogues_to_summarize = history
            
            if not dialogues_to_summarize and not old_summary:
                return  # 没有需要总结的内容
            
            # 格式化对话内容
            dialogue_text = self._format_dialogues_for_summary(dialogues_to_summarize)
            
            # 构建总结 prompt
            prompt = self._build_summary_prompt(old_summary, dialogue_text)
            
            # 调用 LLM 生成总结
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen_plus"],
                temperature=0.3,
                parse_json=False,
                response_format="text",
                timeout=60
            )
            
            new_summary = response.get("content", "")
            
            # 更新数据库
            session = self._get_session_db(session_id)
            if session:
                session.dialogue_summary = new_summary
                self.db.commit()
                custom_logger.info(f"Summary updated for session {session_id}, length: {len(new_summary)}")
            
        except Exception as e:
            custom_logger.error(f"Failed to generate summary: {e}", exc_info=True)

    def _format_dialogues_for_summary(self, dialogues: List[Dict]) -> str:
        """将对话列表格式化为文本"""
        lines = []
        for msg in dialogues:
            role = "玩家" if msg["role"] == "user" else "引导者"
            content = msg.get("content", "")[:200]  # 限制单条长度
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines[-30:])  # 最多取30条

    def _build_summary_prompt(self, old_summary: Optional[str], dialogue_text: str) -> str:
        """构建总结生成的 prompt"""
        base_prompt = """你是一个游戏剧情总结助手。请根据以下内容生成简洁的剧情总结（500字以内）。

总结需要包含：
1. 剧情进展：发生了哪些关键事件
2. 重要NPC对话：与哪些NPC进行了重要交流
3. 未解之谜/线索：目前有哪些待解决的谜团或线索

要求：
- 使用第三人称描述
- 突出关键信息，省略琐碎细节
- 保持时间线清晰
"""
        
        if old_summary:
            return f"""{base_prompt}

【之前的剧情总结】
{old_summary}

【新增的对话内容】
{dialogue_text}

请基于之前的总结和新增内容，生成一份更新后的完整总结（合并去重，避免冗余）："""
        else:
            return f"""{base_prompt}

【对话内容】
{dialogue_text}

请生成剧情总结："""

    def _clean_assistant_message(self, content: str) -> str:
        """清理助手消息中重复的状态信息
        
        移除重复的状态行（如 ❤ 生命 XX   💎 魔法 XX   🧠 理智 XX）
        只保留最后一个状态行
        """
        import re
        
        # 匹配状态行模式：❤ 生命 XX   💎 魔法 XX   🧠 理智 XX
        status_pattern = r'❤\s*生命\s*\d+\s*💎\s*魔法\s*\d+\s*🧠\s*理智\s*\d+'
        
        # 找到所有状态行
        matches = list(re.finditer(status_pattern, content))
        
        if len(matches) <= 1:
            return content  # 0或1个状态行，不需要清理
        
        # 保留最后一个状态行，移除其他的
        result = content
        for match in reversed(matches[:-1]):
            start = match.start()
            end = match.end()
            
            # 扩展到包含前后的换行符
            while start > 0 and result[start-1] in '\n\r':
                start -= 1
            while end < len(result) and result[end] in '\n\r':
                end += 1
            
            result = result[:start] + result[end:]
        
        # 清理多余的空行
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()

    def _build_messages_with_summary(
        self,
        system_prompt: str,
        summary: Optional[str],
        history: List[Dict],
        user_message: str,
        extra_context: List[Dict] = None
    ) -> List[Dict]:
        """构建包含总结的消息列表"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # 插入剧情总结（如果有）
        if summary:
            messages.append({
                "role": "assistant",
                "content": f"【剧情回顾】\n{summary}"
            })
        
        # 添加额外上下文（如角色选择等）
        if extra_context:
            messages.extend(extra_context)
        
        # 添加历史对话（最近5轮，已在 _get_dialogue_history 中清理过状态行）
        messages.extend(history[-self.HISTORY_WINDOW:])
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        return messages

    # ==================== 会话管理 ====================

    def _get_or_create_session(self, request: IWChatRequest) -> FreakWorldGameState:
        if request.session_id:
            session = self._get_session_db(request.session_id)
            if session:
                return session
            custom_logger.info(f"Session {request.session_id} not found, creating new")

        gm_id = request.gm_id if request.gm_id and request.gm_id != "0" else self._get_random_gm_id()
        return self._create_session_db(
            user_id=int(request.user_id),
            freak_world_id=self._parse_world_id(request.world_id),
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

    # ==================== 上下文注入辅助 ====================

    def _build_gm_context_messages(
        self, session: FreakWorldGameState, gender_text: str
    ) -> List[Dict[str, str]]:
        """
        构建 GM 引导阶段的对话上下文，用于注入 step1+ 的 messages。
        让 LLM 知道 GM 引导（2.1-2.7）已经完成，应从世界叙事(1.1)开始。
        """
        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")

        world_config = get_world_config(self._format_world_id(session.freak_world_id))
        world_name = world_config.get("name", "未知世界")
        world_theme = world_config.get("theme", "")
        world_desc = world_config.get("description", "")

        # GM 完成 2.1-2.5 的引导内容（精简但完整覆盖所有步骤）
        gm_intro = (
            f"（{gm_name}出现在虚拟水境衡山路的数字灯牌下）"
            f"旅行者，我是{gm_name}，你的电子精灵向导。"
            f"你现在所在的地方是新沪市的虚拟水境衡山路——复古欧式街道，数字灯牌，仿真水景投影，建筑表面是数字仿皮层。"
            f"在这条街景的某处角落，有一道微小的超域量子宇宙通道。"
            f"穿过它，你将抵达「{world_name}」——一个{world_theme}主题的世界。{world_desc}"
            f"在你进入之前，告诉我——你期待在那个世界遇见的原住民，是男性还是女性？"
        )

        # GM 完成 2.6-2.7 确认并引导进入
        gm_farewell = (
            f"（{gm_name}点了点头）{gender_text}原住民，记住了。"
            f'最后提醒你——进入后绝对不能向任何人提起你来自"新沪市"或"超域量子宇宙"，否则会被强制遣返。'
            f"准备好的话我就送你过去了，不过那扇门我进不了，你得独自前往。"
        )

        gm_exit = (
            f"（{gm_name}引导你走向街角的水景投影，一道幽蓝裂隙在倒影中缓缓裂开。"
            f"她轻轻推了你一把，你的视野被吞没——）"
        )

        return [
            {"role": "assistant", "content": gm_intro},
            {"role": "user", "content": f"我期待见到的原住民是{gender_text}。"},
            {"role": "assistant", "content": gm_farewell},
            {"role": "user", "content": "我准备好了。"},
            {"role": "assistant", "content": gm_exit},
        ]

    def _build_playing_context(self, session: FreakWorldGameState) -> List[Dict[str, str]]:
        """
        构建游戏阶段的前序上下文（GM 引导 + 角色列表 + 选定角色），
        当 DB 中无对话历史时注入，确保 LLM 知道当前在扮演哪个角色。
        """
        gender_text = "男性" if session.gender_preference == "male" else "女性"
        characters = session.characters or []
        current_char = session.current_character_id or ""

        # GM 引导上下文
        context = self._build_gm_context_messages(session, gender_text)

        # 角色列表上下文
        if characters:
            char_list_text = "\n".join([
                f"- {c.get('name')}（{c.get('race', '')}）：{c.get('appearance', '')}，{c.get('personality', '')}，{c.get('status', '')}"
                for c in characters
            ])
            context.append({"role": "user", "content": "我进入了这个世界，我能看到哪些人？"})
            context.append({"role": "assistant", "content": f"你推开那扇门，在昏暗的光线中看到了几个身影：\n\n{char_list_text}\n\n你想和谁交谈？"})

        # 选定角色
        if current_char:
            context.append({"role": "user", "content": f"我选择和{current_char}交谈。"})

        return context

    # ==================== Step 0: 背景介绍 + 性别选择 ====================

    async def _step0_intro(
        self, session: FreakWorldGameState, request: IWChatRequest
    ) -> Dict[str, Any]:
        """action=start: 优先从配置加载固定背景，否则调用 LLM 生成"""
        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")

        world_config = get_world_config(self._format_world_id(session.freak_world_id))
        world_name = world_config.get("name", "未知世界")
        world_theme = world_config.get("theme", "")
        world_description = world_config.get("description", "")

        session.game_status = GameStatus.INTRO
        session.gender_preference = None
        session.current_character_id = None
        session.characters = None
        self._update_session_db(session)

        # --- 优化点 1: 优先加载固定背景，避免 LLM 生成等待 ---
        # 尝试从 world_config 的 config 字段或 prompt 字段获取预设背景
        # 预设背景格式建议在数据库 prompt 字段中以 "---INTRO---" 分隔，或直接存储在 config.fixed_intro
        fixed_intro = None
        raw_config = world_config.get("config", {}) # 注意：get_world_config 返回的可能是 to_world_dict 后的
        
        # 兼容性处理：尝试获取原始 PromptConfig 对象中的固定介绍
        db_config = _query_config_by_id(self._format_world_id(session.freak_world_id))
        if db_config and db_config.config and isinstance(db_config.config, dict):
            fixed_intro = db_config.config.get("fixed_intro")

        if fixed_intro:
            custom_logger.info(f"Using fixed intro for world {session.freak_world_id}")
            # 处理固定背景中的占位符和随机选项语法 [A|B|C]
            gm_description = self._process_fixed_intro(fixed_intro, gm_name, world_name)
        else:
            # 只有没有固定背景时才调用 LLM
            system_prompt = build_system_prompt(
                gm_id=session.gm_id,
                world_id=self._format_world_id(session.freak_world_id),
                is_loading=False,
                base_path=self.base_path
            )

            try:
                # 使用更快的模型 qwen_turbo
                response = await self.llm.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "开始"}
                    ],
                    model_pool=["qwen_turbo"],
                    temperature=0.9,
                    top_p=0.85,
                    max_tokens=4096,
                    parse_json=False,
                    response_format="text"
                )
                gm_description = self._clean_llm_content(response.get("content", ""))
            except Exception as e:
                custom_logger.error(f"LLM GM intro call failed: {e}")
                gm_description = f"（{gm_name}，{gm_config.get('traits', '')}）"

        content = {
            "description": gm_description,
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

    def _process_fixed_intro(self, intro: str, gm_name: str, world_name: str) -> str:
        """
        处理固定背景模板，支持：
        1. 变量替换：{gm_name}, {world_name}
        2. 随机选项：[选项A|选项B|选项C]
        """
        import re
        import random

        # 1. 基础变量替换
        result = intro.replace("{gm_name}", gm_name).replace("{world_name}", world_name)

        # 2. 随机选项替换 [A|B|C]
        def pick_random(match):
            options = match.group(1).split('|')
            return random.choice(options).strip()

        # 匹配方括号内的内容，且包含 |
        result = re.sub(r'\[([^\]]*?\|[^\]]*?)\]', pick_random, result)

        return result.strip()

    # ==================== Step 1: 世界叙事（流式 markdown）====================

    async def _handle_step1(
        self, session: FreakWorldGameState, request: IWChatRequest, selection: str
    ) -> Dict[str, Any]:
        """
        step=1 + selection=male/female → 使用固定背景或生成世界叙事
        优先使用预生成的固定背景，避免LLM调用
        """
        if selection not in ("male", "female"):
            return self._error_response("请在 extParam.selection 中传入性别选择（male/female）")

        # 保存性别偏好
        session.gender_preference = selection
        session.game_status = GameStatus.NARRATIVE
        self._update_session_db(session)

        gender_text = "男性" if selection == "male" else "女性"
        
        # 优先使用预生成的固定背景
        world_config = get_world_config(self._format_world_id(session.freak_world_id))
        world_name = world_config.get("name", "未知世界")
        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")
        
        # 尝试获取固定背景
        fixed_intro = None
        db_config = _query_config_by_id(self._format_world_id(session.freak_world_id))
        if db_config and db_config.config and isinstance(db_config.config, dict):
            fixed_intro = db_config.config.get("fixed_intro")
        
        if fixed_intro:
            # 使用预生成的固定背景作为世界叙事
            custom_logger.info(f"Using fixed intro as narrative for world {session.freak_world_id}")
            ai_content = self._process_fixed_intro(fixed_intro, gm_name, world_name)
        else:
            # 只有没有固定背景时才调用 LLM 生成叙事
            custom_logger.info(f"Generating narrative for world {session.freak_world_id}")
            
            # Step 1: 手动构建简化版 system prompt，不包含角色生成指令
            from .instance_world_prompts import get_style_guide, get_gm_config, load_world_setting
            
            parts = []
            # 1. 通用文风指南
            parts.append(get_style_guide())
            # 2. GM 设定
            gm_config = get_gm_config(session.gm_id)
            if gm_config:
                parts.append(f"### GM 引导者设定 ###\n{gm_config.get('prompt', '')}")
            # 3. 世界设定
            world_setting = load_world_setting(self._format_world_id(session.freak_world_id), self.base_path)
            parts.append(f"### 副本世界信息 ###\n{world_setting}")
            # 4. 明确指令：只生成场景，不生成角色
            parts.append("""### 当前任务 ###
请描述用户进入这个世界后的场景、氛围和环境。
重要：不要描述任何具体的人物或NPC，只描述环境和氛围。
在描述的最后，用一句话引导用户接下来选择一位同伴开始冒险。""")
            
            system_prompt = "\n\n".join(parts)

            # 注入 GM 引导对话上下文
            gm_context = self._build_gm_context_messages(session, gender_text)
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(gm_context)
            
            # 添加用户消息
            messages.append({"role": "user", "content": "我已经到达这个世界了，请描述我看到的场景。"})

            try:
                response = await self.llm.chat_completion(
                    messages=messages,
                    model_pool=["qwen_plus"],
                    temperature=0.9,
                    top_p=0.85,
                    max_tokens=4096,
                    parse_json=False,
                    response_format="text",
                    timeout=60
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
        """step=2 + confirm: 使用预制数据组合生成角色"""
        # 如果已经有了，直接展示
        if session.characters:
            custom_logger.info(f"Using cached characters for session {session.session_id}")
            return self._show_character_list(session)

        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")
        
        gender_text = "男性" if session.gender_preference == "male" else "女性"
        
        session.game_status = GameStatus.CHARACTER_SELECT
        self._update_session_db(session)

        # 使用预制数据生成角色
        characters = await self._generate_characters_from_preset(
            session.freak_world_id, gender_text, gm_name, count=3
        )
        
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
            world_id=self._format_world_id(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        char_name = selected_char.get("name", "角色")
        gender_text = "男性" if session.gender_preference == "male" else "女性"

        # 注入完整前序上下文（GM 引导 + 角色列表 + 选择）
        char_list_text = "\n".join([
            f"- {c.get('name')}（{c.get('race', '')}）：{c.get('appearance', '')}，{c.get('personality', '')}，{c.get('status', '')}"
            for c in characters
        ])

        gm_context = self._build_gm_context_messages(session, gender_text)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(gm_context)
        messages.extend([
            {"role": "user", "content": "我进入了这个世界，我能看到哪些人？"},
            {"role": "assistant", "content": f"你推开那扇门，在昏暗的光线中看到了几个身影：\n\n{char_list_text}\n\n你想和谁交谈？"},
            {"role": "user", "content": f"我选择和{char_name}交谈。"}
        ])

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen_plus"],
                parse_json=False,
                response_format="text",
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096,
                timeout=60
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
            world_id=self._format_world_id(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        history = self._get_dialogue_history(session.session_id) if session.session_id else []
        
        # 当 DB 无对话历史时，注入前序上下文（GM 引导 + 角色选择），避免 LLM 回退到 GM 阶段
        extra_context = None
        if not history and session.current_character_id:
            extra_context = self._build_playing_context(session)

        # 构建消息（包含剧情总结）
        messages = self._build_messages_with_summary(
            system_prompt=system_prompt,
            summary=session.dialogue_summary,
            history=history,
            user_message=message,
            extra_context=extra_context
        )

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen_plus"],
                parse_json=False,
                response_format="text",
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096,
                timeout=60
            )
            ai_content = self._clean_llm_content(response.get("content", ""))
        except Exception as e:
            custom_logger.error(f"LLM call failed: {e}")
            ai_content = "抱歉，系统暂时无法响应，请稍后再试。"

        # 异步触发总结生成（每15轮）
        self._trigger_summary_if_needed(session, history)

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
            world_id=self._format_world_id(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        history = self._get_dialogue_history(session.session_id) if session.session_id else []
        
        # 构建消息（包含剧情总结）
        messages = self._build_messages_with_summary(
            system_prompt=system_prompt,
            summary=session.dialogue_summary,
            history=history,
            user_message=self.SWITCH_KEY  # 换人密钥作为用户消息
        )

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen_plus"],
                parse_json=False,
                response_format="text",
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096,
                timeout=60
            )
            ai_content = self._clean_llm_content(response.get("content", ""))
        except Exception as e:
            custom_logger.error(f"LLM change_char call failed: {e}")
            ai_content = "换人请求失败，请稍后再试。"

        return self._build_response(content=ai_content)

    # ==================== 存档/读档 ====================

    def _get_save_slot(self, save_id: str) -> Optional[COCSaveSlot]:
        """根据 save_id 查询存档（复用 t_coc_save_slot 表）"""
        return self.db.query(COCSaveSlot).filter(
            and_(
                COCSaveSlot.save_id == save_id,
                COCSaveSlot.del_ == 0
            )
        ).first()

    def _create_save_slot(
        self, save_id: str, session: FreakWorldGameState, save_content: str
    ) -> COCSaveSlot:
        """将 IW 存档写入 t_coc_save_slot 表 (支持覆盖更新)

        字段复用策略：
        - save_id / session_id / user_id / gm_id / game_status: 通用字段
        - investigator_card: 存 IW 游戏状态（characters, current_character_id, gender_preference, world_id）
        - temp_data: 存 LLM 压缩的存档文本（iw_prompt_saving 格式）
        - round_number / turn_number: IW 不用，默认 0
        """
        # 检查是否已存在同名存档（用于覆盖更新）
        save_slot = self._get_save_slot(save_id)
        
        iw_game_state = {
            "type": "freak_world",
            "world_id": self._format_world_id(session.freak_world_id),
            "gender_preference": session.gender_preference,
            "current_character_id": session.current_character_id,
            "characters": session.characters,
        }

        if save_slot:
            # 更新现有存档
            save_slot.session_id = session.session_id
            save_slot.user_id = session.user_id
            save_slot.gm_id = session.gm_id
            save_slot.game_status = session.game_status
            save_slot.investigator_card = iw_game_state
            save_slot.temp_data = {"save_content": save_content}
            save_slot.del_ = 0  # 确保未删除
            custom_logger.info(f"Updating existing IW save slot: {save_id}")
        else:
            # 创建新存档
            save_slot = COCSaveSlot(
                save_id=save_id,
                session_id=session.session_id,
                user_id=session.user_id,
                gm_id=session.gm_id,
                game_status=session.game_status,
                investigator_card=iw_game_state,
                round_number=0,
                turn_number=0,
                temp_data={"save_content": save_content},
                del_=0
            )
            self.db.add(save_slot)
            custom_logger.info(f"Creating new IW save slot: {save_id}")

        try:
            self.db.commit()
            self.db.refresh(save_slot)
        except Exception as e:
            self.db.rollback()
            custom_logger.error(f"Failed to commit save slot: {e}")
            raise
            
        return save_slot

    async def _handle_save_action(self, request: IWChatRequest) -> Dict[str, Any]:
        """
        处理存档请求（extParam.action = "save"）

        1. 获取 saveId（前端传入）
        2. 调用 LLM 按 iw_prompt_saving 格式压缩对话
        3. 将压缩文本 + 游戏状态写入 t_coc_save_slot
        4. 返回存档确认
        """
        session = self._get_session_db(request.session_id)
        if not session:
            return self._error_response("会话不存在，无法存档")

        # 获取 saveId（前端/Java 层传入，可能是 int 或 str，统一转 str 匹配 VARCHAR 列）
        save_id = request.save_id
        if not save_id:
            ext_param = request.ext_param or {}
            save_id = ext_param.get("saveId") or ext_param.get("save_id")
        if save_id is not None:
            save_id = str(save_id).strip()
        if not save_id:
            return self._error_response("缺少存档ID（saveId），存档ID由前端传入")

        # 调用 LLM，用存档密钥触发 iw_prompt_saving 格式的压缩总结
        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=self._format_world_id(session.freak_world_id),
            is_loading=False,
            base_path=self.base_path
        )

        history = self._get_dialogue_history(session.session_id) if session.session_id else []
        
        # 如果 DB 无对话历史，注入前序上下文
        extra_context = None
        if not history and session.current_character_id:
            extra_context = self._build_playing_context(session)

        # 构建消息（包含剧情总结）
        messages = self._build_messages_with_summary(
            system_prompt=system_prompt,
            summary=session.dialogue_summary,
            history=history,
            user_message=self.SAVE_KEY,  # 存档密钥作为用户消息
            extra_context=extra_context
        )

        try:
            # 存档生成通常较慢，增加超时时间
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen_plus"],
                parse_json=False,
                response_format="text",
                timeout=60
            )
            save_content = response.get("content", "存档生成失败")
        except Exception as e:
            custom_logger.error(f"Save LLM call failed: {e}")
            save_content = "存档生成失败"

        # 写入存档表
        self._create_save_slot(save_id, session, save_content)

        gm_config = get_gm_config(session.gm_id)
        gm_name = gm_config.get("name", "GM")

        content = f"（{gm_name}为你记录下了这段旅程）\n\n存档已保存。"
        return self._build_response(content=content)

    async def _handle_load_action(self, request: IWChatRequest) -> Dict[str, Any]:
        """
        处理读档请求（extParam.action = "load"）

        1. 根据 saveId 查 t_coc_save_slot
        2. 创建新 session，恢复游戏状态
        3. 用存档中的 LLM 压缩文本 + iw_prompt_loading 调用 LLM 继续对话
        """
        ext_param = request.ext_param or {}
        save_id = ext_param.get("saveId") or ext_param.get("save_id") or request.save_id
        if save_id is not None:
            save_id = str(save_id).strip()
        if not save_id:
            return self._error_response("缺少存档ID（saveId）")

        # 查询存档
        save_slot = self._get_save_slot(save_id)
        if not save_slot:
            return self._error_response(f"未找到存档: {save_id}")

        # 从存档恢复游戏状态
        iw_state = save_slot.investigator_card or {}
        save_text_data = save_slot.temp_data or {}
        save_content = save_text_data.get("save_content", "")

        # 获取或创建会话（如果 session_id 已存在则复用，否则创建新的）
        world_id_str = iw_state.get("world_id", self._format_world_id(1))
        if request.session_id:
            session = self._get_session_db(request.session_id)
            if not session:
                session = self._create_session_db(
                    user_id=save_slot.user_id,
                    freak_world_id=self._parse_world_id(world_id_str),
                    gm_id=save_slot.gm_id,
                    session_id=request.session_id
                )
        else:
            session = self._create_session_db(
                user_id=save_slot.user_id,
                freak_world_id=self._parse_world_id(world_id_str),
                gm_id=save_slot.gm_id
            )

        # 恢复状态
        session.game_status = save_slot.game_status or GameStatus.PLAYING
        session.gender_preference = iw_state.get("gender_preference")
        session.current_character_id = iw_state.get("current_character_id")
        session.characters = iw_state.get("characters")
        self._update_session_db(session)

        # 用 loading prompt + 存档文本调用 LLM 继续
        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=self._format_world_id(session.freak_world_id),
            is_loading=True,
            base_path=self.base_path
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"【副本存档内容】\n{save_content}"}
        ]

        try:
            response = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen_plus"],
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

            # 提取文本内容用于模拟流式
            display_text = ""
            if isinstance(content, str):
                display_text = content
            elif isinstance(content, dict) and "description" in content:
                display_text = content["description"]

            if display_text:
                import asyncio
                chunk_size = 20
                for i in range(0, len(display_text), chunk_size):
                    yield {"type": "delta", "content": display_text[i:i + chunk_size]}
                    await asyncio.sleep(0.02) # 模拟流式打字

            yield {"type": "done", "complete": True, "result": response}

        except Exception as e:
            custom_logger.error(f"Error in IW stream_chat: {e}")
            self.db.rollback()
            yield {"type": "error", "complete": True, "message": str(e)}

    async def _stream_narrative(
        self, request: IWChatRequest, gender: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Step 1 世界叙事的真流式处理（注入 GM 引导上下文）"""
        try:
            session = self._get_or_create_session(request)

            session.gender_preference = gender
            session.game_status = GameStatus.NARRATIVE
            self._update_session_db(session)

            system_prompt = build_system_prompt(
                gm_id=session.gm_id,
                world_id=self._format_world_id(session.freak_world_id),
                is_loading=False,
                base_path=self.base_path
            )

            gender_text = "男性" if gender == "male" else "女性"

            # 注入 GM 引导对话上下文
            gm_context = self._build_gm_context_messages(session, gender_text)
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(gm_context)

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
            
            # --- 优化点 2: 尝试从叙事内容中异步预提取角色 ---
            # 这样在 step=2 点击 confirm 时，可能已经有现成的角色了
            asyncio.create_task(self._pre_extract_characters(session, cleaned))

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
                world_id=self._format_world_id(session.freak_world_id),
                is_loading=False,
                base_path=self.base_path
            )

            history = self._get_dialogue_history(session.session_id) if session.session_id else []
            
            # 当 DB 无对话历史时，注入前序上下文
            extra_context = None
            if not history and session.current_character_id:
                extra_context = self._build_playing_context(session)

            # 构建消息（包含剧情总结）
            messages = self._build_messages_with_summary(
                system_prompt=system_prompt,
                summary=session.dialogue_summary,
                history=history,
                user_message=message,
                extra_context=extra_context
            )

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

            # 异步触发总结生成（每15轮）
            self._trigger_summary_if_needed(session, history)

            cleaned = self._clean_llm_content(full_content)
            yield {"type": "done", "complete": True, "result": {"content": cleaned, "complete": False}}

        except Exception as e:
            custom_logger.error(f"Error in _stream_playing: {e}", exc_info=True)
            self.db.rollback()
            yield {"type": "error", "complete": True, "message": str(e)}

    async def _generate_characters_from_preset(
        self, world_id: str, gender: str, gm_name: str, count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        使用预制数据组合生成角色
        - race + appearance: 从预制表随机获取
        - gender + personality: 从预制表随机获取
        - name: 实时生成
        - status: 基于personality实时生成
        """
        from src.models.world_preset_data import WorldPresetDataManager
        
        try:
            # 初始化预制数据管理器
            preset_manager = WorldPresetDataManager(self.db)
            
            # 获取预制数据组合
            combinations = preset_manager.generate_character_combinations(
                self._format_world_id(world_id), gender, count
            )
            
            if not combinations:
                custom_logger.warning(f"No preset data found for world {world_id}, using fallback")
                # 使用默认数据
                return self._get_fallback_characters(gender, count)
            
            characters = []
            for combo in combinations:
                # 实时生成名字
                name = await self._generate_character_name(world_id, combo["race"])
                
                # 基于personality生成status
                status = await self._generate_character_status(combo["personality"])
                
                char = {
                    "name": name,
                    "gender": combo["gender"],
                    "race": combo["race"],
                    "appearance": combo["appearance"],
                    "personality": combo["personality"],
                    "status": status
                }
                characters.append(char)
            
            custom_logger.info(f"Generated {len(characters)} characters from preset data")
            return characters
            
        except Exception as e:
            custom_logger.error(f"Failed to generate characters from preset: {e}")
            return self._get_fallback_characters(gender, count)
    
    async def _generate_character_name(self, world_id: str, race: str) -> str:
        """实时生成角色名字"""
        try:
            prompt = f"""请为一位{race}生成一个合适的名字。
要求：
- 2-4个字
- 符合该种族/职业的气质
- 不要俗套的名字

只返回名字本身，不要任何其他内容。"""

            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen_turbo"],
                temperature=0.9,
                max_tokens=20,
                parse_json=False,
                timeout=10
            )
            
            name = response.get("content", "").strip()
            # 清理可能的引号或多余内容
            name = name.strip('"\'「」『』')
            
            if name and len(name) >= 2:
                return name
            else:
                return self._get_random_fallback_name()
                
        except Exception as e:
            custom_logger.error(f"Failed to generate name: {e}")
            return self._get_random_fallback_name()
    
    async def _generate_character_status(self, personality: str) -> str:
        """基于个性生成当前状态"""
        try:
            prompt = f"""这位角色的个性是：{personality}

请根据这个个性，描述TA当前的状态和心情（一句话，10-20字）。

只返回状态描述，不要任何其他内容。"""

            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model_pool=["qwen_turbo"],
                temperature=0.8,
                max_tokens=50,
                parse_json=False,
                timeout=10
            )
            
            status = response.get("content", "").strip()
            # 清理可能的引号
            status = status.strip('"\'')
            
            if status and len(status) >= 5:
                return status
            else:
                return "正在等待"
                
        except Exception as e:
            custom_logger.error(f"Failed to generate status: {e}")
            return "正在等待"
    
    def _get_fallback_characters(self, gender: str, count: int = 3) -> List[Dict[str, Any]]:
        """获取默认角色数据"""
        fallback_pool = [
            {"race": "血契贵族", "appearance": "银灰长发松挽，深红高开叉旗袍裹着冷艳曲线，指尖把玩着一柄血晶匕首。", "personality": "疏离而敏锐，言语如湖面涟漪般轻不可捉，却总能精准刺中他人未言之痛。"},
            {"race": "影息族", "appearance": "烟雾般的靛蓝轮廓倚在墙角，胸口能量核心幽幽发亮，耳后延伸出两根感知震颤的晶须。", "personality": "恪守逻辑却厌恶规则，用讽刺当盾、悖论为矛，在秩序废墟上栽种自己的正义。"},
            {"race": "血纹刻印师", "appearance": "苍白指尖沾满暗红颜料，颈侧蔓延着未完成的刺青，瞳孔深处藏着未愈合的旧伤。", "personality": "以沉默为甲、温柔为刃，在阴影里缝补他人裂痕，却从不允许自己被照亮。"},
            {"race": "时痕行者", "appearance": "灰蓝斗篷裹着瘦削身形，袖口露出半截机械义肢，左眼瞳孔呈现诡异的逆时针漩涡。", "personality": "表面玩世不恭，内心背负着无法言说的使命，在时间长河中寻找失落的真相。"},
            {"race": "灵能歌者", "appearance": "银白发丝间缠绕着发光藤蔓，耳垂悬挂着会随情绪变色的晶石，嗓音带着奇异的共鸣。", "personality": "用歌声编织梦境，在虚实之间游走，相信音乐是连接所有世界的唯一语言。"},
        ]
        
        import random
        selected = random.sample(fallback_pool, min(count, len(fallback_pool)))
        
        characters = []
        for combo in selected:
            char = {
                "name": self._get_random_fallback_name(),
                "gender": gender,
                "race": combo["race"],
                "appearance": combo["appearance"],
                "personality": combo["personality"],
                "status": "正在等待"
            }
            characters.append(char)
        
        return characters
    
    def _get_random_fallback_name(self) -> str:
        """获取随机默认名字"""
        import random
        names = ["艾德", "路德维希", "西蒙", "薇拉", "伊莎", "卡伦", "雷恩", "诺瓦", "塞拉", "维克多"]
        return random.choice(names)
