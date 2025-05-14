from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from src.api.routes import router

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
    request_text = await request.body(2)
    request_text = str(request_text.decode('utf-8'))
    app.logger.warning(f'请求发生异常，记录request的请求体如下:{request_text}')
    return JSONResponse(
        status_code=exc.status_code if isinstance(exc, HTTPException) else 500,
        content={"detail": exc.detail}
    )

# 也可以添加通用异常处理
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    await set_body(request)  # 确保可以读取 body
    request_text = await request.body()
    app.logger.error(f"未处理的异常: {exc}, 请求体: {request_text.decode('utf-8')}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后再试。"},
    )

app.include_router(router)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)