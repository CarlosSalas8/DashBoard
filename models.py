from pydantic import BaseModel
from typing import List
from typing import Optional

class Restaurant(BaseModel):
    country: str
    restaurant_link: str
    restaurant_name: str
    claimed: str
    price_level: str
    vegetarian_friendly: str
    vegan_options: str
    gluten_free: str
    original_open_hours: List[dict]
    popularity_detailed_location: str
    popularity_generic_location: str
    continent: str
    province: str
    city: str
    latitude: float
    longitude: float
    avg_rating: float
    food: float
    service: float
    value: float
    open_days_per_week: int
    total_reviews_count: int
    excellent: int
    very_good: int
    average: int
    poor: int
    terrible: int
    pop_detailed_pos: int
    pop_detailed_total: int
    pop_generic_pos: int
    pop_generic_total: int
    meals_list: List[str]
    top_tags_list: List[str]
    cuisines_list: List[str]
    avg_rating_cat: str
    food_cat: str
    service_cat: str
    value_cat: str
    open_days_per_week_cat: str
    price_level_cat: str


class FilterParams(BaseModel):
    country: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    service: Optional[float] = None
    meal_list: Optional[str] = None
    cuisines_list: Optional[str] = None
    price_level_cat: Optional[str] = None


class FilterLocationParams(BaseModel):
    country: Optional[str]
    province: Optional[str]
    city: Optional[str]