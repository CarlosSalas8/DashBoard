from fastapi import APIRouter
from database import db
from models import FilterParams
from database import collection
from models import FilterLocationParams


router = APIRouter()


@router.post("/analytics")
async def get_analytics(filters: FilterParams):
    # Construir el match dinámico
    match_stage = {}
    if filters.country and filters.country.lower() != "string":
        match_stage["country"] = filters.country
    if filters.city and filters.city.lower() != "string":
        match_stage["city"] = filters.city
    if filters.province and filters.province.lower() != "string":
        match_stage["province"] = filters.province
    if filters.service is not None and filters.service != 0:
        match_stage["service"] = filters.service
    if filters.meal_list and filters.meal_list.lower() != "string":
        match_stage["meals_list"] = {"$in": [filters.meal_list]}
    if filters.cuisines_list and filters.cuisines_list.lower() != "string":
        match_stage["cuisines_list"] = {"$in": [filters.cuisines_list]}
    if filters.price_level_cat and filters.price_level_cat.lower() != "string":
        match_stage["price_level_cat"] = filters.price_level_cat

    # Pipeline de agregación
    pipeline = [
        {"$match": match_stage},
        {"$project": {
            "vegetarian": {"$eq": [{"$toLower": "$vegetarian_friendly"}, "si"]},
            "vegan": {"$eq": [{"$toLower": "$vegan_options"}, "si"]},
            "gluten": {"$eq": [{"$toLower": "$gluten_free"}, "si"]},
            "rating": {
                "$cond": [
                    {"$and": [
                        {"$gt": ["$avg_rating", 0]},
                        {"$isNumber": "$avg_rating"}
                    ]},
                    "$avg_rating",
                    None
                ]
            },
            "price_value": {
                "$switch": {
                    "branches": [
                        {"case": {"$eq": [{"$toLower": "$price_level_cat"}, "barato"]}, "then": 1},
                        {"case": {"$eq": [{"$toLower": "$price_level_cat"}, "regular"]}, "then": 2},
                        {"case": {"$eq": [{"$toLower": "$price_level_cat"}, "caro"]}, "then": 3}
                    ],
                    "default": None
                }
            }
        }},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "vegetarian_count": {"$sum": {"$cond": ["$vegetarian", 1, 0]}},
            "vegan_count": {"$sum": {"$cond": ["$vegan", 1, 0]}},
            "gluten_free_count": {"$sum": {"$cond": ["$gluten", 1, 0]}},
            "rating_sum": {"$sum": "$rating"},
            "rating_count": {"$sum": {"$cond": [{"$ne": ["$rating", None]}, 1, 0]}},
            "price_sum": {"$sum": "$price_value"},
        }}
    ]

    result = await collection.aggregate(pipeline).to_list(length=1)

    if not result:
        return {
            "total_restaurants": 0,
            "vegetarian_friendly": 0,
            "vegan_options": 0,
            "gluten_free": 0,
            "avg_rating": 0,
            "avg_price_category": "sin datos"
        }

    data = result[0]
    rating_avg = data["rating_sum"] / data["rating_count"] if data["rating_count"] else 0
    price_avg_num = data["price_sum"] / data["total"] if data["total"] else 0
    price_cat_avg = (
        "barato" if price_avg_num < 1.5 else
        "regular" if price_avg_num < 2.5 else
        "caro"
    ) if data["total"] else "sin datos"

    return {
        "total_restaurants": data["total"],
        "vegetarian_friendly": data["vegetarian_count"],
        "vegan_options": data["vegan_count"],
        "gluten_free": data["gluten_free_count"],
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
