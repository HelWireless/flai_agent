from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas import *
from database import get_db
from dialogue_query import get_user_dialogue_history
import openai
from content_filter import content_filter
from utils import get_emotion_type, check_assistant_repetition, split_message
from vector_query import VectorQuery
import yaml
from typing import List, Dict
import os
import uuid
from speech_api import SpeechAPI
from oss_client import get_oss_bucket
import time
from custom_logger import custom_logger  # 导入自定义logger


router = APIRouter(
    prefix="/pillow",
    tags=["Chat"],  # router 按照 tags 进行分组
    responses={404: {"description": "Not found"}}
)

# 加载配置
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# OpenAI 配置
openai.api_key = config["openai"]["api_key"]
EMBEDDING_MODEL = config["openai"]["embedding_model"]
COMPLETION_MODEL = config["openai"]["completion_model"]

# VectorQuery 配置
vector_db = VectorQuery(
    url=config["qdrant"]["url"],
    api_key=config["qdrant"]["api_key"],
    collection_name=config["qdrant"]["collection_name"]
)

def get_embedding(text: str) -> List[float]:
    custom_logger.info(f"Getting embedding for text: {text[:50]}...")
    embedding = openai.Embedding.create(input=text, model=EMBEDDING_MODEL)["data"][0]["embedding"]
    custom_logger.debug(f"Embedding generated successfully")
    return embedding

def build_context(search_results: List[Dict]) -> str:
    custom_logger.info(f"Building context from {len(search_results)} search results")
    context = "\n".join([hit.payload["text"] for hit in search_results])
    custom_logger.debug(f"Context built: {context[:100]}...")
    return context

def generate_answer(context: str, question: str, messages: list, user_history_exists: bool) -> str:
    custom_logger.info(f"Generating answer for question: {question}")
    is_repetitive, repeated_sentence = check_assistant_repetition(messages)
    
    if is_repetitive:
        custom_logger.warning(f"Repetitive answer detected: {repeated_sentence}")
        new_system_prompt = f"You are a helpful assistant. Use the following context to answer the user's question. Avoid repeating this sentence: '{repeated_sentence}'"
    else:
        new_system_prompt = "You are a helpful assistant. Use the following context to answer the user's question."
    
    if not user_history_exists:
        custom_logger.info("No recent user history found")
        new_system_prompt += " 最近一周没有见过你。"

    messages = [
        {"role": "system", "content": new_system_prompt},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
    ] + messages

    response = openai.ChatCompletion.create(
        model=COMPLETION_MODEL,
        messages=messages
    )
    answer = response.choices[0].message.content
    custom_logger.info(f"Answer generated: {answer[:100]}...")
    return answer

@router.post("/chat-pillow", response_model=ChatResponse)
async def chat_pillow(request: ChatRequest, db: Session = Depends(get_db)):
    custom_logger.info(f"Received chat request from user: {request.user_id}")
    
    is_sensitive, sensitive_words = content_filter.detect_sensitive_content(request.message)
    if is_sensitive:
        custom_logger.warning(f"Sensitive content detected: {sensitive_words}")
        raise HTTPException(status_code=400, detail="Query contains sensitive content")
    
    query_embedding = get_embedding(request.message)
    search_results = vector_db.search_similar(query_embedding, limit=5)
    context = build_context(search_results)
    
    conversation_history = get_user_dialogue_history(db, request.user_id)
    user_history_exists = len(conversation_history) > 0
    custom_logger.info(f"User history exists: {user_history_exists}")

    answer = generate_answer(context, request.message, conversation_history, user_history_exists)

    llm_messages = split_message(answer, request.message_count)
    custom_logger.debug(f"Split answer into {len(llm_messages)} messages")

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
    
    config_path = 'src/config.yaml'
    speech_api = SpeechAPI(config_path, request.user_id)
    
    request_body = speech_api.generate_request_body(request.text)
    
    api_url = "https://openspeech.bytedance.com/api/v1/tts"
    voice_output_path = f"voice_tmp/{uuid.uuid4()}_{request.text_id}.mp3"
    os.makedirs(os.path.dirname("voice_tmp"), exist_ok=True)

    try:
        speech_api.send_request(api_url, request_body, voice_output_path)
        custom_logger.info(f"Voice file generated: {voice_output_path}")
    except Exception as e:
        custom_logger.error(f"Failed to generate voice: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate voice: {str(e)}")
    
    file_key = upload_to_oss(voice_output_path, request.user_id)
    if not file_key:
        custom_logger.error("Failed to upload voice file to OSS")
        raise HTTPException(status_code=500, detail="Failed to upload voice file to OSS")
    
    voice_response_url = f"https://pillow-agent.oss-cn-shanghai.aliyuncs.com/{file_key}"
    custom_logger.info(f"Voice file uploaded successfully: {voice_response_url}")
    
    return Text2VoiceResponse(user_id=request.user_id, text_id=request.text_id, url=voice_response_url)

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
