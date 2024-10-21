from typing import List
import re
import math
import random


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


def generate_random_proportions(count: int) -> List[float]:
    """生成count个随机比例，总和为1"""
    proportions = [random.random() for _ in range(count)]
    total = sum(proportions)
    return [p / total for p in proportions]


def split_message(message: str, count: int) -> List[str]:
    message = message.replace('\\"', '#')

    if count <= 1:
        return [message]

    # 生成随机比例
    proportions = generate_random_proportions(count)

    # 使用正则表达式匹配句子，特别处理感叹句
    pattern = re.compile(r'([^。！？]+[。？])|([^。！？]+![^。！？]*[。！？]?)')
    sentences = pattern.findall(message)
    sentences = [''.join(s) for s in sentences]

    result = []
    current_segment = ""
    current_length = 0
    target_length = 0
    proportion_index = 0

    for sentence in sentences:
        # 如果是感叹句，特殊处理
        if '!' in sentence:
            exclamation_index = sentence.index('!')
            if current_segment:
                result.append(current_segment.strip())
                current_segment = ""
                current_length = 0
                proportion_index += 1
                if proportion_index < count:
                    target_length = int(len(message) * proportions[proportion_index])
            if exclamation_index > 0:
                result.append(sentence[:exclamation_index].strip())
            result.append(sentence[exclamation_index:].strip())
            proportion_index += 1
            if proportion_index < count:
                target_length = int(len(message) * proportions[proportion_index])
        else:
            if current_length == 0:
                target_length = int(len(message) * proportions[proportion_index])

            if current_length + len(sentence) <= target_length or not current_segment:
                current_segment += sentence
                current_length += len(sentence)
            else:
                result.append(current_segment.strip())
                current_segment = sentence
                current_length = len(sentence)
                proportion_index += 1
                if proportion_index < count:
                    target_length = int(len(message) * proportions[proportion_index])

    if current_segment:
        result.append(current_segment.strip())

    # # 如果段落数少于指定的count,将最长的段落从中间分割
    # while len(result) < count:
    #     longest_segment = max(result, key=len)
    #     index = result.index(longest_segment)
    #     half = len(longest_segment) // 2
    #     result.pop(index)
    #     result.insert(index, longest_segment[:half])
    #     result.insert(index + 1, longest_segment[half:])

    # 如果段落数多于指定的count,合并最短的相邻段落
    while len(result) > count:
        min_length = float('inf')
        min_index = 0
        for i in range(len(result) - 1):
            length = len(result[i]) + len(result[i + 1])
            if length < min_length:
                min_length = length
                min_index = i
        result[min_index] = result[min_index] + result[min_index + 1]
        result.pop(min_index + 1)

    i = 0
    while i < len(result):
        if i > 0 and result[i].strip('。！？') == '':
            result[i - 1] += result[i]
            result.pop(i)
        else:
            i += 1

    return [i.replace("。", "") for i in result]


if __name__ == "__main__":
    long_text = "我们要把它分割成更小的部分。啊!它包含多个短句。这是第四个句子。这是第五个句子。这是第六个句子。这是第七个句子。"
    result = split_message(long_text, 3)
    print(result)
