# ------------------------------
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodríguez
# ------------------------------

import json
import time

from load_data import (
    get_connection_mysql,
    get_collection_reviews,
    convertir_review_time,
    obtener_id_usuario,
    obtener_id_articulo,
    insertar_relacion_review_categoria,
    volcar_buffer_mongo,
    insertar_o_recuperar_id_review,
    TAMANO_LOTE_MONGO
)

# -----------------------------------------------------------
# CONFIGURACIÓN DEL NUEVO DATASET
# Modifica estas constantes para cambiar el dataset a insertar
# sin necesidad de tocar ningún otro fichero.
# -----------------------------------------------------------
NOMBRE_CATEGORIA_NUEVA = "Office Products"
RUTA_NUEVO_DATASET = "Office_Products_5.json"


# -----------------------------------------------------------
# FUNCIONES DE APOYO
# -----------------------------------------------------------

def obtener_o_insertar_categoria(cursor_mysql, nombre_categoria):
    """
    Devuelve el id_categoria correspondiente al nombre dado.
    Si la categoría no existe en la tabla CATEGORIA, la inserta.
    Esto permite añadir datasets nuevos sin modificar load_data.py
    ni la lista de categorías originales.

    :param cursor_mysql: cursor activo de MySQL.
    :param nombre_categoria: nombre de la nueva categoría.
    :return: id_categoria (int).
    """
    cursor_mysql.execute(
        "SELECT id_categoria FROM CATEGORIA WHERE nombre_categoria = %s",
        [nombre_categoria]
    )
    resultado = cursor_mysql.fetchone()

    if resultado is not None:
        print("La categoria '" + nombre_categoria
              + "' ya existia (id=" + str(resultado[0]) + ").")
        return resultado[0]

    cursor_mysql.execute(
        "INSERT INTO CATEGORIA (nombre_categoria) VALUES (%s)",
        [nombre_categoria]
    )
    id_categoria = cursor_mysql.lastrowid
    print("Categoria '" + nombre_categoria
          + "' insertada con id=" + str(id_categoria) + ".")
    return id_categoria


# -----------------------------------------------------------
# INSERCIÓN DEL DATASET
# -----------------------------------------------------------

def insertar_dataset(nombre_categoria, ruta_fichero):
    """
    Inserta en MySQL y MongoDB las reviews de un nuevo fichero JSON,
    integrándolas con los datos ya existentes en la base de datos.

    Sigue el mismo modelo que cargar_datasets() en load_data.py:
    - Si la review no existe (según la tripleta id_usuario, id_articulo,
      unixReviewTime), se inserta en REVIEW y en MongoDB, y se registra
      su categoría en REVIEW_CATEGORIA.
    - Si la review ya existía (duplicado entre datasets), solo se añade
      la nueva relación en REVIEW_CATEGORIA para esta categoría, sin
      duplicar la fila en REVIEW ni en MongoDB.
    - Los usuarios y artículos ya existentes no se vuelven a insertar;
      se reutilizan sus identificadores internos.

    :param nombre_categoria: nombre del tipo de producto del nuevo fichero.
    :param ruta_fichero: ruta al fichero JSON con las reviews.
    """
    conexion_mysql = get_connection_mysql()
    cursor_mysql = conexion_mysql.cursor()
    collection_reviews = get_collection_reviews()

    id_categoria = obtener_o_insertar_categoria(cursor_mysql, nombre_categoria)
    conexion_mysql.commit()

    # Caches en memoria para evitar SELECTs repetidos.
    # Se inicializan vacíos: solo se precarga lo que se vaya encontrando
    # en este dataset, lo que es correcto porque los ids internos ya
    # existen en MySQL y se recuperan al primer acceso.
    cache_usuarios = {}   # {reviewerID: (id_usuario, reviewerName)}
    cache_articulos = {}  # {asin: id_articulo}

    # Buffers para el insert por lotes en MongoDB.
    buffer_mongo = []
    buffer_ids = []

    t_inicio = time.time()
    print("Cargando dataset: " + nombre_categoria + "...")

    with open(ruta_fichero, "r", encoding="utf-8") as file:
        for linea in file:
            if linea.strip() == "":
                continue

            review = json.loads(linea)

            reviewer_id = review.get("reviewerID")
            reviewer_name = review.get("reviewerName")
            asin = review.get("asin")
            # overall se convierte a int porque se almacena como TINYINT
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
                cursor_mysql, reviewer_id, reviewer_name, cache_usuarios
            )
            id_articulo = obtener_id_articulo(
                cursor_mysql, asin, cache_articulos
            )

            # INSERT IGNORE + fallback SELECT: misma logica que load_data.py.
            # Evita el SELECT previo en cada review: MySQL usa directamente
            # el indice UNIQUE para detectar duplicados entre datasets.
            try:
                id_review, es_nueva = insertar_o_recuperar_id_review(
                    cursor_mysql, id_usuario, id_articulo, overall,
                    unix_review_time, review_time
                )
            except Exception as error_mysql:
                print("Aviso: review descartada (fallo en MySQL): "
                      + str(error_mysql))
                continue

            # La categoria se enlaza SIEMPRE. Si la review ya existia en
            # otro dataset, solo se registra que tambien pertenece a esta
            # nueva categoria. Se hace ANTES del volcado a MongoDB para
            # que, si el volcado falla, volcar_buffer_mongo pueda borrar
            # REVIEW y REVIEW_CATEGORIA manteniendo la sincronizacion.
            insertar_relacion_review_categoria(
                cursor_mysql, id_review, id_categoria
            )

            # Solo las reviews recien insertadas se envian a MongoDB.
            if es_nueva:
                buffer_mongo.append({
                    "id_review": id_review,
                    "helpful": helpful,
                    "summary": summary,
                    "reviewText": review_text
                })
                buffer_ids.append(id_review)

                if len(buffer_mongo) >= TAMANO_LOTE_MONGO:
                    volcar_buffer_mongo(
                        collection_reviews, buffer_mongo,
                        buffer_ids, cursor_mysql
                    )
                    # Commit intermedio: persiste en MySQL el lote recien
                    # sincronizado con MongoDB.
                    conexion_mysql.commit()

    # Volcar el último lote parcial que haya quedado en el buffer.
    volcar_buffer_mongo(
        collection_reviews, buffer_mongo, buffer_ids, cursor_mysql
    )

    conexion_mysql.commit()

    print("Dataset '" + nombre_categoria + "' insertado en "
          + str(round(time.time() - t_inicio, 2)) + " segundos.")

    cursor_mysql.close()
    conexion_mysql.close()


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------

def main():
    """
    Función principal: inserta el dataset indicado por las constantes
    NOMBRE_CATEGORIA_NUEVA y RUTA_NUEVO_DATASET en la base de datos
    existente, sin borrar ni recrear ninguna tabla.
    """
    t_total = time.time()

    insertar_dataset(NOMBRE_CATEGORIA_NUEVA, RUTA_NUEVO_DATASET)

    print("Carga total completada en "
          + str(round(time.time() - t_total, 2)) + " segundos.")


if __name__ == "__main__":
    main()
