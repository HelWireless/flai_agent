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
    request_text = await request.body()
    custom_logger.error(f"未处理的异常: {exc}, 请求体: {request_text.decode('utf-8')[:100]}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后再试。"},
    )

app.include_router(router)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)