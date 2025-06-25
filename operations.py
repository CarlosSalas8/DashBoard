import pandas as pd
import csv
from database import db
from utils import clean_mongo_document

def group_hours(hour_str):
    if not isinstance(hour_str, str) or hour_str == "no_disponible":
        return []
    items = [h.strip() for h in hour_str.split(",")]
    grouped = {}
    current_day = None
    for h in items:
        if ":" in h:
            parts = h.split(":", 1)
            if parts[0].lower() in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]:
                current_day = parts[0].lower()
                grouped[current_day] = parts[1]
            elif current_day:
                grouped[current_day] += ", " + h
    return [{"day": d, "hours": grouped[d]} for d in grouped]

async def insert_data_from_csv(filepath):
    df = pd.read_csv(filepath, quoting=csv.QUOTE_ALL, encoding="utf-8", on_bad_lines="error")
    
    for col in ["meals_list", "top_tags_list", "cuisines_list"]:
        df[col] = df[col].apply(lambda x: x.split(",") if isinstance(x, str) and x != "no_disponible" else [])

    df["original_open_hours"] = df["original_open_hours"].apply(group_hours)
    records = df.to_dict(orient="records")
    await db["restaurants"].insert_many(records)
    return {"message": "Datos insertados correctamente"}

async def get_open_hours(limit=100):
    return await db["restaurants"].find({}, {"original_open_hours": 1, "_id": 0}).to_list(limit)
async def rebuild_catalogs():
    catalogs = db["catalogs"]
    # 1) Si existe, la borramos
    if "catalogs" in await db.list_collection_names():
        await catalogs.drop()

    # 2) Creamos de nuevo los tres catálogos
    # — Locations (país→provincias→ciudades)
    pipeline = [
        {"$group": {
            "_id": {"country": "$country", "province": "$province", "city": "$city"}
        }},
        {"$group": {
            "_id": {"country": "$_id.country", "province": "$_id.province"},
            "ciudades": {"$addToSet": "$_id.city"}
        }},
        {"$group": {
            "_id": "$_id.country",
            "provincias": {"$addToSet": {
                "nombre": "$_id.province",
                "ciudades": "$ciudades"
            }}
        }},
        {"$project": {"_id": 0, "nombre": "$_id", "provincias": 1}}
    ]
    locs = await db["restaurants"].aggregate(pipeline).to_list(length=None)

    # — Flat catalogs
    cuisines = await db["restaurants"].distinct("cuisines_list")
    meals    = await db["restaurants"].distinct("meals_list")

    await catalogs.insert_many([
        {"tipo": "locations", "items": locs},
        {"tipo": "cuisines",  "items": cuisines},
        {"tipo": "meals",     "items": meals},
    ])

    return {"message": "Catálogos reconstruidos correctamente."}


async def get_catalog(catalog_type: str):
    doc = await db["catalogs"].find_one({"tipo": catalog_type}, {"_id": 0})
    if not doc:
        return None
    # limpia recursivamente floats nan/inf
    return clean_mongo_document(doc)


async def list_catalogs():
    raw = await db["catalogs"].find({}, {"_id": 0}).to_list(length=None)
    # limpia cada documento completo
    return [clean_mongo_document(doc) for doc in raw]