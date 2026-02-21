"""API v1 router aggregation"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, agents, machines, analytics, commands, users

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router)
router.include_router(agents.router)
router.include_router(machines.router)
router.include_router(analytics.router)
router.include_router(commands.router)
router.include_router(users.router)
