"""
语音服务 - 处理文字转语音
"""
import os
import uuid
from fastapi import HTTPException

from ..schemas import Text2Voice, Text2VoiceResponse
from ..custom_logger import custom_logger
from ..utils import upload_to_oss
from .speech_api import SpeechAPI


class VoiceService:
    """语音转换服务"""
    
    def __init__(self, config: dict):
        """
        初始化语音服务
        
        Args:
            config: 应用配置
        """
        self.config = config
    
    async def text_to_voice(self, request: Text2Voice) -> Text2VoiceResponse:
        """
        将文字转换为语音
        
        Args:
            request: 文字转语音请求
        
        Returns:
            语音文件URL
        """
        custom_logger.info(
            f"Converting text to voice for user: {request.user_id}, "
            f"text_id: {request.text_id}"
        )
        
        # 1. 初始化语音 API
        speech_api = SpeechAPI(self.config["speech_api"], str(request.user_id))
        request_body = speech_api.generate_request_body(request.text)
        
        # 2. 生成语音文件
        api_url = "https://openspeech.bytedance.com/api/v1/tts"
        voice_output_path = f"voice_tmp/{request.user_id}_{uuid.uuid4()}_{request.text_id}.mp3"
        os.makedirs(os.path.dirname(voice_output_path), exist_ok=True)
        
        try:
            speech_api.send_request(api_url, request_body, voice_output_path)
            custom_logger.info(f"Voice file generated: {voice_output_path}")
        except Exception as e:
            custom_logger.error(f"Failed to generate voice: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to generate voice: {str(e)}")
        
        # 3. 上传到 OSS
        file_key = upload_to_oss(voice_output_path, str(request.user_id))
        if not file_key:
            custom_logger.error("Failed to upload voice file to OSS")
            raise HTTPException(status_code=500, detail="Failed to upload voice file to OSS")
        
        voice_response_url = f"https://pillow-chat.oss-cn-shanghai.aliyuncs.com/{file_key}"
        custom_logger.info(f"Voice file uploaded successfully: {voice_response_url}")
        
        return Text2VoiceResponse(
            user_id=int(request.user_id),
            text_id=int(request.text_id),
            url=voice_response_url
        )

