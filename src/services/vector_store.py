"""
向量存储服务 - 用于长期记忆的语义检索
"""
from typing import List, Dict, Optional
import requests
import json
import urllib3
from ..custom_logger import custom_logger, debug_log


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
                
                # 禁用SSL警告，因为我们可能使用自签名证书
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                # 检查是否使用HTTPS连接
                qdrant_url = config.get('url')
                is_https = qdrant_url.startswith('https://') if qdrant_url else False
                
                custom_logger.info(f"Initializing vector store - URL: {qdrant_url}, HTTPS: {is_https}")
                
                # 根据URL类型决定是否需要SSL配置
                if is_https:
                    self.client = QdrantClient(
                        url=qdrant_url,
                        api_key=config.get('api_key'),
                        https=True,
                        verify=False  # 忽略SSL证书验证
                    )
                else:
                    # HTTP连接明确指定不需要HTTPS
                    self.client = QdrantClient(
                        url=qdrant_url,
                        api_key=config.get('api_key'),
                        https=False,
                        prefer_grpc=False  # 使用HTTP而不是gRPC
                    )
                    
                self.collection_name = config.get('collection_name', 'conversations')
                self.embedding_api_key = config.get('embedding_api_key')
                self.embedding_url = config.get('embedding_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings')
                self.embedding_model = config.get('embedding_model', 'text-embedding-v4')  # 获取配置的嵌入模型
                
                # 测试连接
                try:
                    # 尝试获取集合信息来测试连接
                    collections = self.client.get_collections()
                    custom_logger.info(f"Vector store connection successful. Available collections: {[c.name for c in collections.collections]}")
                except Exception as conn_err:
                    custom_logger.warning(f"Vector store connection test failed: {conn_err}")
                
                custom_logger.info(f"Vector store enabled: {self.collection_name}")
                debug_log(f"Vector store configuration - URL: {qdrant_url}, Collection: {self.collection_name}, Embedding Model: {self.embedding_model}")
            except ImportError as e:
                custom_logger.warning(f"qdrant-client not installed, vector store disabled: {e}")
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
        
        try:
            import dashscope
            from http import HTTPStatus
            
            debug_log(f"Generating embedding for text: {text[:100]}...")  # 只显示前100个字符
            
            dashscope.api_key = self.embedding_api_key
            response = dashscope.TextEmbedding.call(
                model=self.embedding_model,  # 使用配置中指定的模型
                input=text
            )
            
            if response.status_code == HTTPStatus.OK:
                embedding = response.output['embeddings'][0]['embedding']
                debug_log(f"Embedding generated successfully, dimension: {len(embedding)}")
                # 在debug模式下不再显示具体的向量值
                return embedding
            else:
                custom_logger.error(f"Embedding generation failed: {response}")
                return []
        except Exception as e:
            custom_logger.error(f"Embedding generation failed: {e}")
            return []
    
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
        import time
        start_time = time.time()
        custom_logger.info(f"Starting to search similar conversations for user {user_id}")
        debug_log(f"Search query text: {query_text}")
        
        if not self.enabled:
            return []
        
        try:
            # 生成查询向量
            embedding_start_time = time.time()
            query_vector = self._text_to_vector(query_text)
            embedding_end_time = time.time()
            embedding_duration = embedding_end_time - embedding_start_time
            custom_logger.info(f"Text to vector conversion completed in {embedding_duration:.2f} seconds")
            
            if not query_vector:
                return []
            
            # 搜索
            search_start_time = time.time()
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
            search_end_time = time.time()
            search_duration = search_end_time - search_start_time
            custom_logger.info(f"Vector search completed in {search_duration:.2f} seconds")
            
            # 转换结果
            conversion_start_time = time.time()
            conversations = []
            for result in results:
                conversation_data = {
                    "score": result.score,
                    "user_message": result.payload.get("user_message", ""),
                    "ai_response": result.payload.get("ai_response", ""),
                    "metadata": {
                        k: v for k, v in result.payload.items() 
                        if k not in ["user_id", "user_message", "ai_response", "text"]
                    }
                }
                conversations.append(conversation_data)
                debug_log(f"Found similar conversation - Score: {result.score:.4f}, User: {conversation_data['user_message'][:50]}...")
            
            conversion_end_time = time.time()
            conversion_duration = conversion_end_time - conversion_start_time
            custom_logger.info(f"Results conversion completed in {conversion_duration:.2f} seconds")
            
            custom_logger.debug(f"Found {len(conversations)} similar conversations for user {user_id}")
            debug_log(f"Total similar conversations found: {len(conversations)}")
            
            end_time = time.time()
            total_duration = end_time - start_time
            custom_logger.info(f"Total vector search completed in {total_duration:.2f} seconds")
            
            return conversations
        except Exception as e:
            custom_logger.error(f"Vector search failed: {e}")
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
        import time
        start_time = time.time()
        custom_logger.info(f"Starting to store conversation for user {user_id}")
        debug_log(f"Storing conversation - User: {user_message}, AI: {ai_response[:100]}...")  # 只显示AI回复的前100个字符
        
        if not self.enabled:
            return False
        
        try:
            # 合并用户消息和AI回复作为检索文本
            combine_start_time = time.time()
            combined_text = f"用户: {user_message}\nAI: {ai_response}"
            debug_log(f"Combined text for storage: {combined_text[:200]}...")  # 只显示前200个字符
            
            # 检查是否已存在相似内容（去重）
            similar_conversations = await self.search_similar_conversations(
                user_id=user_id,
                query_text=combined_text,
                limit=1
            )
            
            # 如果最相似的对话超过阈值，则认为是重复内容，不存储
            if similar_conversations and similar_conversations[0]["score"] >= 0.96:
                custom_logger.debug(f"Conversation is too similar (score: {similar_conversations[0]['score']}) to existing content, skipping storage")
                debug_log(f"Skipping storage due to high similarity: {similar_conversations[0]['score']:.4f}")
                return False
            combine_end_time = time.time()
            combine_duration = combine_end_time - combine_start_time
            custom_logger.info(f"Text combination and similarity check completed in {combine_duration:.2f} seconds")
            
            embedding_start_time = time.time()
            vector = self._text_to_vector(combined_text)
            embedding_end_time = time.time()
            embedding_duration = embedding_end_time - embedding_start_time
            custom_logger.info(f"Text to vector conversion completed in {embedding_duration:.2f} seconds")
            
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
            
            debug_log(f"Payload for storage: {json.dumps(payload, ensure_ascii=False)[:300]}...")  # 只显示前300个字符
            
            # 存储到向量数据库
            store_start_time = time.time()
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
            store_end_time = time.time()
            store_duration = store_end_time - store_start_time
            custom_logger.info(f"Vector storage completed in {store_duration:.2f} seconds")
            
            custom_logger.debug(f"Conversation stored to vector DB for user {user_id}")
            debug_log(f"Conversation successfully stored with point ID: {point_id}")
            
            end_time = time.time()
            total_duration = end_time - start_time
            custom_logger.info(f"Total conversation storage completed in {total_duration:.2f} seconds")
            
            return True
        except Exception as e:
            custom_logger.error(f"Failed to store conversation: {e}")
            return False