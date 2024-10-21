from typing import List, Dict
import requests
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os
import json

class VectorQuery:
    def __init__(self, url: str, api_key: str, collection_name: str, embedding_api_key: str):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
        self.embedding_api_key = embedding_api_key
        self.embedding_url = "https://api.siliconflow.cn/v1/embeddings"

    def create_collection(self, vector_size: int):
        """创建或重新创建集合"""
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def insert_document(self, doc_id: str, vector: List[float], payload: Dict):
        """插入文档到向量数据库"""
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )

    def search_similar(self, query_vector: List[float], limit: int = 3) -> List[models.ScoredPoint]:
        """搜索相似文档"""
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit
        )

    def text_to_vector(self, text: str) -> List[float]:
        """使用API将文本转换为向量"""
        payload = {
            "model": "BAAI/bge-large-zh-v1.5",
            "input": text,
            "encoding_format": "float"
        }
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(self.embedding_url, json=payload, headers=headers)
        response.raise_for_status()  # 如果请求失败，这将引发异常

        data = response.json()
        return data['data'][0]['embedding']

    def insert_text(self, text: str, payload: Dict):
        """将文本转换为向量并插入到向量数据库"""
        vector = self.text_to_vector(text)
        doc_id = str(hash(text))  # 使用文本的哈希值作为ID
        payload['text'] = text  # 将原始文本添加到payload中
        self.insert_document(doc_id, vector, payload)

    def search_and_retrieve(self, query_text: str, limit: int = 3) -> List[Dict]:
        """
        搜索相似文档并返回完整的文档信息
        """
        query_vector = self.text_to_vector(query_text)
        results = self.search_similar(query_vector, limit)
        
        retrieved_documents = []
        for result in results:
            document = {
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("text", ""),
                "source": result.payload.get("source", ""),
                # 可以添加更多 payload 中的字段
            }
            retrieved_documents.append(document)
        
        return retrieved_documents

if __name__ == "__main__":
    # 初始化向量数据库
    url = "http://47.103.39.33:6333"  # 替换为您的 Qdrant 服务 URL
    api_key = ""  # 替换为您的 Qdrant API 密钥
    collection_name = "trick_response"
    embedding_api_key = "<your_embedding_api_key>"  # 替换为您的 embedding API 密钥

    vector_query = VectorQuery(url, api_key, collection_name, embedding_api_key)

    # 创建集合
    vector_size = 1024  # BAAI/bge-large-zh-v1.5 模型的向量大小
    vector_query.create_collection(vector_size)

    # 加载文档
    doc_path = "path/to/your/documents"  # 替换为您的文档路径

    for filename in os.listdir(doc_path):
        if filename.endswith(".json"):
            with open(os.path.join(doc_path, filename), 'r', encoding='utf-8') as file:
                data = json.load(file)
                for item in data:
                    text = item['text']
                    payload = {
                        "source": filename,
                        # 可以添加其他元数据
                    }
                    vector_query.insert_text(text, payload)

    print(f"文档已成功插入到 {collection_name} 集合中。")

    # 测试搜索和检索
    test_query = "这是一个测试查询"
    results = vector_query.search_and_retrieve(test_query, limit=3)

    print("\n搜索结果:")
    for result in results:
        print(f"ID: {result['id']}, 得分: {result['score']}")
        print(f"文本: {result['text']}")
        print(f"来源: {result['source']}")
        print()
