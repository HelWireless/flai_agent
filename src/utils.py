from typing import List

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
