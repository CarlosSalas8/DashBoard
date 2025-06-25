from fastapi import APIRouter, HTTPException
from operations import get_catalog, insert_data_from_csv, get_open_hours, list_catalogs, rebuild_catalogs

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


# ————————————————
# Endpoints de catálogos
# ————————————————

@router.post("/catalogs/build", summary="(Re)construir catálogos")
async def build_all_catalogs():
    return await rebuild_catalogs()

@router.get("/catalogs", summary="Listar todos los catálogos")
async def fetch_all_catalogs():
    catalogs = await list_catalogs()
    return {"catalogs": catalogs}

@router.get("/catalogs/{catalog_type}", summary="Obtener un catálogo por tipo")
async def fetch_catalog(catalog_type: str):
    doc = await get_catalog(catalog_type)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Catálogo '{catalog_type}' no existe")
    # doc ya está limpio
    return doc["items"]