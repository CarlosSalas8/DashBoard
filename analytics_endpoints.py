from fastapi import APIRouter
from database import db
from models import FilterParams
from models import FilterLocationParams


router = APIRouter()


@router.post("/analytics")
async def get_analytics(filters: FilterParams):
    query = {}

    # Ignorar si el valor es "string", vacío o 0 (en el caso de floats)
    if filters.country and filters.country.lower() != "string":
        query["country"] = filters.country
    if filters.city and filters.city.lower() != "string":
        query["city"] = filters.city
    if filters.province and filters.province.lower() != "string":
        query["province"] = filters.province
    if filters.service and filters.service != 0:
        query["service"] = filters.service
    if filters.meal_list and filters.meal_list.lower() != "string":
        query["meals_list"] = {"$in": [filters.meal_list]}
    if filters.cuisines_list and filters.cuisines_list.lower() != "string":
        query["cuisines_list"] = {"$in": [filters.cuisines_list]}
    if filters.price_level_cat and filters.price_level_cat.lower() != "string":
        query["price_level_cat"] = filters.price_level_cat

    collection = db["restaurants"]
    restaurants = await collection.find(query).to_list(length=10000)

    total = len(restaurants)

    vegetarian_count = sum(1 for r in restaurants if r.get("vegetarian_friendly", "").lower() == "si")
    vegan_count = sum(1 for r in restaurants if r.get("vegan_options", "").lower() == "si")
    gluten_free_count = sum(1 for r in restaurants if r.get("gluten_free", "").lower() == "si")

    rating_sum = sum(r.get("avg_rating", 0) for r in restaurants if r.get("avg_rating") is not None)
    rating_avg = rating_sum / total if total else 0

    price_categories = {"barato": 1, "regular": 2, "caro": 3}
    price_total = sum(price_categories.get(r.get("price_level_cat", "").lower(), 0) for r in restaurants)
    price_avg_num = price_total / total if total else 0

    price_cat_avg = (
        "barato" if price_avg_num < 1.5 else
        "regular" if price_avg_num < 2.5 else
        "caro"
    ) if total else "sin datos"

    return {
        "total_restaurants": total,
        "vegetarian_friendly": vegetarian_count,
        "vegan_options": vegan_count,
        "gluten_free": gluten_free_count,
        "avg_rating": round(rating_avg, 2),
        "avg_price_category": price_cat_avg
    }





@router.post("/restaurant-locations")
async def get_restaurant_locations(filters: FilterLocationParams):
    query = {}

    if filters.country:
        query["country"] = filters.country
    if filters.province:
        query["province"] = filters.province
    if filters.city:
        query["city"] = filters.city

    projection = {
        "_id": 0,
        "restaurant_name": 1,
        "latitude": 1,
        "longitude": 1,
        "city": 1,
        "province": 1,
        "country": 1,
        "avg_rating": 1,
        "cuisines_list": 1
    }

    collection = db["restaurants"]
    results = await collection.find(query, projection).to_list(length=10000)

    return {"restaurants": results}











@router.get("/restaurants_count")
async def restaurants_count():
    count = await db["restaurants"].count_documents({})
    return {"count": count}


@router.get("/restaurants_by_country")
async def restaurants_by_country():
    pipeline = [
        {"$group": {"_id": "$country", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    result = await db["restaurants"].aggregate(pipeline).to_list(length=None)
    return result


@router.get("/top_tags_by_country")
async def top_tags_by_country():
    pipeline = [
        {"$unwind": "$top_tags_list"},
        {"$group": {"_id": {"country": "$country", "tag": "$top_tags_list"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$group": {"_id": "$_id.country", "top_tags": {"$push": {"tag": "$_id.tag", "count": "$count"}}}},
        {"$project": {"top_tags": {"$slice": ["$top_tags", 5]}}}
    ]
    result = await db["restaurants"].aggregate(pipeline).to_list(length=None)
    return result

@router.get("/top_cuisines_by_country")
async def top_cuisines_by_country():
    pipeline = [
        {"$unwind": "$cuisines_list"},
        {"$group": {"_id": {"country": "$country", "cuisine": "$cuisines_list"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$group": {"_id": "$_id.country", "top_cuisines": {"$push": {"cuisine": "$_id.cuisine", "count": "$count"}}}},
        {"$project": {"top_cuisines": {"$slice": ["$top_cuisines", 5]}}}
    ]
    result = await db["restaurants"].aggregate(pipeline).to_list(length=None)
    return result

@router.get("/avg_rating_by_cuisine")
async def avg_rating_by_cuisine():
    pipeline = [
        {"$match": {"avg_rating": {"$ne": 0}}},  # excluye los nulos
        {"$unwind": "$cuisines_list"},
        {"$group": {"_id": "$cuisines_list", "avg_rating": {"$avg": "$avg_rating"}}},
        {"$sort": {"avg_rating": -1}}
    ]
    result = await db["restaurants"].aggregate(pipeline).to_list(length=None)
    return result

@router.get("/filters/countries")
async def get_countries():
    result = await db["restaurants"].distinct("country")
    return result
