from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.chat import router as chat_router
from app.api.products import router as products_router
from app.api.users import router as users_router
from app.db.database import check_database

app = FastAPI(
    title="Clothing AI Assistant API",
    version="0.2.0",
    description="Backend API for the clothing AI assistant.",
)

app.include_router(chat_router)
app.include_router(products_router)
app.include_router(users_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "clothing-ai-assistant",
    }


@app.get("/db/health")
def database_health_check():
    try:
        check_database()
        return {
            "status": "ok",
            "database": "connected",
        }
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "database": "unavailable",
            },
        )
