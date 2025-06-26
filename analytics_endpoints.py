from typing import Any, Optional
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from database import db
from models import FilterParams
from database import collection
from models import FilterLocationParams
from fastapi import APIRouter, Query
import math

router = APIRouter()

def sanitize(obj: Any) -> Any:
    """
    Recursively replace NaN or infinite floats with None so JSON serialization won't fail.
    """
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

def is_valid_filter_value(value: Any) -> bool:
    """
    Returns False for None, empty string, "string", or empty list.
    """
    if value is None:
        return False
    if isinstance(value, str):
        s = value.strip().lower()
        return s != "" and s != "string"
    if isinstance(value, list):
        return bool(value) and all(
            isinstance(item, str) and item.strip().lower() not in ("", "string")
            for item in value
        )
    return True

@router.post("/analytics")
async def get_analytics(
    filters:   FilterParams,
    north:     float = Query(..., ge=-90, le=90),
    south:     float = Query(..., ge=-90, le=90),
    east:      float = Query(..., ge=-180, le=180),
    west:      float = Query(..., ge=-180, le=180),
    zoom:      float = Query(..., ge=0, le=22),
    page:      int   = Query(1, ge=1),
    limit:    Optional[int] = Query(None, ge=1, le=1000),
):
    try:
        # 1) Build match_stage from filters
        match_stage: dict = {}
        if is_valid_filter_value(filters.country):
            match_stage["country"] = (
                {"$in": filters.country}
                if isinstance(filters.country, list)
                else filters.country
            )
        for fld in ("city", "province", "claimed", "price_level_cat"):
            v = getattr(filters, fld)
            if is_valid_filter_value(v):
                match_stage[fld] = v
        for fld in ("service", "food"):
            v = getattr(filters, fld)
            if v is not None and v > 0:
                match_stage[fld] = {"$gte": v}
        for filt, dbf in (
            ("meal_list", "meals_list"),
            ("cuisines_list", "cuisines_list"),
            ("top_tags_list", "top_tags_list"),
        ):
            vals = getattr(filters, filt)
            if is_valid_filter_value(vals):
                match_stage[dbf] = {"$in": vals}

        # 2) Apply bounding box
        match_stage["latitude"]  = {"$gte": south, "$lte": north}
        match_stage["longitude"] = {"$gte": west,  "$lte": east}

        # 3) Compute overall stats with percentages
        stats_pipeline = [
            {"$match": match_stage},
            {"$addFields": {
                "vegan":          {"$eq":[{"$toLower":{"$toString":"$vegan_options"}}, "si"]},
                "gluten":         {"$eq":[{"$toLower":{"$toString":"$gluten_free"}},   "si"]},
                "valid_rating":   {"$cond":[
                                      {"$and":[
                                          {"$ne":["$avg_rating", None]},
                                          {"$isNumber":"$avg_rating"},
                                          {"$gt":["$avg_rating",   0]},
                                          {"$lte":["$avg_rating",   5]}
                                      ]},
                                      "$avg_rating",
                                      None
                                  ]},
                "price_numeric":  {"$switch":{
                                      "branches":[
                                          {"case":{"$eq":[{"$toLower":{"$toString":"$price_level_cat"}}, "barato"]},  "then":1},
                                          {"case":{"$eq":[{"$toLower":{"$toString":"$price_level_cat"}}, "regular"]}, "then":2},
                                          {"case":{"$eq":[{"$toLower":{"$toString":"$price_level_cat"}}, "caro"]},    "then":3}
                                      ],
                                      "default": None
                                  }}
            }},
            {"$group": {
                "_id": None,
                "total":             {"$sum": 1},
                "vegan_count":       {"$sum":{"$cond":["$vegan", 1, 0]}},
                "gluten_free_count": {"$sum":{"$cond":["$gluten",1,0]}},
                "rating_sum":        {"$sum":{"$ifNull":["$valid_rating",0]}},
                "rating_count":      {"$sum":{"$cond":[{"$ne":["$valid_rating",None]},1,0]}},
                "premium_count":     {"$sum":{"$cond":[{"$eq":["$price_numeric",3]},1,0]}},
                "price_sum":         {"$sum":{"$ifNull":["$price_numeric",0]}},
                "price_count":       {"$sum":{"$cond":[{"$ne":["$price_numeric",None]},1,0]}}
            }}
        ]
        stats_res = await collection.aggregate(stats_pipeline).to_list(length=1)

        overall_stats = {
            "total_restaurants":     0,
            "pct_total_restaurants": 0.0,
            "vegan_count":           0,
            "pct_vegan":             0.0,
            "premium_count":         0,
            "pct_premium":           0.0,
            "avg_rating":            0.0,
            "pct_avg_rating":        0.0,
            "gluten_free_count":     0,
            "pct_gluten_free":       0.0,
            "avg_price_category":    "sin datos",
            "avg_price_numeric":     0.0
        }
        if stats_res and stats_res[0].get("total", 0) > 0:
            d = stats_res[0]
            total   = d["total"]
            vegan   = d["vegan_count"]
            gluten  = d["gluten_free_count"]
            premium = d["premium_count"]
            avg_rt  = d["rating_sum"] / d["rating_count"] if d["rating_count"] > 0 else 0.0
            price_avg_num = d["price_sum"] / d["price_count"] if d["price_count"] > 0 else 0.0
            price_cat     = (
                "barato"  if price_avg_num < 1.5 else
                "regular" if price_avg_num < 2.5 else
                "caro"
            )

            # Total dataset for pct_total_restaurants
            dataset_total = await collection.count_documents({})

            overall_stats.update({
                "total_restaurants":     total,
                "pct_total_restaurants": round(total / dataset_total * 100, 2) if dataset_total > 0 else 0.0,
                "vegan_count":           vegan,
                "pct_vegan":             round(vegan / total * 100, 2),
                "premium_count":         premium,
                "pct_premium":           round(premium / total * 100, 2),
                "avg_rating":            round(avg_rt, 2),
                "pct_avg_rating":        round(avg_rt / 5 * 100, 2),
                "gluten_free_count":     gluten,
                "pct_gluten_free":       round(gluten / total * 100, 2),
                "avg_price_category":    price_cat,
                "avg_price_numeric":     round(price_avg_num, 2)
            })

        # 4) Meals list distribution
        meals_pipeline = [
            {"$match": match_stage},
            {"$unwind": "$meals_list"},
            {"$group": {"_id":"$meals_list","count":{"$sum":1}}},
            {"$project":{"_id":0,"meal":"$_id","count":1}}
        ]
        meals_dist = await collection.aggregate(meals_pipeline).to_list()

        # 5) Top tags list distribution
        tags_pipeline = [
            {"$match": match_stage},
            {"$unwind": "$top_tags_list"},
            {"$group": {"_id":"$top_tags_list","count":{"$sum":1}}},
            {"$project":{"_id":0,"tag":"$_id","count":1}}
        ]
        tags_dist = await collection.aggregate(tags_pipeline).to_list()


        # 6) Clusters vs. listing
        if zoom <= 15:
            # clustering
            if zoom <= 6:
                max_px = 190
            elif zoom <= 12:
                max_px = 120
            else:
                max_px = 80
            deg_px    = 360.0 / (256 * (2 ** zoom))
            cell_size = max_px * deg_px

            cluster_pipeline = [
                {"$match": match_stage},

                # recalculate derived fields per document
                {"$addFields": {
                    "vegan":         {"$eq":[{"$toLower":{"$toString":"$vegan_options"}}, "si"]},
                    "gluten":        {"$eq":[{"$toLower":{"$toString":"$gluten_free"}},   "si"]},
                    "valid_rating":  {"$cond":[
                                         {"$and":[
                                             {"$ne":["$avg_rating", None]},
                                             {"$isNumber":"$avg_rating"},
                                             {"$gt":["$avg_rating",   0]},
                                             {"$lte":["$avg_rating",   5]}
                                         ]},
                                         "$avg_rating",
                                         None
                                     ]},
                    "price_numeric": {"$switch":{
                                         "branches":[
                                             {"case":{"$eq":[{"$toLower":{"$toString":"$price_level_cat"}}, "barato"]},  "then":1},
                                             {"case":{"$eq":[{"$toLower":{"$toString":"$price_level_cat"}}, "regular"]}, "then":2},
                                             {"case":{"$eq":[{"$toLower":{"$toString":"$price_level_cat"}}, "caro"]},    "then":3}
                                         ],
                                         "default": None
                                     }}
                }},

                # compute grid cell
                {"$addFields": {
                    "cellX": {"$floor": {"$divide":[{"$add":["$longitude",180]}, cell_size]}},
                    "cellY": {"$floor": {"$divide":[{"$add":["$latitude",  90]}, cell_size]}}
                }},

                # group per cell
                {"$group": {
                    "_id":               {"x":"$cellX","y":"$cellY"},
                    "total_restaurants": {"$sum":1},
                    "latitude":          {"$avg":"$latitude"},
                    "longitude":         {"$avg":"$longitude"},
                    "vegan_count":       {"$sum":{"$cond":["$vegan",1,0]}},
                    "gluten_free_count": {"$sum":{"$cond":["$gluten",1,0]}},
                    "avgRatingCluster":  {"$avg":"$valid_rating"},
                    "avgPriceCluster":   {"$avg":"$price_numeric"},
                    "premium_count":     {"$sum":{"$cond":[{"$eq":["$price_numeric",3]},1,0]}}
                }},

                # final shape with percentages
                {"$project": {
                    "_id":                0,
                    "total_restaurants":  1,
                    "latitude":           {"$round":["$latitude",6]},
                    "longitude":          {"$round":["$longitude",6]},
                    "vegan_count":        1,
                    "pct_vegan":          {"$round":[{"$multiply":[{"$divide":["$vegan_count","$total_restaurants"]},100]},2]},
                    "gluten_free_count":  1,
                    "pct_gluten_free":    {"$round":[{"$multiply":[{"$divide":["$gluten_free_count","$total_restaurants"]},100]},2]},
                    "avg_rating":         {"$round":["$avgRatingCluster",2]},
                    "pct_avg_rating":     {"$round":[{"$multiply":[{"$divide":["$avgRatingCluster",5]},100]},2]},
                    "premium_count":      1,
                    "pct_premium":        {"$round":[{"$multiply":[{"$divide":["$premium_count","$total_restaurants"]},100]},2]},
                    "avg_price_category": {"$switch":{
                                              "branches":[
                                                  {"case":{"$lt":["$avgPriceCluster",1.5]},"then":"barato"},
                                                  {"case":{"$lt":["$avgPriceCluster",2.5]},"then":"regular"}
                                              ],
                                              "default":"caro"
                                          }}
                }},

                {"$limit": limit or 500}
            ]
            clusters = await collection.aggregate(cluster_pipeline).to_list(length=limit or 500)

            payload = {
                "overall_stats":   overall_stats,
                "meals_list":      meals_dist,
                "top_tags_list":   tags_dist,
                "clusters":        clusters
            }
        else:
            # paginated listing
            total_count = await collection.count_documents(match_stage)
            eff_limit   = limit or min(total_count, 100)
            total_pages = math.ceil(total_count / eff_limit) if eff_limit > 0 else 1
            page        = min(page, total_pages) if total_pages else 1
            skip        = (page - 1) * eff_limit

            cursor = (
                collection
                .find(match_stage, {
                    "_id": 0,
                    "name": 1,
                    "city": 1,
                    "country": 1,
                    "latitude": 1,
                    "longitude": 1,
                    "avg_rating": 1,
                    "price_level_cat": 1,
                    "claimed": 1,
                    "vegan_options": 1,
                    "gluten_free": 1,
                    "meals_list": 1,
                    "top_tags_list": 1
                })
                .skip(skip)
                .limit(eff_limit)
            )

            restaurants = await cursor.to_list(length=eff_limit)
            for doc in restaurants:
                for coord in ("latitude","longitude"):
                    v = doc.get(coord)
                    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                        doc[coord] = None

            payload = {
                "overall_stats":   overall_stats,
                "meals_list":      meals_dist,
                "top_tags_list":   tags_dist,
                "restaurants":     restaurants,
                "pagination": {
                    "page":          page,
                    "limit":         eff_limit,
                    "total_pages":   total_pages,
                    "total_results": total_count
                }
            }

        return JSONResponse(content=sanitize(payload))

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )





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
