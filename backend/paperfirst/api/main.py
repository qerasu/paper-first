from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from paperfirst.api.routes import router
from paperfirst.core.config import get_settings, parse_cors_origins


settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.backend_cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
