from fastapi import APIRouter

from app.api.v1 import auth, health, jobs, sessions, trainings

router = APIRouter(prefix="/api/v1")
for module in (health, auth, trainings, sessions, jobs):
    router.include_router(module.router)
