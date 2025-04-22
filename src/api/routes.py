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
model_names = ["siliconflow", "autodl", "qwen_plus", "autodl", "qwen_max", "autodl", "deepseek"]

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


def generate_prompt(character_id, user_id, db):
    if user_id != 'guest' and character_id == 'default':
        dq = DialogueQuery(db)
        conversation_history, nickname = dq.get_user_pillow_dialogue_history(user_id)
        user_history_exists = len(conversation_history) > 0
        custom_logger.info(f"User history exists: {user_history_exists}")
    elif user_id != 'guest' and character_id != 'default':
        dq = DialogueQuery(db)
        conversation_history, nickname = dq.get_user_third_character_dialogue_history(user_id, character_id)
        user_history_exists = len(conversation_history) > 0
        custom_logger.info(f"User third character history exists: {user_history_exists}")
    else:
        conversation_history = None
        user_history_exists = False
        nickname = "熟悉的人"
        custom_logger.info(f"User id is guest: {user_id} ")
    prompt, model_name = get_prompt_by_character_id(character_id, user_id, nickname)
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
            "top_p": 0.8,
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

async def generate_answer(prompt, messages, question, user_history_exists=False, model_name=None, retry=False, parse_retry_count=0):
    emotion_type = None
    if retry:
        model_name = random.choice(['qwen_plus', 'autodl', 'qwen-max'])
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
        raise HTTPException(status_code=404, detail=f"角色id不存在")

    try:
        # 准备请求数据
        request_data = {
            "model": model,
            "messages": api_messages,
            "stream": False,
            "max_tokens": 2048,
            "temperature": 0.9,
            "top_p": 0.95,
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
        max_parse_retries = 2
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


@router.post("/chat-pillow", response_model=ChatResponse)
async def chat_pillow(request: ChatRequest, db: Session = Depends(get_db)):
    custom_logger.info(f"Received chat request from user: {request.user_id}")
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
                                                                                    request.user_id, db)
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
            opener =await llm_generate_opener(opener, prompt, conversation_history, model_name)
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
