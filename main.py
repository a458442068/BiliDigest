from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.config import settings
from src.utils.logger import setup_logger

setup_logger(settings.log_level)

app = FastAPI(
    title="BiliDigest",
    description="B站视频转文字摘要服务",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.port,
        timeout_keep_alive=600,
        timeout_graceful_shutdown=600,
    )
