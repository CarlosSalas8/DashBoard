from bson import ObjectId
import math

def clean_mongo_document(doc):
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            doc[key] = None  # o puedes poner 0 si prefieres
        elif isinstance(value, list):
            doc[key] = [clean_mongo_document(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            doc[key] = clean_mongo_document(value)
    return doc