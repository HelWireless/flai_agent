"""
向量存储服务 - 用于长期记忆的语义检索
"""
from typing import List, Dict, Optional
import requests
from ..custom_logger import custom_logger


class VectorStore:
    """向量数据库客户端（支持 Qdrant 或其他向量数据库）"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化向量存储
        
        Args:
            config: 向量数据库配置，包含 url, api_key, collection_name 等
        """
        self.enabled = config is not None and config.get('enabled', False)
        
        if self.enabled:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http import models
                
                self.client = QdrantClient(
                    url=config.get('url'),
                    api_key=config.get('api_key')
                )
                self.collection_name = config.get('collection_name', 'conversations')
                self.embedding_api_key = config.get('embedding_api_key')
                self.embedding_url = config.get('embedding_url', 'https://api.siliconflow.cn/v1/embeddings')
                
                custom_logger.info(f"Vector store enabled: {self.collection_name}")
            except ImportError:
                custom_logger.warning("qdrant-client not installed, vector store disabled")
                self.enabled = False
            except Exception as e:
                custom_logger.error(f"Vector store initialization failed: {e}")
                self.enabled = False
        else:
            custom_logger.info("Vector store disabled")
            self.client = None
    
    def _text_to_vector(self, text: str) -> List[float]:
        """将文本转换为向量（使用 embedding API）"""
        if not self.enabled:
            return []
        
        payload = {
            "model": "BAAI/bge-large-zh-v1.5",
            "input": text,
            "encoding_format": "float"
        }
        headers = {
            "Authorization": f"Bearer {self.embedding_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(self.embedding_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data['data'][0]['embedding']
        except Exception as e:
            custom_logger.error(f"Embedding generation failed: {e}")
            return []
    
    async def store_conversation(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        存储对话到向量数据库
        
        Args:
            user_id: 用户ID
            user_message: 用户消息
            ai_response: AI回复
            metadata: 额外元数据（时间、情绪等）
        
        Returns:
            是否成功
        """
        if not self.enabled:
            return False
        
        try:
            # 合并用户消息和AI回复作为检索文本
            combined_text = f"用户: {user_message}\nAI: {ai_response}"
            vector = self._text_to_vector(combined_text)
            
            if not vector:
                return False
            
            # 构建 payload
            payload = {
                "user_id": user_id,
                "user_message": user_message,
                "ai_response": ai_response,
                "text": combined_text,
                **(metadata or {})
            }
            
            # 存储到向量数据库
            from qdrant_client.http import models
            point_id = hash(combined_text) % (2**63)  # 生成唯一ID
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            
            custom_logger.debug(f"Conversation stored to vector DB for user {user_id}")
            return True
        except Exception as e:
            custom_logger.error(f"Failed to store conversation: {e}")
            return False
    
    async def search_similar_conversations(
        self,
        user_id: str,
        query_text: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        搜索相似的历史对话
        
        Args:
            user_id: 用户ID
            query_text: 查询文本
            limit: 返回数量
        
        Returns:
            相似对话列表
        """
        if not self.enabled:
            return []
        
        try:
            # 生成查询向量
            query_vector = self._text_to_vector(query_text)
            
            if not query_vector:
                return []
            
            # 搜索
            from qdrant_client.http import models
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=user_id)
                        )
                    ]
                ),
                limit=limit
            )
            
            # 转换结果
            conversations = []
            for result in results:
                conversations.append({
                    "score": result.score,
                    "user_message": result.payload.get("user_message", ""),
                    "ai_response": result.payload.get("ai_response", ""),
                    "metadata": {
                        k: v for k, v in result.payload.items() 
                        if k not in ["user_id", "user_message", "ai_response", "text"]
                    }
                })
            
            custom_logger.debug(f"Found {len(conversations)} similar conversations for user {user_id}")
            return conversations
        except Exception as e:
            custom_logger.error(f"Vector search failed: {e}")
            return []

