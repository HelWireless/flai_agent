from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import yaml
from vector_query import vector_db
from speech_api import speech_api
from content_filter import content_filter
from typing import List
import io
from fastapi.responses import StreamingResponse

app = FastAPI()

# 加载配置
with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

# OpenAI 配置
openai.api_key = config["openai"]["api_key"]
EMBEDDING_MODEL = config["openai"]["embedding_model"]
COMPLETION_MODEL = config["openai"]["completion_model"]

# 语音 API 配置
speech_api.configure(
    provider=config["speech_api"]["provider"],
    api_key=config["speech_api"]["api_key"],
    region=config["speech_api"]["region"]
)

class Document(BaseModel):
    text: str

class Query(BaseModel):
    text: str

class ContentCheckRequest(BaseModel):
    text: str

class TextToSpeechRequest(BaseModel):
    text: str
    voice: str

def get_embedding(text: str) -> List[float]:
    return openai.Embedding.create(input=text, model=EMBEDDING_MODEL)["data"][0]["embedding"]

def build_context(search_results: List[dict]) -> str:
    return "\n".join([hit.payload["text"] for hit in search_results])

def generate_answer(context: str, question: str, messages: list) -> str:
    is_repetitive, repeated_sentence = check_assistant_repetition(messages)
    
    if is_repetitive:
        new_system_prompt = f"You are a helpful assistant. Use the following context to answer the user's question. Avoid repeating this sentence: '{repeated_sentence}'"
    else:
        new_system_prompt = "You are a helpful assistant. Use the following context to answer the user's question."

    messages = [
        {"role": "system", "content": new_system_prompt},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
    ] + messages

    response = openai.ChatCompletion.create(
        model=COMPLETION_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

def check_assistant_repetition(messages, threshold=0.8):
    assistant_responses = [msg['content'] for msg in messages if msg['role'] == 'assistant']
    
    if len(assistant_responses) < 2:
        return False, ""

    latest_response = assistant_responses[-1]
    previous_responses = assistant_responses[:-1]

    for response in previous_responses:
        similarity = content_filter.check_sentence_similarity(latest_response, response)
        if similarity > threshold:
            return True, response

    return False, ""

@app.post("/add_document")
async def add_document(document: Document):
    embedding = get_embedding(document.text)
    vector_db.insert_document(doc_id=hash(document.text), vector=embedding, payload={"text": document.text})
    return {"message": "Document added successfully"}

@app.post("/query")
async def query(query: Query):
    # 首先检查查询内容是否敏感
    is_sensitive, sensitive_words = content_filter.detect_sensitive_content(query.text)
    if is_sensitive:
        raise HTTPException(status_code=400, detail="Query contains sensitive content")
    
    # 如果不敏感,继续处理查询
    query_embedding = get_embedding(query.text)
    search_results = vector_db.search_similar(query_embedding)
    context = build_context(search_results)
    
    # 假设我们有一个存储对话历史的列表
    conversation_history = []  # 这应该在实际应用中持久化存储
    
    answer = generate_answer(context, query.text, conversation_history)
    
    # 更新对话历史
    conversation_history.append({"role": "user", "content": query.text})
    conversation_history.append({"role": "assistant", "content": answer})
    
    # 检查生成的答案是否包含敏感内容
    is_sensitive, sensitive_words = content_filter.detect_sensitive_content(answer)
    if is_sensitive:
        answer = content_filter.filter_sensitive_content(answer)
    
    return {"answer": answer, "contains_sensitive_content": is_sensitive}

@app.post("/check_content")
async def check_content(request: ContentCheckRequest):
    is_sensitive, sensitive_words = content_filter.detect_sensitive_content(request.text)
    if is_sensitive:
        return {
            "is_sensitive": True,
            "sensitive_words": sensitive_words,
            "filtered_text": content_filter.filter_sensitive_content(request.text)
        }
    else:
        return {"is_sensitive": False}

@app.post("/text_to_speech")
async def text_to_speech(request: TextToSpeechRequest):
    audio_content = speech_api.text_to_speech(request.text, request.voice)
    if audio_content:
        return StreamingResponse(io.BytesIO(audio_content), media_type="audio/mpeg")
    else:
        return {"error": "Failed to generate speech"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)