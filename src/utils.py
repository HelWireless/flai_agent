from typing import List
import re

def get_emotion_type(text: str) -> int:
    # 这里需要实现情感分析逻辑
    # 返回 0-4 之间的一个整数
    # 这里只是一个示例实现，您需要根据实际情况来实现这个函数
    return 4  # 示例：总是返回 4

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

def split_message(message: str, count: int) -> List[str]:
    if len(message) <= 100 or count <= 1:
        return [message]
    
    segment_length = len(message) // count
    return [message[i:i+segment_length] for i in range(0, len(message), segment_length)][:count]

def split_text(text: str, max_length: int = 100) -> List[str]:
    # 使用正则表达式匹配句子，特别处理感叹句
    pattern = re.compile(r'([^。！？]+[。？])|([^。！？]+![^。！？]*[。！？]?)')
    sentences = pattern.findall(text)
    
    result = []
    current_sentence = ""
    
    for sentence_tuple in sentences:
        sentence = ''.join(sentence_tuple)  # 合并匹配的组
        
        # 如果是感叹句，单独处理
        if '!' in sentence:
            if current_sentence:
                result.append(current_sentence.strip())
                current_sentence = ""
            result.append(sentence.strip())
        elif len(current_sentence) + len(sentence) <= max_length:
            current_sentence += sentence
        else:
            if current_sentence:
                result.append(current_sentence.strip())
            current_sentence = sentence
    
    if current_sentence:
        result.append(current_sentence.strip())
    
    # 如果结果中的句子数量少于5，不进行合并
    if len(result) < 5:
        return result
    
    # 将第5个及之后的句子合并
    return result[:4] + ['，'.join(result[4:])]


if __name__ == "__main__":
    long_text = "啊!它包含多个短句。我们要把它分割成更小的部分。这是第四个句子。这是第五个句子。这是第六个句子。这是第四个句子。"
    result = split_text(long_text, max_length=50)
    print(result)
