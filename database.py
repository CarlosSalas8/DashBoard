from motor.motor_asyncio import AsyncIOMotorClient

# Crear cliente de MongoDB
client = AsyncIOMotorClient('mongodb://localhost:27017')

# Base de datos
db = client["tripadvisor_db"]

# Colección de restaurantes
collection = db["restaurants"]
