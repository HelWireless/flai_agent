from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from src.api.routes import router
from src.custom_logger import *
def create_app() -> FastAPI:
    app = FastAPI(title="Pillow Talk", debug=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app

app = create_app()


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    custom_logger.info("=" * 60)
    custom_logger.info("🚀 Flai Agent 正在启动...")
    custom_logger.info("=" * 60)
    
    # 1. 预加载配置
    from src.core.config_loader import get_config_loader
    config_loader = get_config_loader()
    
    try:
        # 预加载所有配置到缓存
        config_loader.get_characters()
        config_loader.get_character_openers()
        config_loader.get_emotions()
        config_loader.get_responses()
        config_loader.get_constants()
        custom_logger.info("✅ 配置文件加载完成")
    except Exception as e:
        custom_logger.error(f"❌ 配置文件加载失败: {e}")
        raise
    
    # 2. 日志清理已在 custom_logger 初始化时完成
    
    custom_logger.info("=" * 60)
    custom_logger.info("✅ 应用启动完成")
    custom_logger.info(f"📚 API 文档: http://localhost:8000/docs")
    custom_logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    custom_logger.info("=" * 60)
    custom_logger.info("👋 Flai Agent 正在关闭...")
    custom_logger.info("=" * 60)
    # 清理资源（如需要）


async def set_body(request: Request):
    receive_ = await request._receive()
    async def receive():
        return receive_
    request._receive = receive

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: Exception):
    await set_body(request)
    request_text = (await request.body()).decode("utf-8")[:100]  # 安全读取 body 并限制长度
    custom_logger.error(f'请求发生异常，记录request的请求体如下:{request_text},exc:{exc}')
    return JSONResponse(
        status_code=exc.status_code if isinstance(exc, HTTPException) else 500,
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