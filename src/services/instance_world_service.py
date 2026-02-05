"""
异世界服务 - 处理异世界文字游戏的核心业务逻辑
"""
import json
import uuid
import random
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..schemas import (
    IWChatRequest, IWChatResponse, IWSession, 
    IWGameState, IWSelection
)
from ..models.instance_world import FreakWorldGameState, FreakWorldDialogue
from ..custom_logger import custom_logger
from .llm_service import LLMService
from .instance_world_prompts import (
    build_system_prompt, get_gm_config, get_world_config,
    get_gm_ids, get_enabled_gms,
    get_iw_prompt_saving, get_json_format_instruction
)


class FreakWorldService:
    """异世界业务服务"""
    
    # 存档触发密钥
    SAVE_KEY = "73829104碧鹿孽心0109要去坐标BBT进行退出并存档"
    # 换人密钥
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
        return random.choice(gm_ids) if gm_ids else "01"
    
    # ==================== 数据库操作 ====================
    
    def _create_session_db(
        self,
        account_id: int,
        freak_world_id: int,
        gm_id: Optional[str] = None
    ) -> FreakWorldGameState:
        """创建新游戏状态（数据库）"""
        session = FreakWorldGameState(
            session_id=self._generate_session_id(),
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
    
    def _build_game_state(self, session: FreakWorldGameState) -> IWGameState:
        """构建游戏状态响应"""
        return IWGameState(
            session_id=session.session_id,
            world_id=str(session.freak_world_id),
            gm_id=session.gm_id,
            game_status=session.game_status,
            current_character_id=session.current_character_id
        )
    
    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 响应
        
        尝试解析 JSON，如果失败则将内容包装为默认格式
        """
        import re
        
        try:
            # 清理可能的代码块标记
            if "```json" in content:
                content = re.sub(r'```json\s*', '', content)
                content = re.sub(r'\s*```', '', content)
            elif "```" in content:
                content = re.sub(r'```\s*', '', content)
            
            content = content.strip()
            
            # 尝试直接解析
            if content.startswith('{') and content.endswith('}'):
                return json.loads(content)
            
            # 尝试提取 JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # 解析失败，返回默认格式
            return {
                "content": content,
                "selection_type": "none",
                "selections": [],
                "game_status": "playing"
            }
            
        except Exception as e:
            custom_logger.warning(f"Failed to parse LLM response: {e}")
            return {
                "content": content,
                "selection_type": "none",
                "selections": [],
                "game_status": "playing"
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
        
        Args:
            request: 请求
        
        Returns:
            响应
        """
        # 创建新游戏状态（数据库）
        session = self._create_session_db(
            account_id=int(request.user_id),
            freak_world_id=int(request.world_id),
            gm_id=request.gm_id
        )
        
        # 调用 LLM 生成 GM 开场白
        llm_response = await self._call_llm(session, "")
        
        # 对话记录由 Java 后端保存到 t_freak_world_dialogue，此处不写入
        
        # 构建响应
        selections = [
            IWSelection(id=s.get("id", str(i)), text=s.get("text", ""))
            for i, s in enumerate(llm_response.get("selections", []))
        ]
        
        return IWChatResponse(
            session_id=session.session_id,
            content=llm_response.get("content", ""),
            selection_type=llm_response.get("selection_type", "none"),
            selections=selections,
            game_state=self._build_game_state(session)
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
            return IWChatResponse(
                session_id=session.session_id,
                content="游戏已结束，请开始新的副本。",
                selection_type="none",
                selections=[],
                game_state=self._build_game_state(session)
            )
        
        # 检查是否切换 GM
        if request.gm_id and request.gm_id != session.gm_id:
            session.gm_id = request.gm_id
            self._update_session_db(session)
            custom_logger.info(f"Switched GM to {request.gm_id}")
        
        # 对话记录由 Java 后端保存到 t_freak_world_dialogue，此处不写入
        
        # 调用 LLM
        llm_response = await self._call_llm(session, request.message)
        
        # 更新游戏状态
        new_game_status = llm_response.get("game_status", llm_response.get("game_state", "playing"))
        if new_game_status in ["ended", "death"]:
            session.game_status = new_game_status
            self._update_session_db(session)
        
        # 构建响应
        selections = [
            IWSelection(id=s.get("id", str(i)), text=s.get("text", ""))
            for i, s in enumerate(llm_response.get("selections", []))
        ]
        
        return IWChatResponse(
            session_id=session.session_id,
            content=llm_response.get("content", ""),
            selection_type=llm_response.get("selection_type", "none"),
            selections=selections,
            game_state=self._build_game_state(session)
        )
    
    async def save_game(self, request: IWChatRequest) -> IWChatResponse:
        """
        保存游戏
        
        发送存档密钥给 LLM，让它生成存档内容
        
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
                content="会话不存在，无法保存。",
                selection_type="none",
                selections=[],
                game_state=IWGameState(
                    session_id="",
                    world_id=request.world_id,
                    gm_id="",
                    game_status="error"
                )
            )
        
        # 对话记录由 Java 后端保存到 t_freak_world_dialogue，此处不写入
        
        # 调用 LLM 生成存档内容
        llm_response = await self._call_llm(session, self.SAVE_KEY)
        save_content = llm_response.get("content", "")
        
        # 生成存档 ID
        save_id = self._generate_save_id()
        
        # 构建存档数据 (返回给调用方，由 Java 写入 t_freak_world_save_slot)
        save_data = {
            "save_id": save_id,
            "session_id": session.session_id,
            "account_id": session.account_id,
            "freak_world_id": session.freak_world_id,
            "gm_id": session.gm_id,
            "game_status": session.game_status,
            "current_character_id": session.current_character_id,
            "gender_preference": session.gender_preference,
            "characters": session.characters,
            "save_content": save_content,
            "created_at": datetime.now().isoformat()
        }
        
        # 存档由 Java 管理 (t_freak_world_save_slot)，这里只返回存档数据
        custom_logger.info(f"Generated save data: {save_id}")
        
        return IWChatResponse(
            session_id=session.session_id,
            content=save_content,
            selection_type="none",
            selections=[],
            game_state=self._build_game_state(session),
            save_id=save_id
        )
    
    async def load_game(self, request: IWChatRequest) -> IWChatResponse:
        """
        加载存档
        
        Args:
            request: 请求（需要 save_id）
        
        Returns:
            响应
        """
        if not request.save_id:
            return IWChatResponse(
                session_id="",
                content="未指定存档 ID。",
                selection_type="none",
                selections=[],
                game_state=IWGameState(
                    session_id="",
                    world_id=request.world_id,
                    gm_id="",
                    game_status="error"
                )
            )
        
        # 存档由 Java 管理 (t_freak_world_save_slot)
        # 这里返回错误提示，加载功能需要通过 Java 接口实现
        custom_logger.warning(f"Load game request for save_id={request.save_id}, but save management is handled by Java")
        
        return IWChatResponse(
            session_id="",
            content="存档加载功能由 Java 服务管理，请通过 Java 接口加载。",
            selection_type="none",
            selections=[],
            game_state=IWGameState(
                session_id="",
                world_id=request.world_id,
                gm_id="",
                game_status="error"
            ),
            save_id=request.save_id
        )
    
    async def process_request(self, request: IWChatRequest) -> IWChatResponse:
        """
        处理请求（入口方法）
        
        根据 action 分发到不同的处理方法
        
        Args:
            request: 请求
        
        Returns:
            响应
        """
        custom_logger.info(
            f"Processing IW request: user={request.user_id}, "
            f"session={request.session_id}, action={request.action}"
        )
        
        try:
            if request.action == "save":
                return await self.save_game(request)
            elif request.action == "load":
                return await self.load_game(request)
            elif request.session_id:
                return await self.continue_chat(request)
            else:
                return await self.start_new_game(request)
        except Exception as e:
            custom_logger.error(f"Error processing IW request: {e}")
            # 回滚数据库事务
            self.db.rollback()
            return IWChatResponse(
                session_id=request.session_id or "",
                content=f"处理请求时发生错误：{str(e)}",
                selection_type="none",
                selections=[],
                game_state=IWGameState(
                    session_id=request.session_id or "",
                    world_id=request.world_id,
                    gm_id="",
                    game_status="error"
                )
            )
    
    async def stream_chat(
        self,
        request: IWChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式对话（真正的 SSE 直通）
        
        Args:
            request: 请求
        
        Yields:
            SSE 事件数据:
            - {"type": "delta", "content": "部分文本"}
            - {"type": "done", "result": {...}}
            - {"type": "error", "message": "错误信息"}
        """
        custom_logger.info(
            f"Stream IW request: user={request.user_id}, "
            f"session={request.session_id}, action={request.action}"
        )
        
        try:
            # 处理特殊操作（存档/加载）- 这些不需要流式
            if request.action == "save":
                response = await self.save_game(request)
                yield {"type": "done", "complete": True, "result": self._response_to_dict(response)}
                return
            
            if request.action == "load":
                response = await self.load_game(request)
                yield {"type": "done", "complete": True, "result": self._response_to_dict(response)}
                return
            
            # 获取或创建会话
            session = None
            is_new_game = False
            
            if request.session_id:
                session = self._get_session_db(request.session_id)
            
            if not session:
                # 创建新游戏状态
                session = self._create_session_db(
                    account_id=int(request.user_id),
                    freak_world_id=int(request.world_id),
                    gm_id=request.gm_id
                )
                is_new_game = True
            else:
                # 检查游戏是否已结束
                if session.game_status in ["ended", "death"]:
                    yield {
                        "type": "done",
                        "complete": True,
                        "result": {
                            "session_id": session.session_id,
                            "content": "游戏已结束，请开始新的副本。",
                            "selection_type": "none",
                            "selections": [],
                            "game_state": self._game_state_to_dict(session),
                            "save_id": None
                        }
                    }
                    return
                
                # 检查是否切换 GM
                if request.gm_id and request.gm_id != session.gm_id:
                    session.gm_id = request.gm_id
                    self._update_session_db(session)
                
                # 对话记录由 Java 后端保存到 t_freak_world_dialogue，此处不写入
            
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
            
            # 如果是新游戏，不添加用户消息
            if not is_new_game and request.message:
                messages.append({"role": "user", "content": request.message})
            
            # 流式调用 LLM
            full_content = ""
            
            async for chunk in self.llm.stream_chat_completion(
                messages=messages,
                model_pool=["qwen3_32b_custom", "qwen_max", "deepseek"],
                temperature=0.9,
                top_p=0.85,
                max_tokens=4096,
                response_format="json_object"
            ):
                if chunk["type"] == "delta":
                    full_content += chunk["content"]
                    yield chunk
                
                elif chunk["type"] == "error":
                    yield chunk
                    return
                
                elif chunk["type"] == "done":
                    full_content = chunk.get("content", full_content)
            
            # 解析 LLM 响应
            parsed_response = self._parse_llm_response(full_content)
            content = parsed_response.get("content", full_content)
            selection_type = parsed_response.get("selection_type", "none")
            selections = parsed_response.get("selections", [])
            new_game_status = parsed_response.get("game_status", parsed_response.get("game_state", "playing"))
            
            # 更新游戏状态
            if new_game_status in ["ended", "death"]:
                session.game_status = new_game_status
                self._update_session_db(session)
            
            # 对话记录由 Java 后端保存到 t_freak_world_dialogue，此处不写入
            
            # 返回最终结果
            yield {
                "type": "done",
                "complete": True,
                "result": {
                    "session_id": session.session_id,
                    "content": content,
                    "selection_type": selection_type,
                    "selections": selections,
                    "game_state": self._game_state_to_dict(session),
                    "save_id": None
                }
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
            "session_id": response.session_id,
            "content": response.content,
            "selection_type": response.selection_type,
            "selections": [{"id": s.id, "text": s.text} for s in response.selections],
            "game_state": {
                "session_id": response.game_state.session_id,
                "world_id": response.game_state.world_id,
                "gm_id": response.game_state.gm_id,
                "game_status": response.game_state.game_status,
                "current_character_id": response.game_state.current_character_id
            },
            "save_id": response.save_id
        }
    
    def _game_state_to_dict(self, session: FreakWorldGameState) -> dict:
        """将会话的游戏状态转换为字典"""
        return {
            "session_id": session.session_id,
            "world_id": str(session.freak_world_id),
            "gm_id": session.gm_id,
            "game_status": session.game_status,
            "current_character_id": session.current_character_id
        }
