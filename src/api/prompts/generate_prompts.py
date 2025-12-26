"""
Prompt 生成模块 - 使用JSON配置
"""
from datetime import datetime
from typing import Dict, Any, Tuple
from src.core.config_loader import get_config_loader


def get_prompt_by_character_id(character_id: str, user_id: str = 'guest', 
                               nickname: str = "熟悉的人", EMS_type: str = None,
                               user_prompt_type: str = "return_json_prompt") -> Tuple[Dict[str, str], str]:
    """
    根据角色ID获取对应的prompt配置
    
    Args:
        character_id: 角色ID
        user_id: 用户ID
        nickname: 用户昵称
        EMS_type: 情绪类型
        user_prompt_type: 用户prompt类型
    
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
        system_prompt = character_sys_info.get(character_id, "{'info':'Character not found'}")
        system_prompt = json_module.dumps(system_prompt, ensure_ascii=False, indent=4)
        model_id = "qwen_max"
    
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
                            
                            ** 请仅输出JSON结构，不要输出任何其他内容 ** 
                         """,
        "return_answer_prompt": """
                            请沉浸在你的角色中，基于之前的对话历史生成回复。
                            """
    }
    
    user_prompt = character_user_info.get(user_prompt_type, "Character not found")
    character_prompt = {"system_prompt": system_prompt, "user_prompt": user_prompt}
    
    return character_prompt, model_id