"""
副本世界服务 - 处理文字副本游戏的核心业务逻辑
"""
import json
import uuid
import random
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..schemas import IWChatRequest, IWChatResponse
from ..models.instance_world import FreakWorldGameState, FreakWorldDialogue
from ..custom_logger import custom_logger
from .llm_service import LLMService
from .instance_world_prompts import (
    build_system_prompt, get_gm_config, get_world_config,
    get_gm_ids, get_enabled_gms,
    get_iw_prompt_saving, get_json_format_instruction
)


# step 常量定义
# GM 由用户提前选择（gmId 参数），step 0 为游戏角色选择
class GameStep:
    CHAR_SELECT = "0"    # 角色选择阶段（用户选择游戏中的角色）
    PLAYING = "1"        # 游戏进行中
    ENDED = "2"          # 游戏正常结束
    DEATH = "3"          # 角色死亡


class FreakWorldService:
    """副本世界业务服务"""
    
    # 存档触发密钥
    SAVE_KEY = "73829104碧鹿孽心0109要去坐标BBT进行退出并存档"
    # 换人密钥（换游戏角色，不是换GM）
    SWITCH_KEY = "73829104核子松鼠0114在哈尔滨错过0117皇上的婚礼所以需要更换交谈角色"
    
    def __init__(self, llm_service: LLMService, db: Session, config: Dict):
        """
        初始化副本世界服务
        
        Args:
            llm_service: LLM 服务
            db: 数据库会话
            config: 应用配置
        """
        self.llm = llm_service
        self.db = db
        self.config = config
        
        # 获取项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_path = os.path.dirname(os.path.dirname(current_dir))
    
    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        return f"fw_{uuid.uuid4().hex[:16]}"
    
    def _generate_save_id(self) -> str:
        """生成存档 ID"""
        return f"save_{uuid.uuid4().hex[:12]}"
    
    def _get_random_gm_id(self) -> str:
        """随机选择一个 GM"""
        gm_ids = get_gm_ids()
        return random.choice(gm_ids) if gm_ids else "gm_default"
    
    def _step_to_game_status(self, step: str) -> str:
        """将 step 转换为内部 game_status"""
        mapping = {
            GameStep.CHAR_SELECT: "character_select",
            GameStep.PLAYING: "playing",
            GameStep.ENDED: "ended",
            GameStep.DEATH: "death"
        }
        return mapping.get(step, "playing")
    
    def _game_status_to_step(self, game_status: str) -> str:
        """将内部 game_status 转换为 step"""
        mapping = {
            "gm_intro": GameStep.CHAR_SELECT,        # GM开场 → step 0
            "world_intro": GameStep.CHAR_SELECT,     # 世界介绍 → step 0
            "character_select": GameStep.CHAR_SELECT, # 角色选择 → step 0
            "playing": GameStep.PLAYING,             # 游戏中 → step 1
            "ended": GameStep.ENDED,                 # 结束 → step 2
            "death": GameStep.DEATH                  # 死亡 → step 3
        }
        return mapping.get(game_status, GameStep.PLAYING)
    
    # ==================== 数据库操作 ====================
    
    def _create_session_db(
        self,
        account_id: int,
        freak_world_id: int,
        gm_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> FreakWorldGameState:
        """创建新游戏状态（数据库）
        
        Args:
            account_id: 用户ID
            freak_world_id: 世界ID
            gm_id: GM ID
            session_id: 会话ID（可选，不传则自动生成）
        """
        session = FreakWorldGameState(
            session_id=session_id or self._generate_session_id(),
            account_id=account_id,
            freak_world_id=freak_world_id,
            gm_id=gm_id or self._get_random_gm_id(),
            game_status="gm_intro",
            del_=0
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        custom_logger.info(f"Created new FW game state in DB: {session.session_id}")
        return session
    
    def _get_session_db(self, session_id: str) -> Optional[FreakWorldGameState]:
        """获取会话（数据库）"""
        return self.db.query(FreakWorldGameState).filter(
            FreakWorldGameState.session_id == session_id
        ).first()
    
    def _update_session_db(self, session: FreakWorldGameState):
        """更新会话（数据库）"""
        self.db.commit()
        self.db.refresh(session)
    
    def _get_dialogue_history_db(self, session_id: int) -> List[Dict[str, str]]:
        """
        获取对话历史（从 t_freak_world_dialogue 只读）
        
        Args:
            session_id: 对话会话 ID (int 类型，对应 t_freak_world_dialogue.session_id)
        
        Returns:
            LLM messages 格式的对话历史列表
        """
        dialogues = self.db.query(FreakWorldDialogue).filter(
            and_(
                FreakWorldDialogue.session_id == session_id,
                FreakWorldDialogue.del_ == 0
            )
        ).order_by(FreakWorldDialogue.create_time.asc()).all()
        
        # 将每条记录的 message+response 转换为两条 LLM 消息
        messages = []
        for d in dialogues:
            messages.extend(d.to_messages())
        return messages
    
    # ==================== 辅助方法 ====================
    
    def _build_response(
        self,
        session: FreakWorldGameState,
        content: str,
        complete: bool = False,
        save_id: Optional[str] = None,
        ext_data: Optional[Dict] = None
    ) -> IWChatResponse:
        """构建响应"""
        return IWChatResponse(
            session_id=session.session_id,
            gm_id=session.gm_id or "0",
            step=self._game_status_to_step(session.game_status),
            content=content,
            complete=complete,
            save_id=save_id,
            ext_data=ext_data
        )
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 响应
        
        文字副本返回纯 markdown，不再解析 JSON
        """
        import re
        
        # 清理可能的代码块标记
        if "```json" in content:
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'\s*```', '', content)
        elif "```" in content:
            # 保留 markdown 代码块，只清理 JSON 包装
            pass
        
        content = content.strip()
        
        # 尝试解析 JSON 提取 content 字段（兼容旧格式）
        try:
            if content.startswith('{') and content.endswith('}'):
                parsed = json.loads(content)
                return {
                    "content": parsed.get("content", content),
                    "step": parsed.get("step", parsed.get("game_status", "playing")),
                    "complete": parsed.get("complete", False),
                    "ext_data": parsed.get("ext_data", None)
                }
        except (json.JSONDecodeError, Exception):
            pass
        
        # 纯 markdown 内容
        return {
            "content": content,
            "step": "playing",
            "complete": False,
            "ext_data": None
        }
    
    async def _call_llm(
        self,
        session: FreakWorldGameState,
        user_message: str,
        is_loading: bool = False,
        save_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        调用 LLM 生成响应
        
        Args:
            session: 会话
            user_message: 用户消息
            is_loading: 是否为加载存档模式
            save_data: 存档数据（加载时使用）
        
        Returns:
            解析后的 LLM 响应
        """
        # 构建系统提示词
        system_prompt = build_system_prompt(
            gm_id=session.gm_id,
            world_id=session.freak_world_id,
            is_loading=is_loading,
            base_path=self.base_path
        )
        
        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        
        # 从数据库获取对话历史
        dialogue_history = self._get_dialogue_history_db(session.session_id)
        for msg in dialogue_history:
            messages.append(msg)
        
        # 如果是加载存档，将存档内容作为第一条用户消息
        if is_loading and save_data:
            save_content = json.dumps(save_data, ensure_ascii=False, indent=2)
            messages.append({
                "role": "user",
                "content": f"【副本存档内容】\n{save_content}"
            })
        
        # 添加当前用户消息
        if user_message:
            messages.append({"role": "user", "content": user_message})
        
        custom_logger.info(f"Calling LLM for session {session.session_id}, messages count: {len(messages)}")
        
        try:
            # 调用 LLM
            result = await self.llm.chat_completion(
                messages=messages,
                model_pool=["qwen3_32b_custom", "qwen_max", "deepseek"],
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096,
                response_format="json_object",
                parse_json=False,  # 我们自己解析
                retry_on_error=True
            )
            
            content = result.get("content", "")
            return self._parse_llm_response(content)
            
        except Exception as e:
            custom_logger.error(f"LLM call failed: {e}")
            return {
                "content": "抱歉，系统暂时无法响应，请稍后再试。",
                "selection_type": "none",
                "selections": [],
                "game_status": "playing"
            }
    
    # ==================== 业务方法 ====================
    
    async def start_new_game(self, request: IWChatRequest) -> IWChatResponse:
        """
        开始新游戏
        
        GM 由后端自动分配，用户选择的是游戏角色
        
        Args:
            request: 请求
        
        Returns:
            响应
        """
        # GM 由后端分配：如果传入了 gm_id 就用，否则随机分配
        gm_id = request.gm_id if request.gm_id and request.gm_id != "0" else self._get_random_gm_id()
        
        # 创建新游戏状态（数据库）
        session = self._create_session_db(
            account_id=int(request.user_id),
            freak_world_id=int(request.world_id) if request.world_id.isdigit() else 1,
            gm_id=gm_id
        )
        
        # 初始状态：角色选择阶段（step=0），GM 已分配
        session.game_status = "character_select"
        self._update_session_db(session)
        
        # 调用 LLM 生成 GM 开场白和角色选择提示
        llm_response = await self._call_llm(session, "")
        
        return self._build_response(
            session,
            content=llm_response.get("content", ""),
            complete=llm_response.get("complete", False)
        )
    
    async def continue_chat(self, request: IWChatRequest) -> IWChatResponse:
        """
        继续对话
        
        Args:
            request: 请求
        
        Returns:
            响应
        """
        session = self._get_session_db(request.session_id)
        if not session:
            custom_logger.error(f"Session not found: {request.session_id}")
            # 如果会话不存在，创建新会话
            return await self.start_new_game(request)
        
        # 检查游戏是否已结束
        if session.game_status in ["ended", "death"]:
            return self._build_response(
                session,
                content="游戏已结束，请开始新的副本。",
                complete=True
            )
        
        # 正常对话（包括角色选择阶段的交互）
        llm_response = await self._call_llm(session, request.message)
        
        # 检查是否游戏结束
        new_step = llm_response.get("step", "playing")
        if new_step in ["ended", "death", GameStep.ENDED, GameStep.DEATH]:
            session.game_status = "ended" if new_step in ["ended", GameStep.ENDED] else "death"
            self._update_session_db(session)
        
        return self._build_response(
            session,
            content=llm_response.get("content", ""),
            complete=llm_response.get("complete", False),
            ext_data=llm_response.get("ext_data")
        )
    
    async def save_game(self, request: IWChatRequest) -> IWChatResponse:
        """
        保存游戏（通过 saveId 有值触发）
        
        Args:
            request: 请求
        
        Returns:
            响应（包含存档 ID）
        """
        session = self._get_session_db(request.session_id)
        if not session:
            custom_logger.error(f"Session not found for save: {request.session_id}")
            return IWChatResponse(
                session_id=request.session_id or "",
                gm_id="0",
                step=GameStep.CHAR_SELECT,
                content="会话不存在，无法保存。",
                complete=True
            )
        
        # 调用 LLM 生成存档内容
        llm_response = await self._call_llm(session, self.SAVE_KEY)
        save_content = llm_response.get("content", "")
        
        # 生成存档 ID
        save_id = self._generate_save_id()
        
        # 存档数据包含 GM 信息，读档时恢复
        ext_data = {
            "save_data": {
                "save_id": save_id,
                "session_id": session.session_id,
                "account_id": session.account_id,
                "world_id": session.freak_world_id,
                "gm_id": session.gm_id,  # 保存 GM 信息
                "game_status": session.game_status,
                "current_character_id": session.current_character_id,
                "created_at": datetime.now().isoformat()
            }
        }
        
        custom_logger.info(f"Generated save data: {save_id}, gm_id: {session.gm_id}")
        
        return self._build_response(
            session,
            content=save_content,
            complete=False,
            save_id=save_id,
            ext_data=ext_data
        )
    
    async def load_game(self, request: IWChatRequest) -> IWChatResponse:
        """
        加载存档（通过 saveId 有值触发）
        
        Args:
            request: 请求（需要 save_id）
        
        Returns:
            响应
        """
        if not request.save_id:
            return IWChatResponse(
                session_id="",
                gm_id="0",
                step=GameStep.CHAR_SELECT,
                content="未指定存档 ID。",
                complete=True
            )
        
        # 从 extParam 获取存档数据（由 Java 传入）
        save_data = request.ext_param.get("save_data") if request.ext_param else None
        
        if save_data:
            # 有存档数据，恢复游戏
            gm_id = save_data.get("gm_id", "0")
            
            # 创建新会话并恢复状态
            session = self._create_session_db(
                account_id=int(request.user_id),
                freak_world_id=int(save_data.get("world_id", request.world_id)),
                gm_id=gm_id
            )
            session.game_status = save_data.get("game_status", "playing")
            session.current_character_id = save_data.get("current_character_id")
            self._update_session_db(session)
            
            # 调用 LLM 恢复游戏
            llm_response = await self._call_llm(session, "", is_loading=True, save_data=save_data)
            
            return self._build_response(
                session,
                content=llm_response.get("content", f"存档加载成功，继续你的冒险。\n\n{save_data.get('save_content', '')}"),
                complete=False
            )
        
        # 没有存档数据，提示通过 Java 接口加载
        custom_logger.warning(f"Load game request for save_id={request.save_id}, no save_data in extParam")
        
        return IWChatResponse(
            session_id="",
            gm_id="0",
            step=GameStep.CHAR_SELECT,
            content="请通过存档接口获取存档数据后再加载。",
            complete=True,
            save_id=request.save_id
        )
    
    async def process_request(self, request: IWChatRequest) -> IWChatResponse:
        """
        处理请求（入口方法 - 同步模式）
        
        根据请求状态分发到不同的处理方法
        
        Args:
            request: 请求
        
        Returns:
            响应
        """
        custom_logger.info(
            f"Processing IW request: user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, step={request.step}"
        )
        
        try:
            # 有 saveId 则为读档
            if request.save_id:
                return await self.load_game(request)
            
            # 有 session_id 则继续对话
            if request.session_id:
                return await self.continue_chat(request)
            
            # 否则开始新游戏
            return await self.start_new_game(request)
            
        except Exception as e:
            custom_logger.error(f"Error processing IW request: {e}")
            self.db.rollback()
            return IWChatResponse(
                session_id=request.session_id or "",
                gm_id=request.gm_id or "0",
                step=request.step or GameStep.CHAR_SELECT,
                content=f"处理请求时发生错误：{str(e)}",
                complete=True
            )
    
    async def stream_chat(
        self,
        request: IWChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式对话（SSE 模式）
        
        GM 由后端自动分配，用户选择的是游戏角色
        
        Args:
            request: 请求
        
        Yields:
            SSE 事件数据:
            - {"type": "delta", "content": "部分文本"}
            - {"type": "done", "complete": true, "result": {...}}
            - {"type": "error", "complete": true, "message": "错误信息"}
        """
        custom_logger.info(
            f"Stream IW request: user={request.user_id}, "
            f"session={request.session_id}, gm_id={request.gm_id}, step={request.step}"
        )
        
        try:
            # 处理读档请求 - 不需要流式
            if request.save_id:
                response = await self.load_game(request)
                yield {"type": "done", "complete": True, "result": self._response_to_dict(response)}
                return
            
            # 获取或创建会话
            session = None
            is_new_game = False
            
            if request.session_id:
                session = self._get_session_db(request.session_id)
            
            if not session:
                # 创建新游戏状态，使用传入的 session_id
                gm_id = request.gm_id if request.gm_id and request.gm_id != "0" else self._get_random_gm_id()
                session = self._create_session_db(
                    account_id=int(request.user_id),
                    freak_world_id=int(request.world_id) if request.world_id.isdigit() else 1,
                    gm_id=gm_id,
                    session_id=request.session_id if request.session_id else None
                )
                session.game_status = "character_select"  # 初始状态：角色选择
                self._update_session_db(session)
                is_new_game = True
            else:
                # 检查游戏是否已结束
                if session.game_status in ["ended", "death"]:
                    yield {
                        "type": "done",
                        "complete": True,
                        "result": self._response_to_dict(self._build_response(
                            session,
                            content="游戏已结束，请开始新的副本。",
                            complete=True
                        ))
                    }
                    return
            
            # 构建系统提示词
            system_prompt = build_system_prompt(
                gm_id=session.gm_id,
                world_id=session.freak_world_id,
                is_loading=False,
                base_path=self.base_path
            )
            
            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]
            
            # 添加对话历史
            dialogue_history = self._get_dialogue_history_db(session.session_id)
            for msg in dialogue_history:
                messages.append(msg)
            
            # 如果不是新游戏开始，添加用户消息
            if not is_new_game and request.message:
                messages.append({"role": "user", "content": request.message})
            
            # 流式调用 LLM
            full_content = ""
            
            async for chunk in self.llm.stream_chat_completion(
                messages=messages,
                model_pool=["qwen3_32b_custom", "qwen_max", "deepseek"],
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096
            ):
                if chunk["type"] == "delta":
                    full_content += chunk["content"]
                    yield chunk
                
                elif chunk["type"] == "error":
                    yield {"type": "error", "complete": True, "message": chunk.get("message", "Unknown error")}
                    return
                
                elif chunk["type"] == "done":
                    full_content = chunk.get("content", full_content)
            
            # 解析 LLM 响应
            parsed_response = self._parse_llm_response(full_content)
            content = parsed_response.get("content", full_content)
            is_complete = parsed_response.get("complete", False)
            
            # 检查是否游戏结束
            new_step = parsed_response.get("step", "playing")
            if new_step in ["ended", "death", GameStep.ENDED, GameStep.DEATH]:
                session.game_status = "ended" if new_step in ["ended", GameStep.ENDED] else "death"
                self._update_session_db(session)
                is_complete = True
            
            # 返回最终结果
            yield {
                "type": "done",
                "complete": True,
                "result": self._response_to_dict(self._build_response(
                    session,
                    content=content,
                    complete=is_complete,
                    ext_data=parsed_response.get("ext_data")
                ))
            }
            
        except Exception as e:
            custom_logger.error(f"Error in stream_chat: {e}")
            self.db.rollback()
            yield {
                "type": "error",
                "complete": True,
                "message": str(e)
            }
    
    def _response_to_dict(self, response: IWChatResponse) -> dict:
        """将 IWChatResponse 转换为字典"""
        return {
            "sessionId": response.session_id,
            "gmId": response.gm_id,
            "step": response.step,
            "content": response.content,
            "complete": response.complete,
            "saveId": response.save_id,
            "extData": response.ext_data
        }
