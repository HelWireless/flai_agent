import re
from typing import List, Tuple
import difflib
from vector_db import VectorDB  # 假设您有一个向量数据库的接口

class ContentFilter:
    def __init__(self, sensitive_words: List[str], keywords: List[str], vector_db: VectorDB):
        self.sensitive_words = sensitive_words
        self.keywords = keywords
        self.vector_db = vector_db
        self.sensitive_pattern = re.compile("|".join(map(re.escape, sensitive_words)), re.IGNORECASE)
        self.keyword_pattern = re.compile("|".join(map(re.escape, keywords)), re.IGNORECASE)

    def detect_sensitive_content(self, text: str) -> Tuple[bool, List[str]]:
        """
        检测文本中是否包含敏感内容
        返回一个元组: (是否包含敏感内容, 检测到的敏感词列表)
        """
        matches = self.sensitive_pattern.findall(text)
        return bool(matches), list(set(matches))

    def filter_sensitive_content(self, text: str, replacement: str = "***") -> str:
        """
        将文本中的敏感内容替换为指定字符
        """
        return self.sensitive_pattern.sub(replacement, text)

    def check_sentence_similarity(self, sentence1, sentence2):
        # 使用 SequenceMatcher 计算两个句子的相似度
        similarity = difflib.SequenceMatcher(None, sentence1, sentence2).ratio()
        return similarity

    def detect_repetition(self, text):
        sentences = text.split('。')  # 假设以句号分隔句子
        for i in range(len(sentences)):
            for j in range(i+1, len(sentences)):
                similarity = self.check_sentence_similarity(sentences[i], sentences[j])
                if similarity > 0.7:  # 设置相似度阈值
                    print(f"发现重复句子:\n{sentences[i]}\n{sentences[j]}")

    def detect_keywords(self, text: str) -> List[str]:
        """
        检测文本中是否包含关键词
        返回检测到的关键词列表
        """
        matches = self.keyword_pattern.findall(text)
        return list(set(matches))

    def query_vector_db(self, keyword: str) -> List[dict]:
        """
        根据关键词查询向量数据库
        返回查询结果列表
        """
        return self.vector_db.query(keyword)

    def process_text(self, text: str) -> dict:
        """
        处理文本：检测敏感词、关键词，并查询向量数据库
        """
        is_sensitive, sensitive_words = self.detect_sensitive_content(text)
        keywords = self.detect_keywords(text)
        vector_db_results = {}
        for keyword in keywords:
            vector_db_results[keyword] = self.query_vector_db(keyword)
        
        self.detect_repetition(text)
        
        return {
            "is_sensitive": is_sensitive,
            "sensitive_words": sensitive_words,
            "keywords": keywords,
            "vector_db_results": vector_db_results
        }

# 初始化 ContentFilter 实例
vector_db = VectorDB()  # 假设您有一个向量数据库的实例
content_filter = ContentFilter(
    sensitive_words=["敏感词1", "敏感词2", "敏感词3"],
    keywords=["关键词1", "关键词2", "关键词3"],
    vector_db=vector_db
)

if __name__ == "__main__":
    # 在主函数中调用
    text = "这是一个包含关键词1和敏感词2的测试文本。这是另一个包含关键词1的句子。"
    result = content_filter.process_text(text)
    print(result)
