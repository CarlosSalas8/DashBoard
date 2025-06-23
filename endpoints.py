from fastapi import APIRouter
from operations import insert_data_from_csv, get_open_hours

router = APIRouter()

@router.get("/")
async def root():
    return {"message": "FastAPI funcionando correctamente"}

@router.post("/insert_data")
async def insert_data():
    return await insert_data_from_csv("c:/Users/casal/Downloads/clean_tripadvisor3.csv")

@router.get("/get_open_hours")
async def fetch_open_hours():
    return await get_open_hours()
