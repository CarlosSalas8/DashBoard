from fastapi import FastAPI
from endpoints import router
from analytics_endpoints import router as analytics_router

app = FastAPI()
app.include_router(router)
app.include_router(analytics_router)
