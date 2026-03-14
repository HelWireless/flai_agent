"""
占卜服务 - 处理占卜抽卡相关的业务逻辑
"""
import json
import random
from typing import Dict, Optional

from fastapi import HTTPException

from ..schemas import DrawCardRequest, DrawCardResponse
from ..custom_logger import custom_logger
from ..core.config_loader import get_config_loader
from .llm_service import LLMService


class FortuneService:
    """占卜业务服务"""
    
    def __init__(self, llm_service: LLMService, config: Dict, config_loader):
        """
        初始化占卜服务
        
        Args:
            llm_service: LLM服务
            config: 应用配置
            config_loader: 配置加载器
        """
        self.llm = llm_service
        self.config = config
        self.config_loader = config_loader
        
        # 加载常量配置
        constants = config_loader.get_constants()
        self.color_map_dict = constants.get('color_map', {})
        self.color_descriptions_dict = constants.get('color_descriptions_dict', {})
        # 加载动作和小食列表
        self.action_list = constants.get('action_list', [])
        self.refreshment_list = constants.get('refreshment_list', [])
        
        # 加载角色配置
        characters = config_loader.get_characters()
        self.character_sys_info = characters.get('characters', {})
    
    def _get_random_color(self) -> tuple:
        """
        获取随机颜色
        
        Returns:
            (颜色名称, 颜色代码)
        """
        items = list(self.color_map_dict.items())
        color_name, hex_code = random.choice(items)
        return color_name, hex_code
    
    async def generate_card(self, request: DrawCardRequest) -> DrawCardResponse:
        """
        生成占卜卡片
        
        Args:
            request: 抽卡请求
        
        Returns:
            卡片响应
        """
        custom_logger.info(f"[draw-card] Generating card for user: {request.user_id}")
        
        # 区分是详细模式还是摘要模式
        if request.totalSummary:
            custom_logger.info("[draw-card] Request type: Detailed card generation")
            return await self._generate_detail_card(request.totalSummary)
        else:
            custom_logger.info("[draw-card] Request type: Summary card generation")
            return await self._generate_summary_card()

    async def _generate_detail_card(self, total_summary: Dict) -> DrawCardResponse:
        """
        生成详细占卜卡片（基于已有摘要）
        
        Args:
            total_summary: 摘要信息
        
        Returns:
            详细卡片
        """
        custom_logger.info("[draw-card:detail] Starting detailed card generation")
        
        if not total_summary:
            raise HTTPException(status_code=500, detail="字段缺失")
        
        # 获取占卜师提示词
        system_prompt = self.character_sys_info.get("fortune_teller_detail", {}).get("sys_prompt", "")
        if not system_prompt:
            raise HTTPException(status_code=404, detail="占卜师配置不存在")
        
        # 获取颜色描述
        color = total_summary.get("color")
        custom_logger.info(f"[draw-card:detail] Color from summary: {color}")
        random_color_brief_list = self.color_descriptions_dict.get(color, [""])
        custom_logger.info(f"[draw-card:detail] Color descriptions available: {len(self.color_descriptions_dict)}")
        custom_logger.info(f"[draw-card:detail] Color brief options: {random_color_brief_list}")
        random_color_brief = random.choice(random_color_brief_list) if random_color_brief_list else ""
        
        custom_logger.info(f"[draw-card:detail] Selected color brief: {random_color_brief}")
        
        # 构建更简化的用户输入 (只包含需要AI生成的部分)
        user_content = f"""
根据以下信息生成详细占卜解读：
运势: {total_summary.get("luck")}
幸运数字: {total_summary.get("number")}
转运动作: {total_summary.get("action")}
幸运小食: {total_summary.get("refreshment")}

请严格按照以下JSON格式返回结果：
{{
    "luckBrief": "运势解读",
    "numberBrief": "数字解读",
    "actionBrief": "动作解读",
    "refreshmentBrief": "小食解读"
}}

注意：只返回JSON格式内容，不要有任何其他解释或文本。
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            # 调用 LLM，使用更强大的模型
            custom_logger.info("[draw-card:detail] LLM request to qwen_max: 2 messages")
            result = await self.llm.chat_completion(
                messages=messages,
                model_name="qwen_max",
                temperature=0.7,
                top_p=0.9,
                max_tokens=2048,
                response_format="json_object",
                parse_json=True,
                retry_on_error=False
            )
            custom_logger.info("[draw-card:detail] LLM response received from qwen_max")
            
            # 检查返回结果是否有效
            if not result or not isinstance(result, dict):
                custom_logger.error("[draw-card:detail] Invalid response format from LLM")
                # 创建默认响应以避免失败
                result = {
                    "luckBrief": "今天将是特殊的一天",
                    "numberBrief": f"数字{total_summary.get('number')}蕴含着特殊能量",
                    "actionBrief": f"尝试'{total_summary.get('action')}'来改善运势",
                    "refreshmentBrief": f"享用'{total_summary.get('refreshment')}'增加好运"
                }
            
            # 补充可以直接获取的信息
            result.update({
                "color": color,
                "hex": total_summary.get("hex"),
                "colorBrief": random_color_brief,
                "brief": total_summary.get("brief", "").replace("未知之地二", total_summary.get("luck", "")),
                "luckNum": total_summary.get("luckNum"),
                "luck": total_summary.get("luck"),
                "number": total_summary.get("number"),
                "action": total_summary.get("action"),
                "refreshment": total_summary.get("refreshment")
            })
            
            # 补充缺失字段
            result = {key: result.get(key, "") for key in DrawCardResponse.__fields__.keys()}
            
            custom_logger.info("[draw-card:detail] Card generation completed successfully")
            return DrawCardResponse(**result)
            
        except Exception as e:
            custom_logger.error(f"[draw-card:detail] Error generating detail card: {str(e)}")
            # 即使在异常情况下也返回一个默认的有效响应
            try:
                default_result = {
                    "luck": total_summary.get("luck", ""),
                    "luckNum": total_summary.get("luckNum", 0.0),
                    "luckBrief": "今天将会是特别的一天",
                    "number": total_summary.get("number", 0),
                    "numberBrief": f"数字{total_summary.get('number', 0)}将为你带来特殊能量",
                    "color": color,
                    "hex": total_summary.get("hex", ""),
                    "colorBrief": random_color_brief,
                    "action": total_summary.get("action", ""),
                    "actionBrief": f"尝试'{total_summary.get('action', '')}'来改善运势",
                    "refreshment": total_summary.get("refreshment", ""),
                    "refreshmentBrief": f"享用'{total_summary.get('refreshment', '')}'增加好运",
                    "brief": total_summary.get("brief", "")
                }
                return DrawCardResponse(**default_result)
            except Exception as fallback_error:
                custom_logger.error(f"[draw-card:detail] Error generating fallback response: {str(fallback_error)}")
                raise HTTPException(status_code=500, detail=f"生成卡片失败: {str(e)}")

    async def _generate_summary_card(self) -> DrawCardResponse:
        """
        生成摘要占卜卡片
        
        Returns:
            摘要卡片
        """
        custom_logger.info("[draw-card:summary] Starting summary card generation")
        
        # 随机选择动作和小食
        random_action = random.choice(self.action_list)
        random_refreshment = random.choice(self.refreshment_list)
        
        custom_logger.info(f"[draw-card:summary] Selected action: {random_action}")
        custom_logger.info(f"[draw-card:summary] Selected refreshment: {random_refreshment}")
        
        # 获取占卜师提示词
        fortune_config = self.character_sys_info.get("fortune_teller_summary", {})
        system_prompt = fortune_config.get("sys_prompt", "")
        
        if not system_prompt:
            raise HTTPException(status_code=404, detail="占卜师配置不存在")
        
        # 生成随机参数
        unknown_place_one_list = fortune_config.get("unknown_place_one_list", [""])
        unknown_place_one = random.choice(unknown_place_one_list) if unknown_place_one_list else ""
        
        brief_list = fortune_config.get("brief", [""])
        brief = random.choice(brief_list) if brief_list else ""
        brief = brief.replace("未知之地一", unknown_place_one)
        
        # 生成随机数据
        raise_num = round(random.uniform(12, 30), 1)
        random_num = random.randint(1, 99)
        brief = brief.replace("神秘数字", str(raise_num))
        
        # 获取随机颜色
        color_name, hex_code = self._get_random_color()
        custom_logger.info(f"[draw-card:summary] Selected color: {color_name}, hex: {hex_code}")
        
        # 随机幸运值（0-5，概率分布不均）
        luckNum = random.choices(
            [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], 
            [0.10, 0.15, 0.25, 0.25, 0.15, 0.10]
        )[0]
        
        # 构建用户输入，明确要求JSON格式
        user_content = f"""
            今天的幸运数字：{random_num}
            转运的关键动作：{random_action}
            强运的日常小食：{random_refreshment}
            
            请严格按照以下JSON格式返回结果：
            {{
                "luck": "运势状态（四个字）",
                "number": {random_num},
                "action": "{random_action}",
                "refreshment": "{random_refreshment}"
            }}
            
            注意：只返回JSON格式内容，不要有任何其他解释或文本。
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            # 调用 LLM，使用更强大的模型
            custom_logger.info("[draw-card:summary] LLM request to qwen_max: 2 messages")
            result = await self.llm.chat_completion(
                messages=messages,
                model_name="qwen_max",
                temperature=0.65,
                top_p=0.8,
                max_tokens=4096,
                response_format="json_object",
                parse_json=True,
                retry_on_error=False
            )
            custom_logger.info("[draw-card:summary] LLM response received from qwen_max")
            
            # 检查返回结果是否有效
            if not result or not isinstance(result, dict):
                custom_logger.error("[draw-card:summary] Invalid response format from LLM")
                # 创建默认响应以避免失败
                result = {
                    "luck": "未知运势",
                    "number": random_num,
                    "action": random_action,
                    "refreshment": random_refreshment
                }
            
            # 确保 result 是字典类型，而不是列表或字符串
            if isinstance(result, list):
                # 如果是列表，取第一个元素或者创建空字典
                result = result[0] if result else {}
            elif isinstance(result, str):
                # 如果是字符串，尝试解析为JSON
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    custom_logger.error("[draw-card:summary] Failed to parse LLM response as JSON")
                    result = {
                        "luck": "未知运势",
                        "number": random_num,
                        "action": random_action,
                        "refreshment": random_refreshment
                    }
            
            # 补充基础信息
            result.update({
                "color": color_name,
                "hex": hex_code,
                "colorBrief": "",
                "luckNum": luckNum,
                "number": random_num,
                "brief": brief,
                "action": random_action,
                "refreshment": random_refreshment
            })
            
            # 补充缺失字段
            result = {key: result.get(key, "") for key in DrawCardResponse.__fields__.keys()}
            
            custom_logger.info("[draw-card:summary] Card generation completed successfully")
            return DrawCardResponse(**result)
            
        except Exception as e:
            custom_logger.error(f"[draw-card:summary] Error generating summary card: {str(e)}")
            # 即使在异常情况下也返回一个默认的有效响应
            try:
                default_result = {
                    "luck": "平稳运势",
                    "luckNum": luckNum,
                    "luckBrief": "今天将会是平稳的一天",
                    "number": random_num,
                    "numberBrief": f"数字{random_num}将为你带来稳定能量",
                    "color": color_name,
                    "hex": hex_code,
                    "colorBrief": "",
                    "action": random_action,
                    "actionBrief": f"尝试'{random_action}'来改善运势",
                    "refreshment": random_refreshment,
                    "refreshmentBrief": f"享用'{random_refreshment}'增加好运",
                    "brief": brief
                }
                return DrawCardResponse(**default_result)
            except Exception as fallback_error:
                custom_logger.error(f"[draw-card:summary] Error generating fallback response: {str(fallback_error)}")
                raise HTTPException(status_code=500, detail=f"生成卡片失败: {str(e)}")
