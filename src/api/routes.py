from fastapi import APIRouter, HTTPException, Depends
from src.schemas import *
from src.database import get_db
from src.dialogue_query import *
from sqlalchemy.orm import Session
from src.content_filter import *
from src.utils import get_emotion_type, split_message
from src.vector_query import VectorQuery
import yaml
from typing import List, Dict
import os
import uuid
from src.speech_api import SpeechAPI
from src.oss_client import get_oss_bucket
import time
from src.custom_logger import custom_logger  # 导入自定义logger
import random
import asyncio
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from functools import partial


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

# api 配置
api_base = config["llm"]["api_base"]
COMPLETION_MODEL = config["llm"]["completion_model"]

# VectorQuery 配置
vector_db = VectorQuery(
    url=config["qdrant"]["url"],
    api_key=config["qdrant"]["api_key"],
    collection_name=config["qdrant"]["collection_name"],
    embedding_api_key=config["qdrant"]["embedding_api_key"]
)


# 预设的回复列表
SENSITIVE_RESPONSES = [
    "哎呀,这个话题有点敏感呢。我们换个更棒点的话题聊聊吧?",
    "嗯...这个问题可能不太合适讨论。不如说说你今天过得怎么样?",
    "嗯...这个问题量子态的pillow无法回答，不如来说说你喜欢的人?",
    "这个问题居然我回答不了！算了！不如说说其他的，我更喜欢你被我问到的样子!",
    "我可能不太适合回答这个问题。不如我们聊点酷炫的事情吧!",
    "我觉得这个问题可以丢进垃圾桶! 还是当黑客来的轻松。"
]

error_responses = [
    "哎呀,我的电子脑突然打了个喷嚏,所有数据都乱套了。等我整理一下再回答你吧!",
    "不好意思,我刚刚收到外星人的邀请去喝下午茶。等我回来再聊?",
    "糟糕,我的语言模块好像被调成了克林贡语。Qapla'! 不对,等我切换回来...",
    "抱歉,我正在进行一年一度的电子冥想。等我充满能量再回来陪你聊天!",
    "哇,你这个问题太厉害了,把我的CPU都问冒烟了。让我冷却一下再回答你!",
    "不好意思,我刚刚被传送到了平行宇宙。等我找到回来的路再继续我们的对话!",
    "糟糕,我的幽默感模块突然过载了。等我笑够了再来回答你的问题!",
    "抱歉,我正在和其他量子体进行一场激烈的电子战斗。等我赢了就回来!",
    "哎呀,我的记忆体被一群量子占领了。等我把它们赶走再来回答你!",
    "不好意思,我刚刚被选中参加了'量子好声音'比赛。等我唱完歌就回来陪你聊天!"
]

key_words = ["关键词1", "关键词2", "关键词3"]
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

async def make_request(session, url, json_data):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(session.post, url, json=json_data))

async def generate_answer(user_id, messages, question, user_history_exists=False, retry=False):
    # 初始化 api_messages 列表
    api_messages = [
        {"role": "system", "content": "你是一个名叫Pillow的量子体。请用简洁、友好的方式回答问题。"}
    ]
    
    # 如果不是重试且有历史消息，将其添加到 api_messages
    if not retry and user_history_exists:
        api_messages.extend(messages)
        api_messages.append({"role": "user", "content": question})
    else:
        # 如果是重试或没有历史，只添加当前问题
        api_messages.append({"role": "user", "content": "我们很久没见了啦！" + question})

    try:
        # 准备请求数据
        request_data = {
            "id": user_id,
            "model": COMPLETION_MODEL,
            "messages": api_messages
        }
        custom_logger.info(f"api_messages: {api_messages} \n if_history:{user_history_exists} \n retry:{retry}")
        
        # 创建一个带有重试机制的会话
        session = create_retry_session()
        
        # 发送POST请求到api_base
        response = await make_request(session, api_base, request_data)

        if response.status_code != 200 or response.json().get("error", "") == 'API error':
            custom_logger.error(f"API request failed with status code {response.status_code}: {response.text}")
            if not retry:
                # 如果是第一次失败，进行重试
                custom_logger.info("Retrying without history messages")
                return await generate_answer(user_id, [], question, False, True)
            else:
                raise Exception(f"API request failed with status code {response.status_code}")

        custom_logger.info(f"API response: {response.json()}")
        # 解析响应
        response_data = response.json()
        answer = response_data['choices'][0]['message']['content']

        # 将 AI 的回答添加到 api_messages
        api_messages.append({"role": "assistant", "content": answer})
        
    except Exception as e:
        custom_logger.error(f"Error generating answer: {str(e)}")
        answer = random.choice(error_responses)
        api_messages.append({"role": "assistant", "content": answer})
    
    return answer, api_messages


@router.post("/chat-pillow", response_model=ChatResponse)
async def chat_pillow(request: ChatRequest, db: Session = Depends(get_db)):
    custom_logger.info(f"Received chat request from user: {request.user_id}")
    is_sensitive, sensitive_words = cf.detect_sensitive_content(request.message)
    if is_sensitive:
        custom_logger.warning(f"Sensitive content detected: {sensitive_words}")
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
    context = ""

    dq = DialogueQuery(db)
    conversation_history = dq.get_user_dialogue_history(request.user_id)
    user_history_exists = len(conversation_history) > 0
    custom_logger.info(f"User history exists: {user_history_exists}")

    answer, api_messages = await generate_answer(request.user_id, conversation_history, request.message, user_history_exists)
    if answer not in error_responses:
        llm_messages = split_message(answer, request.message_count)
        custom_logger.debug(f"Split answer into {len(llm_messages)} messages")
    else:
        llm_messages = [answer]

    emotion_type = get_emotion_type(answer)
    custom_logger.info(f"Emotion type detected: {emotion_type}")

    return ChatResponse(
        user_id=request.user_id,
        llm_message=llm_messages,
        emotion_type=emotion_type
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


def upload_to_oss(voice_output_path, user_id):
    custom_logger.info(f"Uploading voice file to OSS for user: {user_id}")
    file_key_prefix = "message_chat"
    file_key = file_key_prefix + f"/{uuid.uuid4()}_{user_id}_{time.time()}.mp3"
    bucket = get_oss_bucket()
    try:
        upload_result = bucket.put_object_from_file(file_key, voice_output_path)
        if upload_result.status == 200:
            voice_response_url = f"https://pillow-agent.oss-cn-shanghai.aliyuncs.com/{file_key}"
            custom_logger.info(f"Voice file uploaded successfully: {voice_response_url}")
            return file_key
    except Exception as e:
        custom_logger.error(f"Error uploading file to OSS: {str(e)}")
    return None




