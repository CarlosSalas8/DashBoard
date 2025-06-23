import pandas as pd
import csv
from database import db

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
