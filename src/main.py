from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from src.api.routes import router
from src.custom_logger import custom_logger
import json
from fastapi.exceptions import RequestValidationError
import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    custom_logger.info("=" * 60)
    custom_logger.info("🚀 深壤 Agent 正在启动...")
    custom_logger.info("=" * 60)
    
    # 预加载配置
    from src.core.config_loader import get_config_loader
    config_loader = get_config_loader()
    
    try:
        config_loader.get_characters()
        config_loader.get_character_openers()
        config_loader.get_emotion_states()
        config_loader.get_responses()
        config_loader.get_constants()
        custom_logger.info("✅ 配置文件加载完成")
    except Exception as e:
        custom_logger.error(f"❌ 配置文件加载失败: {e}")
        raise
    
    custom_logger.info("=" * 60)
    custom_logger.info("✅ 应用启动完成")
    custom_logger.info(f"📚 API 文档: http://localhost:8000/docs")
    custom_logger.info("=" * 60)
    
    yield  # 应用运行
    
    # 关闭事件
    custom_logger.info("=" * 60)
    custom_logger.info("👋 深壤 Agent 正在关闭...")
    custom_logger.info("=" * 60)


def create_app() -> FastAPI:
    # 控制第三方库的日志级别，避免在生产环境输出过多调试信息
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("dashscope").setLevel(logging.INFO)
    
    app = FastAPI(title="Pillow Talk", debug=False, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证错误，记录请求内容"""
        try:
            # 尝试读取请求体
            body = await request.body()
            try:
                body_json = json.loads(body.decode('utf-8'))
                custom_logger.info(f"Validation error for request: {body_json}")
            except:
                custom_logger.info(f"Validation error for request (raw): {body.decode('utf-8') if body else 'Empty body'}")
        except Exception as e:
            custom_logger.error(f"Error reading request body in validation exception handler: {e}")
        
        custom_logger.error(f"Validation error: {exc}")
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()}
        )
    
    @app.middleware("http")
    async def log_all_requests(request: Request, call_next):
        # 记录所有请求的基本信息
        custom_logger.info(f"Incoming request: {request.method} {request.url}")
        
        # 特别关注所有 POST 聊天/存档请求
        if request.method == "POST":
            url_str = str(request.url)
            # 匹配主要的业务路径
            if any(path in url_str for path in ["/chat", "/pillow", "/freak-world", "/coc"]):
                try:
                    # 读取请求体
                    body = await request.body()
                    # 尝试解析为JSON
                    try:
                        body_json = json.loads(body.decode('utf-8'))
                        # 脱敏敏感信息（可选，目前主要是业务数据）
                        custom_logger.info(f"Request Body [{url_str}]: {body_json}")
                    except:
                        # 如果不是JSON格式，记录原始内容
                        custom_logger.info(f"Request Body (raw) [{url_str}]: {body.decode('utf-8') if body else 'Empty body'}")
                except Exception as e:
                    custom_logger.error(f"Error reading request body in middleware: {e}")
        
        try:
            response = await call_next(request)
            custom_logger.info(f"Response: {response.status_code} for {request.method} {request.url}")
            return response
        except Exception as e:
            custom_logger.error(f"Middleware caught unhandled exception: {str(e)}")
            raise e
    
    return app

app = create_app()

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    custom_logger.error(f'Request exception: {exc.status_code}: {exc.detail}')
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    try:
        # 尝试读取请求体，但如果已经读取过会抛出异常
        request_text = await request.body()
    except RuntimeError:
        # 如果无法读取请求体，设置为空字符串
        request_text = b""
    except Exception:
        # 处理其他可能的异常
        request_text = b""

    # 继续处理异常日志记录等
    custom_logger.error(f"Unhandled exception: {str(exc)}\nRequest: {request_text.decode(errors='ignore')}")

    # 返回适当的响应
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


app.include_router(router)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)