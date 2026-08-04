# ------------------------------
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodríguez
# ------------------------------

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import BulkWriteError
import json
import pymysql
import time
from datetime import datetime

from configuracion import (
    MYSQL_HOST,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    MONGO_HOST,
    MONGO_PORT,
    MONGO_DATABASE,
    MONGO_COLLECTION_REVIEWS,
    DATASETS
)

# -----------------------------------------------------------
# FUNCIONES DE CONEXIÓN Y CREACIÓN DE BASES DE DATOS
# -----------------------------------------------------------

def get_database(database: str) -> Database:
    """
    Función para obtener la base de datos de MongoDB
    :param database: el nombre de la base de datos
    :return: la base de datos
    """
    connection_string = f"mongodb://{MONGO_HOST}:{MONGO_PORT}"
    client = MongoClient(connection_string)
    return client[database]


def get_collection_reviews():
    """
    Función para obtener la colección de reviews de MongoDB
    :return: la colección
    """
    dbname = get_database(MONGO_DATABASE)
    collection_name = dbname[MONGO_COLLECTION_REVIEWS]
    return collection_name


def preparar_mongodb() -> None:
    """
    Prepara MongoDB para la carga de datos.
    Si ya existe la colección, la elimina para evitar duplicados.
    Además, crea un índice único sobre id_review como red de seguridad
    para que MongoDB no admita documentos duplicados aunque la lógica
    de Python fallase.
    """
    collection_name = get_collection_reviews()
    collection_name.drop()
    collection_name.create_index("id_review", unique=True)


def crear_base_datos_mysql() -> None:
    """
    Crea la base de datos de MySQL si no existe
    :return: None
    """
    conexion_mysql = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD
    )

    cursor = conexion_mysql.cursor()

    sql = f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}"
    cursor.execute(sql)

    cursor.close()
    conexion_mysql.close()


def get_connection_mysql():
    """
    Función para obtener la conexión a MySQL
    :return: la conexión
    """
    conexion = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    return conexion


# -----------------------------------------------------------
# CONSTANTES DE CARGA
# -----------------------------------------------------------

# Tamano de lote para los inserts por lote en MongoDB.
# Acumular documentos y enviarlos de golpe con insert_many
# reduce drasticamente los round-trips de red frente a
# hacer un insert_one por cada review.
TAMANO_LOTE_MONGO = 10000


# -----------------------------------------------------------
# FUNCIONES DE APOYO
# -----------------------------------------------------------

def convertir_review_time(review_time_texto):
    """
    Convierte el campo reviewTime del JSON a una fecha de Python.
    Si el texto es None, vacío o tiene un formato inesperado,
    devuelve None en lugar de romper la carga.
    :param review_time_texto: el texto original de la fecha
    :return: un objeto date o None
    """
    if review_time_texto is None or review_time_texto.strip() == "":
        return None

    try:
        return datetime.strptime(review_time_texto, "%m %d, %Y").date()
    except (ValueError, TypeError):
        return None


def obtener_id_usuario(cursor_mysql, reviewer_id, reviewer_name, cache_usuarios):
    """
    Devuelve el id_usuario correspondiente al reviewerID.
    Si el usuario no existe, lo inserta.
    Si el usuario ya existe pero tiene reviewerName vacío y el nuevo
    nombre no lo es, se actualiza. Si ya tiene un nombre no vacío,
    no se reemplaza (se conserva el primero no vacío registrado).

    Utiliza cache_usuarios (dict) para evitar SELECTs repetidos a MySQL.
    La clave es reviewerID y el valor es (id_usuario, reviewerName).
    """
    if reviewer_id in cache_usuarios:
        id_usuario, nombre_guardado = cache_usuarios[reviewer_id]
        if (nombre_guardado is None or nombre_guardado == "") and reviewer_name:
            cursor_mysql.execute(
                "UPDATE USUARIO SET reviewerName = %s WHERE id_usuario = %s",
                [reviewer_name, id_usuario]
            )
            cache_usuarios[reviewer_id] = (id_usuario, reviewer_name)
        return id_usuario

    cursor_mysql.execute(
        "SELECT id_usuario, reviewerName FROM USUARIO WHERE reviewerID = %s",
        [reviewer_id]
    )
    resultado = cursor_mysql.fetchone()

    if resultado is None:
        cursor_mysql.execute(
            "INSERT INTO USUARIO (reviewerID, reviewerName) VALUES (%s, %s)",
            [reviewer_id, reviewer_name]
        )
        id_usuario = cursor_mysql.lastrowid
        cache_usuarios[reviewer_id] = (id_usuario, reviewer_name)
        return id_usuario

    id_usuario = resultado[0]
    nombre_actual = resultado[1]

    if (nombre_actual is None or nombre_actual == "") and reviewer_name:
        cursor_mysql.execute(
            "UPDATE USUARIO SET reviewerName = %s WHERE id_usuario = %s",
            [reviewer_name, id_usuario]
        )
        cache_usuarios[reviewer_id] = (id_usuario, reviewer_name)
    else:
        cache_usuarios[reviewer_id] = (id_usuario, nombre_actual)

    return id_usuario


def obtener_id_articulo(cursor_mysql, asin, cache_articulos):
    """
    Devuelve el id_articulo correspondiente al ASIN.
    Si el artículo no existe, lo inserta.

    Utiliza cache_articulos (dict) para evitar SELECTs repetidos.
    La clave es asin y el valor es id_articulo.
    """
    if asin in cache_articulos:
        return cache_articulos[asin]

    cursor_mysql.execute(
        "SELECT id_articulo FROM ARTICULO WHERE asin = %s",
        [asin]
    )
    resultado = cursor_mysql.fetchone()

    if resultado is None:
        cursor_mysql.execute(
            "INSERT INTO ARTICULO (asin) VALUES (%s)",
            [asin]
        )
        id_articulo = cursor_mysql.lastrowid
        cache_articulos[asin] = id_articulo
        return id_articulo

    cache_articulos[asin] = resultado[0]
    return resultado[0]


def insertar_relacion_review_categoria(cursor_mysql, id_review, id_categoria):
    """
    Inserta la relación entre review y categoría si no existía.
    Una review pertenece a la categoría del fichero JSON del que se leyó.
    Si la misma review aparece en varios ficheros, tendrá varias categorías.

    Usa INSERT IGNORE para que la clave primaria compuesta rechace
    duplicados sin lanzar excepcion, evitando el SELECT previo.
    """
    cursor_mysql.execute(
        "INSERT IGNORE INTO REVIEW_CATEGORIA (id_review, id_categoria) "
        "VALUES (%s, %s)",
        [id_review, id_categoria]
    )


def volcar_buffer_mongo(collection, buffer_mongo, buffer_ids, cursor_mysql):
    """
    Envia a MongoDB un lote completo de documentos con insert_many.
    Si alguno falla, se eliminan de MySQL las filas correspondientes
    (tanto en REVIEW_CATEGORIA como en REVIEW) para mantener la
    sincronizacion entre ambas bases de datos.
    """
    if len(buffer_mongo) == 0:
        return

    try:
        collection.insert_many(buffer_mongo, ordered=False)
    except BulkWriteError as bwe:
        # Algunos documentos pudieron insertarse correctamente.
        # Solo se borran de MySQL los que fallaron.
        indices_fallidos = set()
        for error in bwe.details.get("writeErrors", []):
            indices_fallidos.add(error["index"])
        for idx in indices_fallidos:
            if idx < len(buffer_ids):
                id_review = buffer_ids[idx]
                cursor_mysql.execute(
                    "DELETE FROM REVIEW_CATEGORIA WHERE id_review = %s",
                    [id_review]
                )
                cursor_mysql.execute(
                    "DELETE FROM REVIEW WHERE id_review = %s",
                    [id_review]
                )
        if len(indices_fallidos) > 0:
            print("Aviso: " + str(len(indices_fallidos))
                  + " reviews descartadas (fallo parcial en MongoDB).")
    except Exception as error_mongo:
        # Fallo total: se borran todas las filas del lote de MySQL.
        for id_review in buffer_ids:
            cursor_mysql.execute(
                "DELETE FROM REVIEW_CATEGORIA WHERE id_review = %s",
                [id_review]
            )
            cursor_mysql.execute(
                "DELETE FROM REVIEW WHERE id_review = %s",
                [id_review]
            )
        print("Aviso: lote completo descartado (fallo en MongoDB): "
              + str(error_mongo))

    del buffer_mongo[:]
    del buffer_ids[:]


def insertar_o_recuperar_id_review(cursor_mysql, id_usuario, id_articulo,
                                    overall, unix_review_time, review_time):
    """
    Intenta insertar la review en REVIEW. Si la UNIQUE la rechaza
    (la misma tripleta id_usuario/id_articulo/unixReviewTime ya existia
    en otro dataset), recupera el id_review existente con un unico SELECT.

    Este patron evita hacer un SELECT previo a cada INSERT: INSERT IGNORE
    deja que MySQL use directamente el indice UNIQUE para detectar el
    duplicado, lo que es mucho mas barato que una query SELECT explicita.
    Con millones de reviews, ahorra millones de round-trips.

    Devuelve una tupla (id_review, es_nueva):
      - es_nueva=True  -> se acaba de insertar, debe volcarse a MongoDB.
      - es_nueva=False -> ya existia en otro dataset, solo hay que
                          enlazar la categoria en REVIEW_CATEGORIA.
    """
    cursor_mysql.execute(
        "INSERT IGNORE INTO REVIEW "
        "(id_usuario, id_articulo, overall, unixReviewTime, reviewTime) "
        "VALUES (%s, %s, %s, %s, %s)",
        [id_usuario, id_articulo, overall, unix_review_time, review_time]
    )

    if cursor_mysql.rowcount == 1:
        return cursor_mysql.lastrowid, True

    # rowcount == 0: la UNIQUE ha rechazado el INSERT porque ya existia.
    # Un unico SELECT para recuperar el id_review existente.
    cursor_mysql.execute(
        "SELECT id_review FROM REVIEW "
        "WHERE id_usuario = %s AND id_articulo = %s AND unixReviewTime = %s",
        [id_usuario, id_articulo, unix_review_time]
    )
    fila = cursor_mysql.fetchone()
    if fila is None:
        # No deberia ocurrir en una ejecucion normal. Se lanza excepcion
        # para que el bucle principal descarte la review con seguridad.
        raise RuntimeError(
            "INSERT IGNORE rechazado pero la fila no aparece al buscarla."
        )
    return fila[0], False


# -----------------------------------------------------------
# CREACIÓN DE TABLAS EN MYSQL
# -----------------------------------------------------------

def crear_tablas_mysql() -> None:
    """
    Crea las tablas del proyecto en MySQL.
    Si ya existían, las elimina antes para volver a cargar todo desde cero.
    """
    crear_base_datos_mysql()

    conexion = get_connection_mysql()
    cursor = conexion.cursor()

    cursor.execute("DROP TABLE IF EXISTS REVIEW_CATEGORIA")
    cursor.execute("DROP TABLE IF EXISTS REVIEW")
    cursor.execute("DROP TABLE IF EXISTS ARTICULO")
    cursor.execute("DROP TABLE IF EXISTS CATEGORIA")
    cursor.execute("DROP TABLE IF EXISTS USUARIO")

    sql_crear_usuario = """
    CREATE TABLE IF NOT EXISTS USUARIO (
        id_usuario INT NOT NULL AUTO_INCREMENT,
        reviewerID VARCHAR(30) NOT NULL,
        reviewerName VARCHAR(255),
        PRIMARY KEY (id_usuario),
        UNIQUE (reviewerID)
    );
    """

    sql_crear_categoria = """
    CREATE TABLE IF NOT EXISTS CATEGORIA (
        id_categoria INT NOT NULL AUTO_INCREMENT,
        nombre_categoria VARCHAR(100) NOT NULL,
        PRIMARY KEY (id_categoria),
        UNIQUE (nombre_categoria)
    );
    """

    sql_crear_articulo = """
    CREATE TABLE IF NOT EXISTS ARTICULO (
        id_articulo INT NOT NULL AUTO_INCREMENT,
        asin VARCHAR(20) NOT NULL,
        PRIMARY KEY (id_articulo),
        UNIQUE (asin)
    );
    """

    sql_crear_review ="""
    CREATE TABLE IF NOT EXISTS REVIEW (
        id_review INT NOT NULL AUTO_INCREMENT,
        id_usuario INT NOT NULL,
        id_articulo INT NOT NULL,
        overall TINYINT,          -- Siempre es un entero pequeño (1-5)
        unixReviewTime BIGINT NOT NULL,
        reviewTime DATE,
        PRIMARY KEY (id_review),
        UNIQUE (id_usuario, id_articulo, unixReviewTime),
        FOREIGN KEY (id_usuario) REFERENCES USUARIO(id_usuario),
        FOREIGN KEY (id_articulo) REFERENCES ARTICULO(id_articulo)
    );
    """

    cursor.execute(sql_crear_usuario)
    cursor.execute(sql_crear_categoria)
    cursor.execute(sql_crear_articulo)
    cursor.execute(sql_crear_review)

    sql_crear_review_categoria = """
    CREATE TABLE IF NOT EXISTS REVIEW_CATEGORIA (
        id_review INT NOT NULL,
        id_categoria INT NOT NULL,
        PRIMARY KEY (id_review, id_categoria),
        FOREIGN KEY (id_review) REFERENCES REVIEW(id_review),
        FOREIGN KEY (id_categoria) REFERENCES CATEGORIA(id_categoria)
    );
    """

    cursor.execute(sql_crear_review_categoria)

    # Nota: los indices secundarios NO se crean aqui.
    # Se crean despues de la carga de datos en crear_indices_secundarios()
    # para acelerar los INSERT masivos. Durante la carga solo se necesitan
    # la PK, las UNIQUE y los indices automaticos de las FOREIGN KEY, que
    # ya estan definidos en los CREATE TABLE anteriores.

    conexion.commit()
    cursor.close()
    conexion.close()


# -----------------------------------------------------------
# CREACION DE INDICES SECUNDARIOS (TRAS LA CARGA)
# -----------------------------------------------------------

def crear_indices_secundarios() -> None:
    """
    Crea los indices secundarios DESPUES de la carga masiva de datos.

    Mantener estos indices durante la carga obliga a MySQL a actualizarlos
    fila a fila en cada INSERT, lo que es costoso con millones de filas.
    Crearlos sobre una tabla ya poblada es mucho mas rapido: MySQL
    construye el indice de una sola vez, ordenadamente, sin fragmentacion.

    Ninguno de estos indices se necesita durante la carga (las queries de
    carga filtran por PK, UNIQUE o FK, no por estos campos), asi que
    posponerlos es seguro y reduce drasticamente el tiempo total.
    """
    conexion = get_connection_mysql()
    cursor = conexion.cursor()

    # Indice sobre reviewTime para la consulta de "reviews por año" (opcion 1
    # del menu de visualizaciones), que agrupa por YEAR(reviewTime).
    cursor.execute("""
    CREATE INDEX idx_review_reviewTime
    ON REVIEW(reviewTime);
    """)

    # Indice sobre reviewerName para la consulta de 4.3, que filtra por
    # reviewerName IS NOT NULL AND != '' y ordena por reviewerName.
    # Sin este indice MySQL hace full scan de USUARIO para ordenar.
    cursor.execute("""
    CREATE INDEX idx_usuario_reviewer_name
    ON USUARIO(reviewerName);
    """)

    # Indice sobre unixReviewTime para las consultas de evolucion temporal
    # (opcion 4 del menu), que agrupan y ordenan por este campo sobre toda
    # la tabla REVIEW. Sin este indice MySQL ordena en memoria.
    # Nota: REVIEW(id_articulo) y REVIEW(id_usuario) no se crean explicitamente
    # porque los genera automaticamente al declarar las claves foraneas.
    cursor.execute("""
    CREATE INDEX idx_review_unix_review_time
    ON REVIEW(unixReviewTime);
    """)

    # Indice sobre REVIEW_CATEGORIA(id_categoria, id_review) para las consultas
    # que filtran reviews por categoria. Ya hay un indice sobre la PK
    # (id_review, id_categoria), pero las consultas filtran por id_categoria,
    # asi que necesitamos el indice inverso.
    cursor.execute("""
    CREATE INDEX idx_review_categoria_categoria_review
    ON REVIEW_CATEGORIA(id_categoria, id_review);
    """)

    conexion.commit()
    cursor.close()
    conexion.close()


# -----------------------------------------------------------
# INSERCIÓN DE CATEGORÍAS
# -----------------------------------------------------------

def insertar_categorias_mysql() -> None:
    """
    Inserta en MySQL las categorías del proyecto
    """
    conexion = get_connection_mysql()
    cursor = conexion.cursor()

    sql = """
    INSERT INTO CATEGORIA (nombre_categoria)
    VALUES (%s)
    """

    for nombre_categoria, _ in DATASETS:
        cursor.execute(sql, [nombre_categoria])

    conexion.commit()
    cursor.close()
    conexion.close()


# La tabla CATEGORIA se rellena al principio porque sus valores no salen
# dentro de cada review del JSON, sino que vienen dados por el fichero
# que estamos leyendo (Video Games, Toys and Games, etc.).
# En cambio, las tablas USUARIO, ARTICULO y REVIEW se van rellenando
# mientras recorremos las reviews una a una, porque sus datos sí aparecen
# en cada línea del fichero.
# La relación entre cada review y su categoría de procedencia se registra
# en la tabla intermedia REVIEW_CATEGORIA.

# -----------------------------------------------------------
# CARGA DE DATOS
# -----------------------------------------------------------

def cargar_datasets() -> None:
    """
    Lee los ficheros JSON línea a línea y carga la información
    en MySQL y MongoDB siguiendo el esquema del proyecto.

    Optimizaciones aplicadas para reducir los round-trips a las BBDD:
    - Caches en memoria (dict) para usuarios y articulos, evitando
      SELECTs repetidos sobre datos que no cambian.
    - INSERT IGNORE + fallback SELECT en REVIEW: el SELECT previo de
      comprobacion de duplicados solo se ejecuta cuando el INSERT ha
      sido rechazado por el indice UNIQUE, es decir, en los casos en
      los que la review ya existia en otro dataset. Para las reviews
      nuevas (mayoria), basta un unico round-trip.
    - INSERT IGNORE en REVIEW_CATEGORIA para eliminar el SELECT
      previo de comprobacion.
    - Inserciones por lotes en MongoDB con insert_many en lugar de
      insert_one, reduciendo los round-trips de red.
    - Commits intermedios tras cada volcado a MongoDB, acotando el
      tamano del undo log y permitiendo recuperacion parcial si se
      interrumpe la carga.
    - Indices secundarios creados DESPUES de la carga masiva (ver
      crear_indices_secundarios), no durante el INSERT.
    """
    conexion_mysql = get_connection_mysql()
    cursor_mysql = conexion_mysql.cursor()

    collection_reviews = get_collection_reviews()

    # Caches en memoria. Se mantienen entre datasets porque los
    # usuarios y articulos pueden repetirse entre ficheros distintos.
    cache_usuarios = {}    # {reviewerID: (id_usuario, reviewerName)}
    cache_articulos = {}   # {asin: id_articulo}

    for nombre_categoria, ruta_fichero in DATASETS:
        t_dataset = time.time()

        sql = """
        SELECT id_categoria
        FROM CATEGORIA
        WHERE nombre_categoria = %s
        """
        cursor_mysql.execute(sql, [nombre_categoria])
        resultado = cursor_mysql.fetchone()
        id_categoria = resultado[0]

        print("Cargando dataset: " + nombre_categoria + "...")

        # Buffers para el insert por lotes en MongoDB y en REVIEW_CATEGORIA.
        buffer_mongo = []
        buffer_ids = []
        buffer_categoria = []

        with open(ruta_fichero, "r", encoding="utf-8") as file:
            for linea in file:
                if linea.strip() == "":
                    continue

                review = json.loads(linea)

                reviewer_id = review.get("reviewerID")
                reviewer_name = review.get("reviewerName")
                asin = review.get("asin")
                # overall se guarda como TINYINT porque siempre es un entero
                # pequeno (1-5). El JSON original lo almacena como float (5.0),
                # por lo que se convierte a int antes de la insercion.
                overall = review.get("overall")
                if overall is not None:
                    overall = int(overall)
                unix_review_time = review.get("unixReviewTime")

                # Validación: si falta algún campo imprescindible, se salta la línea.
                if not reviewer_id or not asin or unix_review_time is None:
                    continue

                review_time = convertir_review_time(review.get("reviewTime"))

                helpful = review.get("helpful")
                summary = review.get("summary")
                review_text = review.get("reviewText")

                id_usuario = obtener_id_usuario(
                    cursor_mysql,
                    reviewer_id,
                    reviewer_name,
                    cache_usuarios
                )

                id_articulo = obtener_id_articulo(
                    cursor_mysql, asin, cache_articulos
                )

                # INSERT IGNORE + fallback SELECT en una sola llamada:
                # - si la review es nueva, se inserta y se devuelve su id;
                # - si ya existia en otro dataset, se recupera el id existente.
                # Sustituye al patron anterior (SELECT previo + INSERT) y
                # ahorra un round-trip a MySQL por cada review.
                # El try/except descarta la review si ocurre un error de
                # MySQL distinto del duplicado (dato corrupto, overflow, etc.)
                # sin abortar toda la carga del fichero.
                try:
                    id_review, es_nueva = insertar_o_recuperar_id_review(
                        cursor_mysql, id_usuario, id_articulo, overall,
                        unix_review_time, review_time
                    )
                except Exception as error_mysql:
                    print("Aviso: review descartada (fallo en MySQL): "
                          + str(error_mysql))
                    continue

                # La categoria se acumula en buffer para volcarla por
                # lotes con executemany, reduciendo drasticamente los
                # round-trips a MySQL (de ~500k individuales a ~50 lotes).
                # Se enlaza SIEMPRE, tanto si la review es nueva como si
                # ya existia en otro dataset.
                buffer_categoria.append((id_review, id_categoria))

                # Solo las reviews recien insertadas se envian a MongoDB.
                # Las duplicadas entre datasets ya estan alli desde la
                # primera vez que se leyeron.
                if es_nueva:
                    buffer_mongo.append({
                        "id_review": id_review,
                        "helpful": helpful,
                        "summary": summary,
                        "reviewText": review_text
                    })
                    buffer_ids.append(id_review)

                if len(buffer_mongo) >= TAMANO_LOTE_MONGO:
                    # Volcado por lotes de REVIEW_CATEGORIA. Se hace ANTES
                    # de volcar a MongoDB para que, si el volcado fallara,
                    # volcar_buffer_mongo pueda borrar REVIEW_CATEGORIA
                    # manteniendo la sincronizacion entre bases de datos.
                    if buffer_categoria:
                        cursor_mysql.executemany(
                            "INSERT IGNORE INTO REVIEW_CATEGORIA "
                            "(id_review, id_categoria) VALUES (%s, %s)",
                            buffer_categoria
                        )
                        buffer_categoria.clear()
                    volcar_buffer_mongo(
                        collection_reviews, buffer_mongo,
                        buffer_ids, cursor_mysql
                    )
                    # Commit intermedio: persiste en MySQL el lote que
                    # acaba de sincronizarse con MongoDB. Reduce el
                    # tamano de la transaccion y acelera los INSERT
                    # posteriores (undo log mas pequeno).
                    conexion_mysql.commit()

        # Volcar el buffer de categorias pendiente.
        if buffer_categoria:
            cursor_mysql.executemany(
                "INSERT IGNORE INTO REVIEW_CATEGORIA "
                "(id_review, id_categoria) VALUES (%s, %s)",
                buffer_categoria
            )
            buffer_categoria.clear()
        # Volcar el ultimo lote parcial que quede en el buffer.
        volcar_buffer_mongo(
            collection_reviews, buffer_mongo, buffer_ids, cursor_mysql
        )

        conexion_mysql.commit()
        print("Dataset " + nombre_categoria + " completado en "
              + str(round(time.time() - t_dataset, 2)) + " segundos.")

    cursor_mysql.close()
    conexion_mysql.close()


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------

def main() -> None:
    """
    Función principal del programa
    """
    t_total = time.time()

    t = time.time()
    preparar_mongodb()
    print("Preparar MongoDB completado en "
          + str(round(time.time() - t, 2)) + " segundos.")

    t = time.time()
    crear_tablas_mysql()
    print("Crear tablas MySQL completado en "
          + str(round(time.time() - t, 2)) + " segundos.")

    t = time.time()
    insertar_categorias_mysql()
    print("Insertar categorias completado en "
          + str(round(time.time() - t, 2)) + " segundos.")

    t = time.time()
    cargar_datasets()
    print("Carga de datasets completada en "
          + str(round(time.time() - t, 2)) + " segundos.")

    t = time.time()
    crear_indices_secundarios()
    print("Creacion de indices secundarios completada en "
          + str(round(time.time() - t, 2)) + " segundos.")

    print("Carga total completada en "
          + str(round(time.time() - t_total, 2)) + " segundos.")


if __name__ == "__main__":
    main()
