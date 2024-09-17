from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models

class VectorQuery:
    def __init__(self, url: str, api_key: str, collection_name: str):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name

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

# 初始化 VectorQuery 实例的代码应该移到 main.py 中