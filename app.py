from fastapi import FastAPI
from endpoints import router
from analytics_endpoints import router as analytics_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                # o lista de tus orígenes: ["http://localhost:5500"]
    allow_credentials=True,
    allow_methods=["GET","POST","OPTIONS","PUT","DELETE"],
    allow_headers=["*"],                # para que acepte Content-Type, Authorization, etc.
)

app.include_router(router)
app.include_router(analytics_router)
