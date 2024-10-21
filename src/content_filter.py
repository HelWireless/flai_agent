import re
from typing import List, Tuple
import difflib
import os
class ContentFilter:
    def __init__(self,additional_keywords: List[str] = None):
        self.sensitive_words = self.load_sensitive_words()
        self.keywords = additional_keywords or []
        self.sensitive_pattern = re.compile("|".join(map(re.escape, self.sensitive_words)), re.IGNORECASE)
        self.keyword_pattern = re.compile("|".join(map(re.escape, self.keywords)), re.IGNORECASE)

    def load_sensitive_words(self) -> List[str]:
        # 获取当前脚本的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建config.yaml的绝对路径
        config_path = os.path.join(current_dir, "sensitive_word_data.txt")

        with open(config_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]

    def detect_sensitive_content(self, text: str) -> Tuple[bool, List[str]]:
        matches = self.sensitive_pattern.findall(text)
        return bool(matches), list(set(matches))

    def filter_sensitive_content(self, text: str, replacement: str = "***") -> str:
        return self.sensitive_pattern.sub(replacement, text)

    def check_sentence_similarity(self, sentence1: str, sentence2: str) -> float:
        return difflib.SequenceMatcher(None, sentence1, sentence2).ratio()

    def detect_repetition(self, text: str, similarity_threshold: float = 0.7) -> List[Tuple[str, str, float]]:
        sentences = text.split('。')
        repetitions = []
        for i in range(len(sentences)):
            for j in range(i+1, len(sentences)):
                similarity = self.check_sentence_similarity(sentences[i], sentences[j])
                if similarity > similarity_threshold:
                    repetitions.append((sentences[i], sentences[j], similarity))
        return repetitions

    def remove_repetitions(self, text: str, similarity_threshold: float = 0.7) -> str:
        sentences = text.split('。')
        unique_sentences = []
        for sentence in sentences:
            is_duplicate = False
            for unique_sentence in unique_sentences:
                if self.check_sentence_similarity(sentence, unique_sentence) > similarity_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_sentences.append(sentence)
        return '。'.join(unique_sentences)

    def detect_keywords(self, text: str) -> List[str]:
        matches = self.keyword_pattern.findall(text)
        return list(set(matches))

    def process_text(self, text: str) -> dict:
        is_sensitive, sensitive_words = self.detect_sensitive_content(text)
        keywords = self.detect_keywords(text)
        repetitions = self.detect_repetition(text)
        
        if repetitions:
            text = self.remove_repetitions(text)
        
        return {
            "is_sensitive": is_sensitive,
            "sensitive_words": sensitive_words,
            "keywords": keywords,
            "repetitions": repetitions,
            "processed_text": text
        }



if __name__ == "__main__":
    # 初始化 ContentFilter 实例
    content_filter = ContentFilter(
        additional_keywords=["关键词1", "关键词2", "关键词3"]
    )
    text = "这是一个包含关键词1和刘少奇的测试文本。这是另一个包含关键词1的句子。这是一个非常相似的句子。这是一个非常相似的句子。"
    result = content_filter.process_text(text)
    print(result)
    
    print("处理后的文本:", result["processed_text"])
