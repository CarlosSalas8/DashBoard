from bson import ObjectId
import math

def clean_mongo_document(doc: dict) -> dict:
    for key, value in doc.items():
        # 1) ObjectId → str
        if isinstance(value, ObjectId):
            doc[key] = str(value)

        # 2) Float nan/inf → None
        elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            doc[key] = None

        # 3) Dict → recursivo
        elif isinstance(value, dict):
            doc[key] = clean_mongo_document(value)

        # 4) List → limpiamos cada elemento
        elif isinstance(value, list):
            cleaned_list = []
            for item in value:
                if isinstance(item, dict):
                    cleaned_list.append(clean_mongo_document(item))
                elif isinstance(item, float) and (math.isnan(item) or math.isinf(item)):
                    cleaned_list.append(None)
                else:
                    cleaned_list.append(item)
            doc[key] = cleaned_list

        # resto de tipos (str, int, etc.) se quedan tal cual

    return doc
