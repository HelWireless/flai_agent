from typing import List
import re
import math
import random
from collections import Counter


def get_emotion_type(text: str) -> int:
    emotion_keywords = {
        '开心': ['哈哈', '开心', '高兴', '快乐', '棒', '好', '有趣', '愉快', '甜', '喜欢', '爱', '欢乐', '兴奋', '赞', '爽', '满意', 
                 '开怀', '乐', '笑', '幸福', '舒心', '轻松', '愉悦', '欣喜', '欢欣', '喜悦', '欢快', '畅快', '美好', '温馨'],
        '期待': ['期待', '希望', '盼望', '等待', '想要', '充满', '未来', '憧憬', '向往', '渴望', '梦想', '展望', '憧憬', '聊聊', '来说说', '怎么样',
                 '期盼', '企盼', '盼', '期许', '憧憬', '展望', '畅想', '憧憬', '向往', '渴求', '期望', '期冀', '期盼', '期许'],
        '生气': ['生气', '操','愤怒', '讨厌', '烦', '恨', '不想', '恼火', '气愤', '不爽', '不满', '不快', '恼怒', '厌恶', '烦躁', '不理', '不搭理',
                 '恼', '怒', '火大', '气死', '气炸', '恨死', '烦死', '厌烦', '讨厌', '憎恨', '恼怒', '气愤', '恼火', '气恼'],
        '伤心': ['伤心', '难过', '悲伤', '哭', '痛苦', '忧伤', '失落', '沮丧', '遗憾', '惆怅', '悲观', '消沉', '绝望',
                 '心碎', '悲痛', '哀伤', '悲凄', '凄凉', '凄惨', '悲惨', '凄凉', '悲戚', '悲怆', '悲恸', '悲恻', '悲凉'],
        '惊恐': ['害怕', '恐惧', '惊吓', '可怕', '吓', '惊慌', '担心', '焦虑', '恐慌', '惶恐', '惊骇', '惊惶', '怕怕', '呜呜',
                 '惊', '骇', '惧', '惶', '惊悚', '惊惧', '惊恐', '惊骇', '惊惶', '惊惧', '惊怖', '惊慌', '惊吓', '惊惧'],
        '害羞': ['害羞', '尴尬', '羞涩', '脸红', '不好意思', '腼腆', '羞怯', '难为情', '扭捏', '拘谨',
                 '羞赧', '羞怯', '羞涩', '羞答答', '羞怯怯', '羞答答', '羞赧赧', '羞涩涩', '羞怯怯', '羞答答'],
        '抱抱': ['抱抱', '拥抱', '安慰', '需要', '温暖', '安慰', '呵护', '依偎', '亲密', '体贴', '关爱',
                 '搂', '抱', '拥', '抱紧', '搂紧', '依偎', '依靠', '依附', '依恋', '依赖'],
        '无语': ['无语', '哎，', '不知道说什么', '呵呵', '无话可说', '不知所措', '茫然', '不明白', '困惑', '莫名其妙',
                 '懵', '懵逼', '懵圈', '蒙圈', '蒙蔽', '迷糊', '迷茫', '迷惑', '迷惘', '迷失']
    }
    
    emotion_map = {
        "开心": 2,
        "期待": 6,
        "生气": 7,
        "伤心": 8,
        "惊恐": 5,
        "害羞": 1,
        "抱抱": 3,
        "无语": 4
    }
    
    # 表情符号映射
    emoji_map = {
        '😊': '开心', '😄': '开心', '😃': '开心', '😁': '开心',
        '🤔': '期待', '🙏': '期待',
        '😠': '生气', '😡': '生气', '🤬': '生气',
        '😢': '伤心', '😭': '伤心', '😞': '伤心',
        '😨': '惊恐', '😱': '惊恐', '😰': '惊恐',
        '😳': '害羞', '🤭': '害羞',
        '🤗': '抱抱',
        '😐': '无语', '😑': '无语', '🙄': '无语'
    }
    
    text = text.lower()
    exclamation_count = text.count('!')
    question_count = text.count('?')
    
    # 词频分析
    word_counts = Counter(re.findall(r'\w+', text))
    
    emotion_scores = {emotion: 0 for emotion in emotion_keywords.keys()}
    
    # 关键词匹配
    for emotion, keywords in emotion_keywords.items():
        for keyword in keywords:
            if keyword in text:
                emotion_scores[emotion] += text.count(keyword) * 2  # 关键词匹配权重加倍
    
    # 表情符号判断
    for emoji, emotion in emoji_map.items():
        if emoji in text:
            emotion_scores[emotion] += text.count(emoji) * 3  # 表情符号权重更高
    
    # 考虑感叹号和问号
    if exclamation_count > 0:
        emotion_scores['开心'] += exclamation_count
        emotion_scores['生气'] += exclamation_count
    if question_count > 0:
        emotion_scores['期待'] += question_count
    
    # 获取得分最高的情感
    max_emotion = max(emotion_scores, key=emotion_scores.get)
    
    # 如果最高分为0，则返回'无语'
    if emotion_scores[max_emotion] == 0:
        return emotion_map['无语']
    
    return emotion_map[max_emotion]


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
    long_text = "我们要把它分割成更小的部分。啊!它包含多短句。这是第四个句子。这是第五个句子。这是第六个句子。这是第七个句子。"
    result = split_message(long_text, 3)
    print(result)

    test_sentences = [
        "我今天真的很开心！😊",
        "我对未来充满期待，你觉得呢？",
        "这太让人生气了，简直不可理喻！😠",
        "听到这个消息，我感到非常伤心。😢",
        "天哪，这太可怕了！😱",
        "我有点不好意思说这个... 😳",
        "需要一个温暖的抱抱。🤗",
        "这是什么情况？我完全不明白。"
    ]
    
    for sentence in test_sentences:
        emotion_type = get_emotion_type(sentence)
        print(f"句子: {sentence}")
        print(f"情感类型: {emotion_type}")
        print()