from typing import List
import re
import random
from collections import Counter


def get_emotion_type(text: str, emotion_type=None) -> int:
    emotion_keywords = {
        '开心': ['哈哈', '开心', '高兴', '快乐', '棒', '好', '有趣', '愉快', '甜', '喜欢', '爱', '欢乐', '兴奋', '赞',
                 '爽', '满意',
                 '开怀', '乐', '笑', '幸福', '舒心', '轻松', '愉悦', '欣喜', '欢欣', '喜悦', '欢快', '畅快', '美好',
                 '温馨'],
        '期待': ['期待', '希望', '盼望', '等待', '想要', '充满', '未来', '憧憬', '向往', '渴望', '梦想', '展望', '憧憬',
                 '聊聊', '来说说', '怎么样',
                 '期盼', '企盼', '盼', '期许', '憧憬', '展望', '畅想', '憧憬', '向往', '渴求', '期望', '期冀', '期盼',
                 '期许'],
        '生气': ['生气', '操', '愤怒', '讨厌', '烦', '恨', '不想', '恼火', '气愤', '不爽', '不满', '不快', '恼怒',
                 '厌恶', '烦躁', '不理', '不搭理',
                 '恼', '怒', '火大', '气死', '气炸', '恨死', '烦死', '厌烦', '讨厌', '憎恨', '恼怒', '气愤', '恼火',
                 '气恼'],
        '伤心': ['伤心', '难过', '悲伤', '哭', '痛苦', '忧伤', '失落', '沮丧', '遗憾', '惆怅', '悲观', '消沉', '绝望',
                 '心碎', '悲痛', '哀伤', '悲凄', '凄凉', '凄惨', '悲惨', '凄凉', '悲戚', '悲怆', '悲恸', '悲恻',
                 '悲凉'],
        '惊恐': ['害怕', '恐惧', '惊吓', '可怕', '吓', '惊慌', '担心', '焦虑', '恐慌', '惶恐', '惊骇', '惊惶', '怕怕',
                 '呜呜',
                 '惊', '骇', '惧', '惶', '惊悚', '惊惧', '惊恐', '惊骇', '惊惶', '惊惧', '惊怖', '惊慌', '惊吓',
                 '惊惧'],
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
    if emotion_type:
        try:
            return emotion_map[emotion_type]
        except Exception as e:
            print("error is ", e)
            return get_emotion_type(text)

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


def generate_random_proportions(count: int) -> List[float]:
    """生成count个随机比例，总和为1"""
    proportions = [random.random() for _ in range(count)]
    total = sum(proportions)
    return [p / total for p in proportions]


def clean_sentence(sentence: str) -> str:
    # 定义要移除的符号
    symbols_to_remove = r'[\\"\(\)\[\]\{\}]'
    # 使用正则表达式替换这些符号为空字符串
    cleaned_sentence = re.sub(symbols_to_remove, '', sentence)
    # 去除首尾空白字符
    cleaned_sentence = cleaned_sentence.strip()

    # 去除句子开头到第一个文字之间的所有符号
    cleaned_sentence = re.sub(r'^[^\w\s]+', '', cleaned_sentence)

    return cleaned_sentence


def split_message(message: str, count: int) -> List[str]:
    message = message.replace('\\"', '#')

    if count <= 1:
        return [clean_sentence(message)]

    # 生成随机比例
    proportions = generate_random_proportions(count)

    # 使用正则表达式匹配句子，考虑空格、句号、感叹号和问号作为分隔符
    pattern = re.compile(r'([^。！？\s]+[。！？]?)|([^。！？\s]+\s)')
    sentences = pattern.findall(message)
    sentences = [''.join(s).strip() for s in sentences if ''.join(s).strip()]

    result = []
    current_segment = ""
    current_length = 0
    target_length = 0
    proportion_index = 0

    for sentence in sentences:
        if current_length == 0:
            target_length = int(len(message) * proportions[proportion_index])

        if current_length + len(sentence) <= target_length or not current_segment:
            current_segment += sentence + " "
            current_length += len(sentence)
        else:
            result.append(current_segment.strip())
            current_segment = sentence + " "
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
        result[min_index] = result[min_index] + " " + result[min_index + 1]
        result.pop(min_index + 1)

    # 确保至少有 count 个段落
    while len(result) < count:
        longest_segment = max(result, key=len)
        index = result.index(longest_segment)
        parts = longest_segment.split(None, 1)
        if len(parts) > 1:
            result[index] = parts[0]
            result.insert(index + 1, parts[1])
        else:
            break

    # 清理每个句子中的干扰符号
    result = [clean_sentence(sentence) for sentence in result]
    # 过滤掉长度小于或等于1的句子
    result = [sentence for sentence in result if len(sentence) > 1]

    # print(f"最终结果: {result}")
    return result


if __name__ == "__main__":
    long_text = "你刚刚好像在逗我，说要给我奖励，但是我可没那(么容易就范哦) 要奖励也\"可以，“‘k&不过先告诉我，你准备了什么样的奖励呢 期待ing～"
    result = split_message(long_text, 10)
    print(f"主函数中的结果: {result}")

    # 添加更多测试用例
    test_cases = [
        "!!!你好，这是一个测试句子。",
        "...这是另一个(测试)句子。",
        "###第三个测试句子!!!",
        "   空格开头的句子",
        "（括号）开头的句子",
        "\"引号\"开头的句子",
        "\\反斜杠\\开头的句子",
    ]

    for test_case in test_cases:
        cleaned = clean_sentence(test_case)
        print(f"原句: {test_case}")
        print(f"清理后: {cleaned}")
        print()
