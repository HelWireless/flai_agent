"""
Prompt 生成模块 - 使用JSON配置
"""
from datetime import datetime
from typing import Dict, Any, Tuple
from src.core.config_loader import get_config_loader


def get_prompt_by_character_id(character_id: str, user_id: str = 'guest', 
                               nickname: str = "熟悉的人", EMS_type: str = None,
                               user_prompt_type: str = "return_json_prompt",
                               virtual_id: int = 0) -> Tuple[Dict[str, str], str]:
    """
    根据角色ID获取对应的prompt配置
    
    Args:
        character_id: 角色ID
        user_id: 用户ID
        nickname: 用户昵称
        EMS_type: 情绪类型
        user_prompt_type: 用户prompt类型
        virtual_id: 虚拟身份卡ID，0表示用户自己，>0表示扮演对应身份卡人物
    
    Returns:
        (character_prompt, model_id): prompt字典和模型ID
    """
    loader = get_config_loader()
    
    # 获取配置
    characters_config = loader.get_characters()
    emotion_states_config = loader.get_emotion_states()
    
    character_sys_info = characters_config.get('characters', {})
    ESM_dict = emotion_states_config
    world_background = characters_config.get('world_background', '')
    guidance = characters_config.get('guidance', '')
    
    # 获取当前时间并直接格式化，精确到秒
    now = datetime.now()
    formatted_time = now.strftime("%Y年%m月%d日 %H点%M分%S秒")
    
    if character_id == "default":
        if user_id == 'guest':
            system_prompt = character_sys_info["default"].get("guest_prompt", "Character not found")
        else:
            system_prompt = character_sys_info["default"].get("user_prompt", "Character not found")
        
        system_prompt = system_prompt.replace("formatted_time", formatted_time)
        system_prompt = system_prompt.replace("nickname", nickname)
        
        if EMS_type:
            system_prompt = system_prompt.replace("{emotion_type}",
                                                  ESM_dict.get(EMS_type, {}).get("emotion_type", ""))
            system_prompt = system_prompt.replace("{emotion_description}",
                                                  ESM_dict.get(EMS_type, {}).get("emotion_description", ""))
            system_prompt = system_prompt.replace("{emotion_reaction}",
                                                  ESM_dict.get(EMS_type, {}).get("emotion_reaction", ""))
            system_prompt = system_prompt.replace("{emotion_prompt}",
                                                  ESM_dict.get(EMS_type, {}).get("emotion_prompt", ""))
        
        model_id = None
    else:
        import json as json_module
        # 首先尝试从正常缓存中获取
        system_prompt = character_sys_info.get(character_id)
        # 如果没有找到，尝试强制刷新配置
        if system_prompt is None:
            characters_config = loader.get_characters(reload=True)
            character_sys_info = characters_config.get('characters', {})
            system_prompt = character_sys_info.get(character_id)
        
        # 如果仍然没有找到，抛出异常或返回错误信息
        if system_prompt is None:
            # 返回一个有意义的错误信息，让调用方知道角色不存在
            # 这样可以在chat_service中进行适当处理
            system_prompt = f"{{\"error\":\"角色ID {character_id} 不存在，请检查ID是否正确\"}}"
            model_id = None  # 角色不存在时使用默认模型
        else:
            # 在序列化为JSON之前检查是否有指定的模型ID
            model_id = system_prompt.get('model_id') or None
            # 将角色配置序列化为JSON字符串
            import json as json_module
            system_prompt = json_module.dumps(system_prompt, ensure_ascii=False, indent=4)
    
    # 如果有虚拟身份卡，注入身份背景到 system_prompt
    if virtual_id and str(virtual_id) != "0":
        from src.services.identity_card_service import build_identity_prompt
        identity_prompt = build_identity_prompt(virtual_id)
        if identity_prompt:
            system_prompt = system_prompt + identity_prompt
    
    # 构建用户prompt配置
    character_user_info = {
        "return_json_prompt": """
                            请沉浸在你的角色中，基于之前的对话历史生成回复，并以JSON格式返回结果。
                            请参考以下JSON格式示例：
                            ```json
                            {
                            "emotion_type":  "开心",   // 你当前的情绪，从以下选项中选择：["开心","期待","生气","伤心","惊恐","害羞","抱抱","无语","其他"]
                            "answer": "好的，我现在好开心呀~！"          // 你对问题的回答
                            }
                            ```
                            
                            ** 请仅输出JSON格式，不要输出任何其他内容 ** 
                         """,
        "return_answer_prompt": """
                            请沉浸在你的角色中，基于之前的对话历史生成回复。
                            """
    }
    
    user_prompt = character_user_info.get(user_prompt_type, "Character not found")
    character_prompt = {"system_prompt": system_prompt, "user_prompt": user_prompt}
    
    return character_prompt, model_id