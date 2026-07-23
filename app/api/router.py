from fastapi import APIRouter

from app.api.accounts import router as accounts_router
from app.api.orders import router as orders_router
from app.api.positions import router as positions_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(accounts_router)
api_router.include_router(orders_router)
api_router.include_router(positions_router)
