from typing import List
import re
import random
from collections import Counter
from src.services.oss_client import get_oss_bucket
import uuid
import time
from src.custom_logger import custom_logger  # 导入自定义logger
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

    # 扩展匹配：将 LLM 可能返回的其他情绪词映射到这 8 种核心情绪
    extended_mapping = {
        "激动": "开心", "欣喜": "开心", "快乐": "开心", "高兴": "开心", "欢喜": "开心", "喜悦": "開心",
        "怀念": "期待", "向往": "期待", "盼望": "期待", "渴望": "期待", "好奇": "期待",
        "愤怒": "生气", "恼火": "生气", "不满": "生气", "讨厌": "生气", "愤恨": "生气",
        "难过": "伤心", "悲伤": "伤心", "沮丧": "伤心", "痛苦": "伤心", "失落": "伤心", "委屈": "伤心",
        "害怕": "惊恐", "恐惧": "惊恐", "惊吓": "惊恐", "担心": "惊恐", "焦虑": "惊恐", "慌张": "惊恐",
        "羞涩": "害羞", "尴尬": "害羞", "腼腆": "害羞", "脸红": "害羞",
        "温暖": "抱抱", "依恋": "抱抱", "安慰": "抱抱", "亲密": "抱抱",
        "困惑": "无语", "迷茫": "无语", "无奈": "无语", "尴尬": "无语", "懵逼": "无语", "淡定": "无语", "冷静": "无语"
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

    def _get_matched_id(e_type):
        """内部匹配逻辑：支持精确匹配和扩展映射"""
        if not e_type:
            return None
        # 1. 精确匹配核心 8 种
        if e_type in emotion_map:
            return emotion_map[e_type]
        # 2. 匹配扩展映射
        if e_type in extended_mapping:
            core_type = extended_mapping[e_type]
            return emotion_map[core_type]
        # 3. 模糊匹配（包含关系）
        for core_name, core_id in emotion_map.items():
            if core_name in e_type or e_type in core_name:
                return core_id
        return None

    if emotion_type:
        # 处理 LLM 可能返回列表的情况
        if isinstance(emotion_type, list):
            for et in emotion_type:
                matched_id = _get_matched_id(et)
                if matched_id:
                    return matched_id
            # 如果列表里都没有匹配到，取第一个作为后续处理的基础
            emotion_type = emotion_type[0] if emotion_type else None

        matched_id = _get_matched_id(emotion_type)
        if matched_id:
            return matched_id
        else:
            # emotion_type不在map中，尝试从扩展映射中寻找
            custom_logger.warning(f"Unknown emotion_type: {emotion_type}, using random fallback")
            return random.choice(list(emotion_map.values()))

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
    # 添加调试日志
    from .custom_logger import debug_log
    debug_log(f"clean_sentence input: '{sentence}'")
    
    # 移除中英文括号及其他指定符号，但保留有意义的标点符号如波浪号
    symbols_to_remove = r'[\\"‘’“”\(\)（）\[\]\{\}【】]'
    cleaned_sentence = re.sub(symbols_to_remove, '', sentence)
    debug_log(f"After removing symbols: '{cleaned_sentence}'")
    
    cleaned_sentence = cleaned_sentence.strip()
    debug_log(f"After stripping: '{cleaned_sentence}'")

    # 去除开头到第一个文字或空格前的非文字字符，但保留有意义的符号如波浪号
    cleaned_sentence = re.sub(r'^[^\w\s~]+', '', cleaned_sentence)
    debug_log(f"After removing leading non-word chars: '{cleaned_sentence}'")
    
    debug_log(f"clean_sentence output: '{cleaned_sentence}'")
    return cleaned_sentence

def remove_emojis(text: str) -> str:
    """移除文本中的所有emoji"""
    from .custom_logger import debug_log
    debug_log(f"Before remove_emojis: {text}")
    # 使用更安全的正则表达式匹配emoji，避免误删中文字符
    emoji_pattern = re.compile(
        "([\U0001F600-\U0001F64F]"  # 表情符号
        "|[\U0001F300-\U0001F5FF]"  # 符号和图形
        "|[\U0001F680-\U0001F6FF]"  # 交通和地图符号
        "|[\U0001F700-\U0001F77F]"  # 几何形状扩展
        "|[\U0001F780-\U0001F7FF]"  # 附加几何形状
        "|[\U0001F800-\U0001F8FF]"  # 补充符号-交通
        "|[\U0001F900-\U0001F9FF]"  # 补充符号-大
        "|[\U0001FA00-\U0001FA6F]"  # 传统游戏符号
        "|[\U0001FA70-\U0001FAFF]"  # 补充符号-小
        "|[\U00002600-\U000027BF]"  # 杂项符号
        "|[\U0001F000-\U0001F02F])"  # 棋牌符号
    , flags=re.UNICODE)
    result = emoji_pattern.sub('', text)
    debug_log(f"After remove_emojis: {result}")
    return result

def is_all_emojis(text: str) -> bool:
    """检查文本是否全部由emoji组成"""
    if not text:
        return False
    
    # 使用正则表达式匹配emoji（修正范围，避免匹配到中文字符）
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和图形
        "\U0001F680-\U0001F6FF"  # 交通和地图
        "\U0001F700-\U0001F77F"  # 炼金术符号
        "\U0001F780-\U0001F7FF"  # 几何形状扩展
        "\U0001F800-\U0001F8FF"  # 补充箭头-C
        "\U0001F900-\U0001F9FF"  # 补充符号和图形
        "\U0001FA00-\U0001FA6F"  # 国际象棋符号
        "\U0001FA70-\U0001FAFF"  # 符号和图形扩展-A
        "\U00002702-\U000027B0"  # 装饰符号
        "\U0001F1E0-\U0001F1FF"  # 国旗
        "\U00002600-\U000026FF"  # 杂项符号
        "\U0000FE00-\U0000FE0F"  # 变体选择器
        "\U0000200D"             # 零宽连接符
        "]", 
        flags=re.UNICODE
    )
    
    # 移除所有emoji
    text_without_emojis = emoji_pattern.sub('', text)
    
    # 如果移除emoji后文本为空，则说明原文本全部由emoji组成
    return len(text_without_emojis.strip()) == 0

def remove_random_interjections(sentences: List[str]) -> List[str]:
    """50%的概率删除单独的口癖词"""
    interjections = {"哼", "哈", "哎呀", "嗯", "哦", "呃", "啊", "哎", "咦", "嘘", "哼哼", "哈哈", "嘿嘿"}
    
    result = []
    for sentence in sentences:
        # 检查是否是单独的口癖词
        if sentence.strip() in interjections:
            # 50%的概率删除
            if random.random() < 0.5:
                continue  # 跳过这个句子（即删除它）
        
        result.append(sentence)
    
    # 如果所有句子都被删除了，至少保留一个
    if not result and sentences:
        result.append(sentences[0])
    
    return result

def get_emoji_emotion(emoji_text: str) -> str:
    """
    识别emoji的情感类型
    
    Args:
        emoji_text: 包含emoji的文本
    
    Returns:
        情感类型字符串
    """
    # emoji到情感的映射
    emoji_emotion_map = {
        # 开心类
        '😊': '开心', '😄': '开心', '😃': '开心', '😁': '开心', '😆': '开心', 
        '😀': '开心', '🥰': '开心', '😍': '开心', '🤩': '开心', '😘': '开心',
        '😋': '开心', '😜': '开心', '😝': '开心', '🤪': '开心', '😎': '开心',
        '🎉': '开心', '🎊': '开心', '✨': '开心', '💖': '开心', '❤️': '开心',
        # 期待/思考类
        '🤔': '期待', '🙏': '期待', '👀': '期待', '🧐': '期待', '💭': '期待',
        # 生气类
        '😠': '生气', '😡': '生气', '🤬': '生气', '💢': '生气', '😤': '生气',
        # 伤心类
        '😢': '伤心', '😭': '伤心', '😞': '伤心', '😔': '伤心', '😿': '伤心',
        '🥺': '伤心', '😥': '伤心', '😓': '伤心',
        # 惊恐类
        '😨': '惊恐', '😱': '惊恐', '😰': '惊恐', '😧': '惊恐', '😦': '惊恐',
        # 害羞类
        '😳': '害羞', '🤭': '害羞', '🙈': '害羞', '😅': '害羞',
        # 抱抱/安慰类
        '🤗': '抱抱', '💕': '抱抱', '💗': '抱抱', '🥹': 'brace',
        # 无语类
        '😐': '无语', '😑': '无语', '🙄': '无语', '😒': '无语', '🤷': '无语',
    }
    
    # 统计各情感出现次数
    emotion_counts = {}
    for char in emoji_text:
        if char in emoji_emotion_map:
            emotion = emoji_emotion_map[char]
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    if not emotion_counts:
        return '开心'  # 默认开心
    
    # 返回出现次数最多的情感
    return max(emotion_counts, key=emotion_counts.get)


def get_response_emoji(emotion: str) -> str:
    """
    根据情感类型返回对应的回复emoji
    
    Args:
        emotion: 情感类型
    
    Returns:
        对应的emoji
    """
    # 情感对应的回复emoji池
    emotion_response_emojis = {
        '开心': ['😊', '😄', '🥰', '😘', '💖', '✨', '🎉', '😁', '💕'],
        '期待': ['🤔', '👀', '😏', '🧐', '💭', '✨'],
        '生气': ['😤', '🙄', '😑', '💢'],  # 回复生气用傲娇的emoji
        '伤心': ['🤗', '💕', '😘', '🥹', '💖'],  # 回复伤心用安慰的emoji
        '惊恐': ['😳', '👀', '🤗', '💕'],  # 回复惊恐用安抚的emoji
        '害羞': ['😊', '🤭', '😏', '💕', '😘'],  # 回复害羞用调皮的emoji
        '抱抱': ['🤗', '💕', '💖', '😘', '🥰'],  # 回复抱抱用温暖的emoji
        '无语': ['😏', '🤭', '😜', '✨'],  # 回复无语用调皮的emoji
    }
    
    emojis = emotion_response_emojis.get(emotion, ['😊', '💕'])
    return random.choice(emojis)


def split_message(message: str, count: int, is_voice: bool = False, user_message: str = None) -> List[str]:
    """
    分割消息为多个段落
    
    Args:
        message: LLM生成的回复
        count: 分割段落数
        is_voice: 是否语音模式
        user_message: 用户的原始消息（用于判断是否需要emoji回复）
    
    Returns:
        分割后的消息列表
    """
    if not isinstance(message, str):
        message = str(message)
    
    # 语音模式下不进行分割，直接返回清理后的完整消息
    if is_voice:
        # 在voice模式下，禁止出现emoji
        message = remove_emojis(message)
        # 语音模式下不进行分割，直接返回清理后的完整消息
        cleaned = clean_sentence(message)
        from .custom_logger import debug_log
        debug_log(f"Voice mode: original message: {message}, cleaned: {cleaned}")
        if len(cleaned) == 0:
            return [message]
        return [cleaned]
    
    # 处理emoji（非语音模式）
    if user_message and is_all_emojis(user_message):
        # 非voice模式下，如果用户输入全是emoji，则我们也用emoji回复（90%概率）
        if random.random() < 0.9:
            # 识别用户emoji的情感，返回对应的emoji
            user_emotion = get_emoji_emotion(user_message)
            response_emoji = get_response_emoji(user_emotion)
            return [response_emoji]
    
    message = message.replace('\\"', '#')

    if count == 1:
        cleaned = clean_sentence(message)
        # 确保即使清理后内容不为空
        if len(cleaned) == 0:
            return [message]  # 如果清理后为空，返回原始消息
        return [cleaned]
    elif count == 0:
        return [message]

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
    # 过滤掉长度小于或等于1的句子，但保留有意义的符号如波浪号
    result = [sentence for sentence in result if len(sentence) > 1 or (len(sentence) == 1 and sentence in '~！!。.?？…')]

    # 只对第一个句子进行处理，50%的概率删除单独的口癖词
    if len(result) > 0:
        first_sentence = result[0]
        interjections = {"哼", "哈", "哎呀", "嗯", "哦", "呃", "啊", "哎", "咦", "嘘", "哼哼", "哈哈", "嘿嘿"}
        
        # 检查是否是单独的口癖词（长度较短且在口癖词列表中）
        if first_sentence.strip() in interjections and len(first_sentence.strip()) <= 2:
            # 50%的概率删除
            if random.random() < 0.5:
                result.pop(0)
                # 如果删除了第一个句子，确保至少有一个句子
                if not result and sentences:
                    result.append(sentences[0])

    # print(f"最终结果: {result}")
    return result


def upload_to_oss(voice_output_path, user_id):
    custom_logger.info(f"Uploading voice file to OSS for user: {user_id}")
    file_key_prefix = "message_chat"
    file_key = file_key_prefix + f"/{uuid.uuid4()}_{user_id}_{time.time()}.mp3"
    bucket = get_oss_bucket()
    try:
        upload_result = bucket.put_object_from_file(file_key, voice_output_path)
        if upload_result.status == 200:
            voice_response_url = f"https://pillow-chat.oss-cn-shanghai.aliyuncs.com/{file_key}"
            custom_logger.info(f"Voice file uploaded successfully: {voice_response_url}")
            return file_key
    except Exception as e:
        custom_logger.error(f"Error uploading file to OSS: {str(e)}")
    return None

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