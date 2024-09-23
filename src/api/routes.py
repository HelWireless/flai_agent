from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas import ChatRequest, ChatResponse, UserHistory
from database import get_db
from dialogue_query import get_user_dialogue_history
import openai
from content_filter import content_filter
from utils import get_emotion_type, check_assistant_repetition, split_message
from vector_query import VectorQuery
import yaml
from typing import List, Dict

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
    return openai.Embedding.create(input=text, model=EMBEDDING_MODEL)["data"][0]["embedding"]

def build_context(search_results: List[Dict]) -> str:
    return "\n".join([hit.payload["text"] for hit in search_results])

def generate_answer(context: str, question: str, messages: list, user_history_exists: bool) -> str:
    is_repetitive, repeated_sentence = check_assistant_repetition(messages)
    
    if is_repetitive:
        new_system_prompt = f"You are a helpful assistant. Use the following context to answer the user's question. Avoid repeating this sentence: '{repeated_sentence}'"
    else:
        new_system_prompt = "You are a helpful assistant. Use the following context to answer the user's question."
    
    if not user_history_exists:
        new_system_prompt += " 最近一周没有见过你。"

    # 组装 messages，历史对话在前，最新的用户提问和系统提示在后
    messages = [
        {"role": "system", "content": new_system_prompt},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
    ] + messages

    response = openai.ChatCompletion.create(
        model=COMPLETION_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

@router.post("/chat-pillow", response_model=ChatResponse)
async def chat_pillow(request: ChatRequest, db: Session = Depends(get_db)):
    # 首先检查查询内容是否敏感
    is_sensitive, sensitive_words = content_filter.detect_sensitive_content(request.message)
    if is_sensitive:
        raise HTTPException(status_code=400, detail="Query contains sensitive content")
    
    # 如果不敏感,继续处理查询
    query_embedding = get_embedding(request.message)
    search_results = vector_db.search_similar(query_embedding, limit=5)
    context = build_context(search_results)
    
    # 获取用户历史对话
    conversation_history = get_user_dialogue_history(db, request.user_id)
    user_history_exists = len(conversation_history) > 0

    # 生成回答
    answer = generate_answer(context, request.message, conversation_history, user_history_exists)

    # 将回答分割成多个部分（如果需要）
    llm_messages = split_message(answer, request.message_count)

    # 获取情感类型
    emotion_type = get_emotion_type(answer)

    return ChatResponse(
        user_id=request.user_id,
        llm_message=llm_messages,
        emotion_type=emotion_type
    )
