# ------------------------------
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto 
# - Claudia Moya Rodríguez
# ------------------------------

# ------------------------------
# CONFIGURACION DE MYSQL
# ------------------------------
MYSQL_HOST = "localhost"
MYSQL_USER = "..."
MYSQL_PASSWORD = "..."
MYSQL_DATABASE = "amazon_reviews_mysql"

# ------------------------------
# CONFIGURACION DE MONGODB
# ------------------------------
MONGO_HOST = "localhost"
MONGO_PORT = 27017
MONGO_DATABASE = "amazon_reviews_mongo"
MONGO_COLLECTION_REVIEWS = "reviews_texto"
MONGO_CONNECTION_STRING = f"mongodb://{MONGO_HOST}:{MONGO_PORT}"

# ------------------------------
# CONFIGURACION DE NEO4J
# ------------------------------
NEO4J_HOST = "localhost"
NEO4J_PORT = 7687
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "aaaaaaaa"

# ------------------------------
# RUTAS DE LOS FICHEROS
# ------------------------------
RUTA_TOYS_AND_GAMES = "Toys_and_Games_5.json"
RUTA_VIDEO_GAMES = "Video_Games_5.json"
RUTA_DIGITAL_MUSIC = "Digital_Music_5.json"
RUTA_MUSICAL_INSTRUMENTS = "Musical_Instruments_5.json"

# ------------------------------
# DATASETS A CARGAR
# Cada tupla:
# (nombre_categoria, ruta_fichero)
# ------------------------------
DATASETS = [
    ("Toys and Games", RUTA_TOYS_AND_GAMES),
    ("Video Games", RUTA_VIDEO_GAMES),
    ("Digital Music", RUTA_DIGITAL_MUSIC),
    ("Musical Instruments", RUTA_MUSICAL_INSTRUMENTS)
]