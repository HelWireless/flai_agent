import json

from fastapi import APIRouter, HTTPException, Depends
from src.schemas import *
from src.database import get_db
from src.dialogue_query import *
from sqlalchemy.orm import Session
from src.content_filter import *
from src.utils import get_emotion_type, split_message, upload_to_oss
from src.vector_query import VectorQuery
import yaml
from typing import List, Dict
import os
import uuid
from src.speech_api import SpeechAPI

from src.custom_logger import custom_logger  # 导入自定义logger
import random
import asyncio
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from functools import partial
from datetime import datetime
from src.api.prompts.character_other_info import *
from src.api.prompts.generate_prompts import *

router = APIRouter(
    prefix="/pillow",
    tags=["Chat"],  # router 按照 tags 进行分组
    responses={404: {"description": "Not found"}}
)

# 获取当前脚本的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 构建config.yaml的绝对路径
config_path = os.path.join(os.path.dirname(current_dir), "config.yaml")
# 加载配置
with open(config_path, "r", encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file)

# autdo model api 配置
model_names = ["autodl", "qwen_plus", "qwen3_32b_custom", "qwen_max", "autodl", "deepseek", "qwen3_32b_custom"]

# VectorQuery 配置
vector_db = VectorQuery(
    url=config["qdrant"]["url"],
    api_key=config["qdrant"]["api_key"],
    collection_name=config["qdrant"]["collection_name"],
    embedding_api_key=config["qdrant"]["embedding_api_key"]
)

cf = ContentFilter(additional_keywords=key_words)


# def get_embedding(text: str) -> List[float]:
#     custom_logger.info(f"Getting embedding for text: {text[:50]}...")
#     embedding = openai.Embedding.create(input=text, model=EMBEDDING_MODEL)["data"][0]["embedding"]
#     custom_logger.debug(f"Embedding generated successfully")
#     return embedding


def build_context(search_results: List[Dict]) -> str:
    custom_logger.info(f"Building context from {len(search_results)} search results")
    context = "\n".join([hit.payload["text"] for hit in search_results])
    custom_logger.debug(f"Context built: {context[:100]}...")
    return context


def create_retry_session(retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def generate_prompt(character_id, user_id, if_voice, db):
    ESM_type = None
    if user_id != 'guest' and character_id == 'default':
        dq = DialogueQuery(db)
        conversation_history, nickname = dq.get_user_pillow_dialogue_history(user_id, if_voice)
        user_history_exists = len(conversation_history) > 0
        if user_history_exists:
            ESM_type = analyze_ESM_from_history(conversation_history)
        custom_logger.info(f"User history exists: {user_history_exists}, and ESM type is {ESM_type} and character_id is {character_id}")
    elif user_id != 'guest' and character_id != 'default':
        dq = DialogueQuery(db)
        conversation_history, nickname = dq.get_user_third_character_dialogue_history(user_id, character_id)
        user_history_exists = len(conversation_history) > 0
        ESM_type = analyze_ESM_from_history(conversation_history)
        custom_logger.info(f"User third character history exists: {user_history_exists}, and ESM type is {ESM_type} and character_id is {character_id}")
    else:
        conversation_history = None
        user_history_exists = False
        ESM_type = None
        nickname = "熟悉的人"
        custom_logger.info(f"User id is guest: {user_id} and character_id is {character_id}")
    prompt, model_name = get_prompt_by_character_id(character_id, user_id, nickname, ESM_type)
    return prompt, conversation_history, user_history_exists, model_name


async def make_request(session, url, json_data, headers):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(session.post, url, json=json_data, headers=headers))


async def llm_generate_opener(openers, prompt, conversation_history, model_name=None, retry=False):
    # model api 配置
    api_base = config[model_name]["base_url"]
    model = config[model_name]["model"]
    api_key = config[model_name]["api_key"]
    api_messages = [{"role": "system", "content": prompt["system_prompt"]}]

    user_content = f"""
        <history>
        {conversation_history}
        </history>
        <openers>
        {openers}
        </openers>
    
    根据用户的history以及openers里提供的参考内容，生成2个新的开场白。开场白以json的格式返回，且仅返回json，其他不要返回，具体格式如下：
    {{
    "openers":[
            "学弟，这杯「月光微醺」是今晚的特别款，基酒用了最新的纳米活性金酒",
            "学弟，这杯「星梦迷离」是特别为你调制的（手指轻敲着水晶杯沿，眼神中闪过一丝狡黠）"
            ]
    }}
    """
    # 如果是重试或没有历史，只添加当前问题
    api_messages.append({"role": "user", "content": user_content})
    if "Character not found" in prompt["system_prompt"]:
        raise HTTPException(status_code=404, detail=f"角色id不存在")

    try:
        # 准备请求数据
        request_data = {
            "model": model,
            "messages": api_messages,
            "stream": False,
            "max_tokens": 2048,
            "temperature": 0.65,
            "top_p": 0.9,
        }

        headers = {
            f"Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        custom_logger.info(f"api_messages: {api_messages} \n retry:{retry}")
        # 创建一个带有重试机制的会话
        session = create_retry_session()

        # 发送POST请求到api_base
        response = await make_request(session, api_base, request_data, headers)
        if response.status_code != 200 or response.json().get("error", "") == 'API error':
            custom_logger.error(f"API request failed with status code {response.status_code}: {response.text}")
            if not retry:
                # 如果是第一次失败，进行重试
                custom_logger.info("Retrying without history messages")
                return await llm_generate_opener(openers, prompt, conversation_history, 'qwen_max', True)
            else:
                raise Exception(f"API request failed with status code {response.status_code}")

        # 解析响应
        response_data = response.json()
        answer = response_data['choices'][0]['message']['content']

        try:
            cleaned_result = answer.replace("```json\n", "").replace("\n```", "")
            answer_dict = json.loads(cleaned_result)
            print(answer_dict["openers"])
            answer = answer_dict["openers"]
        except Exception as e:
            answer = error_responses
            custom_logger.error(f"Error answer_dict: {str(e)}")
    except Exception as e:
        custom_logger.error(f"Error generating answer: {str(e)}")
        answer = error_responses
    return answer


async def generate_answer(prompt, messages, question, user_history_exists=False, model_name=None, retry=False,
                          parse_retry_count=0):
    emotion_type = None
    if retry:
        model_name = random.choice(['qwen_plus', 'autodl', 'qwen-max', 'qwen3_32b_custom'])
    else:
        if not model_name:
            model_name = random.choice(model_names)

    # model api 配置
    api_base = config[model_name]["base_url"]
    model = config[model_name]["model"]
    api_key = config[model_name]["api_key"]

    api_messages = [{"role": "system", "content": prompt["system_prompt"]}]
    user_content = prompt["user_prompt"].replace("query", question)
    # 如果不是重试且有历史消息，将其添加到 api_messages
    if not retry and user_history_exists:
        # api_messages.extend(messages)
        user_content = user_content.replace("history_chat", str(messages))
        api_messages.append({"role": "user", "content": user_content})
    else:
        user_content = user_content.replace("history_chat", "None")
        # 如果是重试或没有历史，只添加当前问题
        api_messages.append({"role": "user", "content": user_content})

    if "Character not found" in prompt["system_prompt"]:
        return HTTPException(status_code=404, detail=f"角色id不存在")

    try:
        # 准备请求数据
        request_data = {
            "model": model,
            "messages": api_messages,
            "stream": False,
            "max_tokens": 2048,
            "temperature": 0.9,
            "top_p": 0.85,
            "enable_thinking": False,
            "presence_penalty": 1.0,
            "response_format":{"type": "json_object"}
        }

        headers = {
            f"Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        custom_logger.info(f"api_messages: {api_messages} \n if_history:{user_history_exists} \n retry:{retry}")

        # 创建一个带有重试机制的会话
        session = create_retry_session()

        # 发送POST请求到api_base
        response = await make_request(session, api_base, request_data, headers)

        if response.status_code != 200 or response.json().get("error", "") == 'API error':
            custom_logger.error(f"API request failed with status code {response.status_code}: {response.text}")
            if not retry:
                # 如果是第一次失败，进行重试
                custom_logger.info("Retrying without history messages")
                return await generate_answer(prompt, [], question, False, None, True, parse_retry_count)
            else:
                raise Exception(f"API request failed with status code {response.status_code}")

        custom_logger.info(f"API response: {response.json()}")
        # 解析响应
        response_data = response.json()
        answer = response_data['choices'][0]['message']['content']

        # 新增解析重试逻辑
        max_parse_retries = 3
        answer_result = ""
        while parse_retry_count <= max_parse_retries:
            try:
                if "```json" in answer:
                    answer = answer.replace("```json\n", "").replace("\n```", "")
                answer_dict = json.loads(answer)
                emotion_type = answer_dict["emotion_type"]
                answer_result = answer_dict["answer"]
                break  # 解析成功则跳出循环
            except Exception as e:
                parse_retry_count += 1
                if parse_retry_count <= max_parse_retries:
                    custom_logger.warning(f"JSON解析失败，第{parse_retry_count}次重试...")
                    # 重新生成回答（保留历史但更换模型）
                    return await generate_answer(
                        prompt,
                        messages,
                        question,
                        user_history_exists,
                        model_name=None,  # 强制更换模型
                        retry=True,
                        parse_retry_count=parse_retry_count
                    )
                else:
                    answer_result = random.choice(error_responses)
                    custom_logger.error(f"最终JSON解析失败: {str(e)}")
                    break
        # 将 AI 的回答添加到 api_messages
        api_messages.append({"role": "assistant", "content": answer_result})
    except Exception as e:
        custom_logger.error(f"Error generating answer: {str(e)}")
        answer_result = random.choice(error_responses)
        api_messages.append({"role": "assistant", "content": answer_result})
    return answer_result, api_messages, emotion_type

def analyze_ESM_from_history(messages, model_name=None, retry=False, parse_retry_count=0):
    """
    分析用户历史对话的情绪类型

    Args:
        messages: 用户历史对话记录
        model_name: 使用的模型名称
        retry: 是否重试
        parse_retry_count: JSON解析重试次数

    Returns:
        emotion_type: 情绪类型
    """
    if retry:
        model_name = random.choice(['qwen_plus','qwen_max'])
    else:
        if not model_name:
            model_name = random.choice(['qwen_plus','qwen_max'])

    # model api 配置
    api_base = config[model_name]["base_url"]
    model = config[model_name]["model"]
    api_key = config[model_name]["api_key"]

    api_messages = [{"role": "system", "content": "你是一个优秀的情感分析专家"}]

    # 构建用户内容，包含历史对话
    user_content = f"""
    请根据以下对话历史分析用户的情绪状态状态，并只在以下emotion_list列表中选择一个，仅以以下JSON格式返回结果:
    emotion_list = [
    'happy', 
    'admiration', 
    'anger', 
    'sadness', 
    'fear', 
    'disgust', 
    'surprise', 
    'anxiety', 
    'neutral'
        ]
    
    {{
        "emotion_type": "emotion_list 的其中之一"
    }}
    
    对话历史:
    {str(messages)}
    
    请分析上述对话中用户的情绪状态，只需返回emotion_type字段。
    """

    api_messages.append({"role": "user", "content": user_content})

    try:
        # 准备请求数据
        request_data = {
            "model": model,
            "messages": api_messages,
            "stream": False,
            "max_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.8,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        custom_logger.info(f"Emotion analysis - api_messages: {api_messages} \n retry:{retry}")

        # 发送POST请求到api_base
        response = requests.post(api_base, json=request_data, headers=headers)

        if response.status_code != 200 or response.json().get("error", "") == 'API error':
            custom_logger.error(f"API request failed with status code {response.status_code}: {response.text}")
            if not retry:
                # 如果是第一次失败，进行重试
                custom_logger.info("Retrying emotion analysis")
                return analyze_ESM_from_history(messages, None, True, parse_retry_count)
            else:
                raise Exception(f"API request failed with status code {response.status_code}")

        # 解析响应
        response_data = response.json()
        answer = response_data['choices'][0]['message']['content']
        custom_logger.info(f"Emotion analysis API response: {response_data} and {answer}")

        # 解析JSON响应
        max_parse_retries = 3
        emotion_type = "neutral"  # 默认情绪类型
        while parse_retry_count <= max_parse_retries:
            try:
                if "json" in answer:
                    answer = answer.replace("\n", "").replace("\n", "")
                    answer_dict = json.loads(answer)
                    emotion_type = answer_dict.get("emotion_type", "neutral")
                    break  # 解析成功则跳出循环
                else:
                    answer_dict = json.loads(answer)
                    emotion_type = answer_dict["emotion_type"]
                    custom_logger.info(f"Emotion JSON parsing is: {str(emotion_type)}")
                    break
            except Exception as e:
                parse_retry_count += 1
                if parse_retry_count <= max_parse_retries:
                    custom_logger.warning(f"Emotion JSON parsing failed, retry {parse_retry_count}...")
                    return analyze_ESM_from_history(messages,
                                                    model_name=None,  # 强制更换模型
                                                    retry=True,
                                                    parse_retry_count=parse_retry_count)
                else:
                    custom_logger.error(f"Final Emotion JSON parsing failed: {str(e)}")
                    emotion_type = "neutral"
                    break
    except Exception as e:
        custom_logger.error(f"Error analyzing emotion: {str(e)}")
        emotion_type = "neutral"
    return emotion_type


@router.post("/chat-pillow", response_model=ChatResponse)
async def chat_pillow(request: ChatRequest, db: Session = Depends(get_db)):
    custom_logger.info(f"Received chat request from user: {request.user_id} \n if voice request: {request.voice}  ")
    if_voice = request.voice
    is_sensitive, sensitive_words = cf.detect_sensitive_content(request.message)
    if is_sensitive:
        custom_logger.warning(f"Sensitive content  detected: {sensitive_words}")
        # 随机选择一个预设回复
        answer = random.choice(SENSITIVE_RESPONSES)
        emotion_type = get_emotion_type(answer)

        return ChatResponse(
            user_id=request.user_id,
            llm_message=[answer],
            emotion_type=emotion_type
        )

    # query_embedding = get_embedding(request.message)
    # search_results = vector_db.search_similar(query_embedding, limit=5)
    # context = build_context(search_results)
    prompt, conversation_history, user_history_exists, model_name = generate_prompt(request.character_id,
                                                                                    request.user_id, if_voice, db)
    answer, api_messages, emotion_type = await generate_answer(
        prompt=prompt,
        messages=conversation_history,
        question=request.message,
        user_history_exists=user_history_exists,
        model_name=model_name
    )
    if answer not in error_responses:
        llm_messages = split_message(answer, request.message_count)
        custom_logger.debug(f"Split answer into {len(llm_messages)} messages")
    else:
        llm_messages = [answer]

    emotion_type_ind = get_emotion_type(answer, emotion_type)
    custom_logger.info(f"Emotion type detected: {emotion_type_ind}")

    return ChatResponse(
        user_id=request.user_id,
        llm_message=llm_messages,
        emotion_type=emotion_type_ind
    )


@router.post("/text2voice", response_model=Text2VoiceResponse)
async def text_to_voice(request: Text2Voice):
    custom_logger.info(f"Received text-to-voice request for user: {request.user_id}, text_id: {request.text_id}")
    speech_api = SpeechAPI(config["speech_api"], str(request.user_id))
    request_body = speech_api.generate_request_body(request.text)
    api_url = "https://openspeech.bytedance.com/api/v1/tts"
    voice_output_path = f"voice_tmp/{request.user_id}_{uuid.uuid4()}_{request.text_id}.mp3"
    os.makedirs(os.path.dirname(voice_output_path), exist_ok=True)

    try:
        speech_api.send_request(api_url, request_body, voice_output_path)
        custom_logger.info(f"Voice file generated: {voice_output_path}")
    except Exception as e:
        custom_logger.error(f"Failed to generate voice: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate voice: {str(e)}")

    file_key = upload_to_oss(voice_output_path, str(request.user_id))
    if not file_key:
        custom_logger.error("Failed to upload voice file to OSS")
        raise HTTPException(status_code=500, detail="Failed to upload voice file to OSS")

    voice_response_url = f"https://pillow.fanwoon.com/{file_key}"
    custom_logger.info(f"Voice file uploaded successfully: {voice_response_url}")

    return Text2VoiceResponse(user_id=int(request.user_id), text_id=int(request.text_id), url=voice_response_url)


@router.post("/character_opener", response_model=GenerateOpenerResponse)
async def generate_character_opener(request: GenerateOpenerRequest, db: Session = Depends(get_db)):
    custom_logger.info(
        f"Received character_opener request for character: {request.character_id}, index: {request.opener_index}"
        f"history:{request.history} user_id:{request.user_id}")

    # 获取角色开场白配置
    opener = characters_opener.get(request.character_id, None)

    # 1. 角色不存在处理
    if opener is None:
        custom_logger.error(f"Character {request.character_id} not found")
        raise HTTPException(status_code=404, detail=f"角色 {request.character_id} 不存在")

    # 2. 空列表处理
    if not opener:  # 检查是否是空列表
        custom_logger.error(f"Character {request.character_id} has empty opener list")
        raise HTTPException(status_code=404, detail=f"角色 {request.character_id} 未配置开场白")

    # 3. 索引范围校验
    if request.opener_index < 0 or request.opener_index > 4:
        custom_logger.error(f"Invalid opener index: {request.opener_index}")
        raise HTTPException(status_code=400, detail="开场白索引需在 0-4 内")

    if request.user_id != 'guest':
        # 获取对应信息
        prompt, conversation_history, user_history_exists, model_name = generate_prompt(request.character_id,
                                                                                        request.user_id, db)
        if request.history:
            opener = await llm_generate_opener(opener, prompt, conversation_history, model_name)
    # 4. 索引有效性检查
    try:
        selected_opener = opener[request.opener_index]
    except IndexError:
        max_index = len(opener) - 1
        custom_logger.error(f"Index {request.opener_index} exceeds max available index {max_index}")
        raise HTTPException(
            status_code=404,
            detail=f"当前角色仅支持 0-{max_index} 号开场白"
        )

    return GenerateOpenerResponse(opener=selected_opener)


@router.post("/draw-card", response_model=DrawCardResponse)
async def draw_card(request: DrawCardRequest):
    custom_logger.info(f"Received draw card request for user: {request.userId}")

    def get_random_color(color_map_dict):
        items = list(color_map_dict.items())
        color_name, hex_code = random.choice(items)
        return color_name, hex_code

    # 获取占卜师角色提示词
    if request.totalSummary:
        result_summary = request.totalSummary
        if not result_summary:
            return HTTPException(status_code=500, detail=f"字段缺失: {str(result_summary)}")
        system_prompt = character_sys_info.get("fortune_teller_detail", {}).get("sys_prompt", "")

        random_color_brief_list = color_descriptions_dict.get(result_summary.get("color"))
        random_color_brief = random.choice(random_color_brief_list)

        random_color_dict = {"color": result_summary.get("color"),
                             "hex": result_summary.get("hex"),
                             "colorBrief": random_color_brief,
                             "brief": result_summary.get("brief")
                             }
        user_content = f"""
                     {{  
                            "luckNum": {result_summary.get("luckNum")},
                            "luck": "{result_summary.get("luck")}",
                            "luckBrief": "",
                            "number": {result_summary.get("number")},
                            "numberBrief": "",
                            "action": "{result_summary.get("action")}",
                            "actionBrief": "",
                            "refreshment": "{result_summary.get("refreshment")}",
                            "refreshmentBrief": ""
                        }}
                """
    else:
        system_prompt = character_sys_info.get("fortune_teller_summary", {}).get("sys_prompt", "")

        unknown_place_one_list = character_sys_info.get("fortune_teller_summary", {}).get("unknown_place_one_list", "")
        unknown_place_one = random.choice(unknown_place_one_list)
        brief_list = character_sys_info.get("fortune_teller_summary", {}).get("brief", "")
        # 从列表中随机选择一个
        brief = random.choice(brief_list)
        brief = brief.replace("未知之地一", unknown_place_one)

        # 随机幸运数字和颜色
        # 生成12-30之间有1位小数的随机数
        raise_num = round(random.uniform(12, 30), 1)
        random_num = random.randint(1, 99)
        color_name, hex_code = get_random_color(color_map_dict)  # 修正：调用函数获取拼接值
        # 随机成0-5的整数，且0和5的概率较低，3的概率稍高1,2,和4
        luckNum = random.choices([0.0, 1.0, 2.0, 3.0, 4.0, 5.0], [0.06, 0.30, 0.25, 0.20, 0.15, 0.04])[0]
        brief = brief.replace("神秘数字", str(raise_num))

        random_color_dict = {"color": color_name,
                             "hex": hex_code,
                             "colorBrief": "",
                             "luckNum": luckNum,
                             "number": random_num,
                             "brief": brief
                             }
        # 构建用户输入
        user_content = f"""
            今天的幸运数字：{random_num}
        """

    if not system_prompt:
        return HTTPException(status_code=404, detail="角色配置不存在")
    model_id = "qwen_plus"

    api_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    try:
        # 准备请求数据
        request_data = {
            "model": config[model_id]["model"],
            "messages": api_messages,
            "stream": False,
            "max_tokens": 4096,
            "temperature": 0.65,
            "top_p": 0.8,
            "enable_thinking": False,
            "presence_penalty": 1.0,
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {config[model_id]['api_key']}",
            "Content-Type": "application/json"
        }

        session = create_retry_session()
        response = await make_request(session, config[model_id]["base_url"], request_data, headers)

        if response.status_code != 200 or response.json().get("error"):
            custom_logger.error(f"API request failed with status code {response.status_code}: {response.text}")
            return HTTPException(status_code=500, detail="调用大模型失败")

        response_data = response.json()
        answer = response_data['choices'][0]['message']['content']

        # 增加调试日志：输出原始回答内容
        custom_logger.debug(f"Raw model response content: {answer}")

        # 尝试解析为 JSON
        result_dict = json.loads(answer)
        result_dict.update(random_color_dict)
        # 检查result_dict结果是否符合DrawCardResponse要求，缺少某些字段，则补充对应字段，用“”来填充
        result_dict = {key: result_dict.get(key, "") for key in DrawCardResponse.__fields__.keys()}
        result_dict.update({"brief": result_dict["brief"].replace("未知之地二", result_dict["luck"])})
    except json.JSONDecodeError as je:
        custom_logger.error(f"JSON 解析失败，原始内容为: {answer}, 错误详情: {str(je)}")
        return HTTPException(status_code=500, detail=f"JSON 解析失败: {str(je)}")
    except Exception as e:
        custom_logger.error(f"Error generating card: {str(e)}")
        return HTTPException(status_code=500, detail=f"生成卡片失败: {str(e)}")

    return DrawCardResponse(**result_dict)
