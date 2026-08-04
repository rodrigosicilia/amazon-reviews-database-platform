# ============================================================
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodríguez
# ============================================================

"""
neo4JProyecto.py

Tercera parte del proyecto de Bases de Datos.
Menú por terminal para cargar en Neo4J los grafos pedidos en los
apartados 4.1, 4.2, 4.3 y 4.4 del enunciado.

Esquema MySQL esperado:
- USUARIO(id_usuario, reviewerID, reviewerName)
- CATEGORIA(id_categoria, nombre_categoria)
- ARTICULO(id_articulo, asin)
- REVIEW(id_review, id_usuario, id_articulo, overall, unixReviewTime, reviewTime)
- REVIEW_CATEGORIA(id_review, id_categoria)

Se sigue el estilo mostrado en los manuales:
- MySQL con pymysql.connect(...)
- Neo4J con GraphDatabase.driver(...)
- Sesiones de Neo4J con with driver.session() as session
- Consultas Cypher con session.run(...)
"""

import csv
import math

import pymysql
from neo4j import GraphDatabase

import configuracion as cfg


# ============================================================
# CONSTANTES DEL ENUNCIADO
# ============================================================

NUM_USUARIOS_SIMILITUD = 30
NUM_USUARIOS_ORDENADOS = 400
NUM_ARTICULOS_POPULARES = 5
MAX_REVIEWS_ARTICULO_POPULAR = 40
RUTA_FICHERO_SIMILITUDES = "similitudes_pearson.csv"


# ============================================================
# FUNCIONES AUXILIARES DE CONFIGURACION
# ============================================================


def get_password_neo4j():
    """
    Obtiene la contraseña de Neo4J desde configuracion.py.
    """
    return cfg.NEO4J_PASSWORD



def construir_uri_neo4j():
    """
    Construye la URI de Neo4J a partir de configuracion.py.
    """
    return "neo4j://" + str(cfg.NEO4J_HOST) + ":" + str(cfg.NEO4J_PORT)


# ============================================================
# DRIVER GLOBAL DE NEO4J
# Se crea fuera de las funciones siguiendo el estilo del manual.
# ============================================================

URI_NEO4J = construir_uri_neo4j()
PASSWORD_NEO4J = get_password_neo4j()
driver = GraphDatabase.driver(URI_NEO4J, auth=(cfg.NEO4J_USER, PASSWORD_NEO4J))


# ============================================================
# CONEXION MYSQL
# ============================================================


def get_conexion_mysql():
    """
    Obtiene la conexión a MySQL.
    """
    conexion = pymysql.connect(
        host=cfg.MYSQL_HOST,
        user=cfg.MYSQL_USER,
        password=cfg.MYSQL_PASSWORD,
        database=cfg.MYSQL_DATABASE
    )
    return conexion


# ============================================================
# FUNCIONES AUXILIARES GENERALES
# ============================================================


def construir_marcadores_sql(cantidad):
    """
    Construye la lista de marcadores %s para cláusulas IN.
    """
    texto = ""
    i = 0

    while i < cantidad:
        texto = texto + "%s"
        if i < cantidad - 1:
            texto = texto + ", "
        i = i + 1

    return texto



def nombre_visible_usuario(reviewer_id, reviewer_name):
    """
    Devuelve el nombre que conviene mostrar en el nodo de usuario.
    """
    if reviewer_name is None:
        return reviewer_id

    if reviewer_name == "":
        return reviewer_id

    return reviewer_name



def crear_restricciones_neo4j():
    """
    Crea restricciones de unicidad en Neo4J si no existen.
    Estas restricciones crean indices automaticos que aceleran
    las operaciones MERGE y persisten aunque se borren los nodos.
    """
    with driver.session() as session:
        try:
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS "
                "FOR (u:Usuario) REQUIRE u.id_usuario IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS "
                "FOR (a:Articulo) REQUIRE a.id_articulo IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS "
                "FOR (t:TipoArticulo) REQUIRE t.id_categoria IS UNIQUE"
            )
        except Exception:
            pass



def limpiar_neo4j():
    """
    Elimina todos los nodos y relaciones de Neo4J.
    """
    with driver.session() as session:
        consulta = "MATCH (n) DETACH DELETE n"
        session.run(consulta)



def pedir_entero_positivo(mensaje):
    """
    Pide un entero positivo.
    """
    correcto = False
    numero = 0

    while correcto is False:
        texto = input(mensaje).strip()

        if texto.isdigit():
            numero = int(texto)
            if numero > 0:
                correcto = True
            else:
                print("Debe introducirse un entero positivo.")
        else:
            print("Debe introducirse un entero positivo.")

    return numero



def obtener_categorias(conexion):
    """
    Devuelve la lista de categorias disponibles en la base de datos.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT nombre_categoria
    FROM CATEGORIA
    ORDER BY nombre_categoria;
    """
    cursor.execute(sql)
    resultado = cursor.fetchall()
    cursor.close()

    categorias = []
    i = 0
    while i < len(resultado):
        categorias.append(resultado[i][0])
        i = i + 1

    return categorias


def pedir_nombre_categoria(conexion):
    """
    Pide una categoría existente en la tabla CATEGORIA.
    Muestra las categorias disponibles y valida contra la lista obtenida.
    """
    categorias = obtener_categorias(conexion)

    categoria = ""
    correcta = False

    while correcta is False:
        print()
        print("Categorias disponibles:")
        i = 0
        while i < len(categorias):
            print("  - " + categorias[i])
            i = i + 1
        print()

        categoria = input("Introduce el nombre exacto de la categoría: ").strip()

        if categoria == "":
            print("Debes introducir una categoria.")
        elif categoria in categorias:
            correcta = True
        else:
            print("Esa categoría no existe.")

    return categoria



def pedir_opcion_menu():
    """
    Pide una opción válida del menú principal.
    """
    opcion = ""
    correcta = False

    while correcta is False:
        print()
        print("================ MENÚ NEO4J ================")
        print("1. Apartado 4.1 - Similitudes entre usuarios")
        print("2. Apartado 4.2 - Usuarios y artículos aleatorios")
        print("3. Apartado 4.3 - Usuarios y tipos de artículo")
        print("4. Apartado 4.4 - Artículos populares y artículos en común")
        print("5. Salir")
        print("============================================")

        opcion = input("Introduzca una opción: ").strip()

        if opcion == "1" or opcion == "2" or opcion == "3" or opcion == "4" or opcion == "5":
            correcta = True
        else:
            print("Opción no válida. Inténtelo de nuevo.")

    return opcion


# ============================================================
# CONSULTAS MYSQL - APARTADO 4.1
# ============================================================


def consulta_top_usuarios(conexion, limite):
    """
    Recupera los usuarios con más reviews.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT u.id_usuario,
           u.reviewerID,
           u.reviewerName,
           COUNT(r.id_review) AS numero_reviews
    FROM USUARIO u
    INNER JOIN REVIEW r ON u.id_usuario = r.id_usuario
    GROUP BY u.id_usuario, u.reviewerID, u.reviewerName
    ORDER BY numero_reviews DESC, u.id_usuario ASC
    LIMIT %s;
    """
    cursor.execute(sql, [limite])
    datos = cursor.fetchall()
    cursor.close()
    return datos



def consulta_valoraciones_por_articulo_usuario(conexion, ids_usuarios):
    """
    Recupera una valoración por usuario y artículo.

    Si un usuario tuviese más de una review sobre el mismo artículo,
    se toma la media para que cada artículo aparezca una sola vez.
    """
    datos = []

    if len(ids_usuarios) == 0:
        return datos

    cursor = conexion.cursor()
    marcadores = construir_marcadores_sql(len(ids_usuarios))
    sql = """
    SELECT r.id_usuario,
           r.id_articulo,
           AVG(r.overall) AS valoracion_media
    FROM REVIEW r
    WHERE r.id_usuario IN (""" + marcadores + """)
    GROUP BY r.id_usuario, r.id_articulo
    ORDER BY r.id_usuario ASC, r.id_articulo ASC;
    """
    cursor.execute(sql, ids_usuarios)
    datos = cursor.fetchall()
    cursor.close()
    return datos


# ============================================================
# CONSULTAS MYSQL - APARTADO 4.2
# ============================================================


def consulta_articulos_aleatorios_por_categoria(conexion, categoria, cantidad):
    """
    Selecciona artículos aleatorios de una categoría.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT DISTINCT a.id_articulo,
           a.asin
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    INNER JOIN ARTICULO a ON r.id_articulo = a.id_articulo
    WHERE c.nombre_categoria = %s
    ORDER BY RAND()
    LIMIT %s;
    """
    cursor.execute(sql, [categoria, cantidad])
    datos = cursor.fetchall()
    cursor.close()
    return datos

def consulta_reviews_de_articulos(conexion, ids_articulos):
    """
    Recupera todas las reviews de un conjunto de artículos.
    """
    datos = []

    if len(ids_articulos) == 0:
        return datos

    cursor = conexion.cursor()
    marcadores = construir_marcadores_sql(len(ids_articulos))
    sql = """
    SELECT r.id_review,
           u.id_usuario,
           u.reviewerID,
           u.reviewerName,
           a.id_articulo,
           a.asin,
           r.overall,
           r.unixReviewTime,
           r.reviewTime
    FROM REVIEW r
    INNER JOIN USUARIO u ON r.id_usuario = u.id_usuario
    INNER JOIN ARTICULO a ON r.id_articulo = a.id_articulo
    WHERE a.id_articulo IN (""" + marcadores + """)
    ORDER BY a.id_articulo ASC, u.id_usuario ASC, r.unixReviewTime ASC;
    """
    cursor.execute(sql, ids_articulos)
    datos = cursor.fetchall()
    cursor.close()
    return datos



def consulta_reviews_de_articulos_por_categoria(conexion, ids_articulos, categoria):
    """
    Recupera las reviews de un conjunto de artículos filtrando por categoría.

    A diferencia de consulta_reviews_de_articulos, solo devuelve las reviews
    cuya procedencia (REVIEW_CATEGORIA) pertenece a la categoría indicada.
    Esto evita que, cuando un artículo aparece en varios datasets, se carguen
    en Neo4J reviews procedentes de otras categorías distintas a la elegida.
    """
    datos = []

    if len(ids_articulos) == 0:
        return datos

    cursor = conexion.cursor()
    marcadores = construir_marcadores_sql(len(ids_articulos))
    sql = """
    SELECT r.id_review,
           u.id_usuario,
           u.reviewerID,
           u.reviewerName,
           a.id_articulo,
           a.asin,
           r.overall,
           r.unixReviewTime,
           r.reviewTime
    FROM REVIEW r
    INNER JOIN USUARIO u ON r.id_usuario = u.id_usuario
    INNER JOIN ARTICULO a ON r.id_articulo = a.id_articulo
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    WHERE a.id_articulo IN (""" + marcadores + """)
      AND c.nombre_categoria = %s
    ORDER BY a.id_articulo ASC, u.id_usuario ASC, r.unixReviewTime ASC;
    """
    parametros = list(ids_articulos) + [categoria]
    cursor.execute(sql, parametros)
    datos = cursor.fetchall()
    cursor.close()
    return datos


def consulta_primeros_usuarios_ordenados_por_nombre(conexion, limite):
    """
    Recupera los primeros usuarios ordenados por nombre.

    Solo se incluyen usuarios con reviewerName no nulo y no vacio,
    ya que ordenar por nombre cuando no hay nombre carece de sentido.
    Dentro de los que si tienen nombre se ordena alfabeticamente,
    y reviewerID se usa como desempate.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT u.id_usuario,
           u.reviewerID,
           u.reviewerName
    FROM USUARIO u
    WHERE u.reviewerName IS NOT NULL
      AND u.reviewerName != ''
    ORDER BY u.reviewerName ASC, u.reviewerID ASC
    LIMIT %s;
    """
    cursor.execute(sql, [limite])
    datos = cursor.fetchall()
    cursor.close()
    return datos



def consulta_articulos_distintos_por_tipo(conexion, ids_usuarios):
    """
    Recupera cuántos artículos distintos ha puntuado cada usuario por categoría.

    En 4.3 se pide el número de artículos consumidos de ese tipo,
    por eso se cuenta DISTINCT id_articulo y no el número de reviews.
    """
    datos = []

    if len(ids_usuarios) == 0:
        return datos

    cursor = conexion.cursor()
    marcadores = construir_marcadores_sql(len(ids_usuarios))
    sql = """
    SELECT u.id_usuario,
           u.reviewerID,
           u.reviewerName,
           c.id_categoria,
           c.nombre_categoria,
           COUNT(DISTINCT r.id_articulo) AS numero_articulos
    FROM USUARIO u
    INNER JOIN REVIEW r ON u.id_usuario = r.id_usuario
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    WHERE u.id_usuario IN (""" + marcadores + """)
    GROUP BY u.id_usuario, u.reviewerID, u.reviewerName,
             c.id_categoria, c.nombre_categoria
    ORDER BY u.id_usuario ASC, c.nombre_categoria ASC;
    """
    cursor.execute(sql, ids_usuarios)
    datos = cursor.fetchall()
    cursor.close()
    return datos

def consulta_total_articulos_distintos(conexion, ids_usuarios):
    """
    Recupera el numero total de articulos distintos que ha puntuado cada usuario.
    Esto se usa en 4.3 para evitar falsos positivos con articulos multicategoria:
    un usuario que solo ha puntuado un unico articulo no debe considerarse
    multicategoria aunque ese articulo pertenezca a varias categorias.
    """
    datos = []

    if len(ids_usuarios) == 0:
        return datos

    cursor = conexion.cursor()
    marcadores = construir_marcadores_sql(len(ids_usuarios))
    sql = """
    SELECT r.id_usuario,
           COUNT(DISTINCT r.id_articulo) AS total_articulos
    FROM REVIEW r
    WHERE r.id_usuario IN (""" + marcadores + """)
    GROUP BY r.id_usuario;
    """
    cursor.execute(sql, ids_usuarios)
    datos = cursor.fetchall()
    cursor.close()
    return datos



def consulta_articulos_populares(conexion):
    """
    Recupera los 5 artículos más populares con menos de 40 reviews.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT a.id_articulo,
           a.asin,
           COUNT(r.id_review) AS numero_reviews
    FROM ARTICULO a
    INNER JOIN REVIEW r ON a.id_articulo = r.id_articulo
    GROUP BY a.id_articulo, a.asin
    HAVING COUNT(r.id_review) < %s
    ORDER BY numero_reviews DESC, a.asin ASC
    LIMIT %s;
    """
    cursor.execute(sql, [MAX_REVIEWS_ARTICULO_POPULAR, NUM_ARTICULOS_POPULARES])
    datos = cursor.fetchall()
    cursor.close()
    return datos

def consulta_articulos_en_comun_usuarios(conexion, ids_articulos):
    """
    Calcula cuántos artículos en común han puntuado los usuarios que aparecen
    en el conjunto de artículos seleccionado del apartado 4.4.
    """
    resultado = []

    if len(ids_articulos) == 0:
        return resultado

    cursor = conexion.cursor()
    marcadores = construir_marcadores_sql(len(ids_articulos))
    sql = """
    SELECT r1.id_usuario AS id_usuario_1,
           r2.id_usuario AS id_usuario_2,
           COUNT(DISTINCT r1.id_articulo) AS articulos_comunes
    FROM REVIEW r1
    INNER JOIN REVIEW r2
        ON r1.id_articulo = r2.id_articulo
       AND r1.id_usuario < r2.id_usuario
    WHERE r1.id_articulo IN (""" + marcadores + """)
      AND r2.id_articulo IN (""" + marcadores + """)
    GROUP BY r1.id_usuario, r2.id_usuario
    HAVING COUNT(DISTINCT r1.id_articulo) > 0
    ORDER BY articulos_comunes DESC, id_usuario_1 ASC, id_usuario_2 ASC;
    """

    parametros = []
    i = 0
    while i < len(ids_articulos):
        parametros.append(ids_articulos[i])
        i = i + 1
    i = 0
    while i < len(ids_articulos):
        parametros.append(ids_articulos[i])
        i = i + 1

    cursor.execute(sql, parametros)
    resultado = cursor.fetchall()
    cursor.close()
    return resultado


# ============================================================
# FUNCIONES AUXILIARES DE CALCULO
# ============================================================


def media_lista(lista_valores):
    """
    Calcula la media de una lista numérica.
    """
    if len(lista_valores) == 0:
        return 0.0

    suma = 0.0
    i = 0
    while i < len(lista_valores):
        suma = suma + float(lista_valores[i])
        i = i + 1

    return suma / len(lista_valores)



def construir_estructura_ratings(reviews_usuarios):
    """
    Construye un diccionario con esta estructura:
    ratings_por_usuario[id_usuario] = {id_articulo: overall, ...}

    Se guarda así porque para Pearson hace falta acceder rápido a las notas de
    cada usuario por artículo y también a los artículos que comparten dos usuarios.
    """
    ratings_por_usuario = {}

    i = 0
    while i < len(reviews_usuarios):
        id_usuario = reviews_usuarios[i][0]
        id_articulo = reviews_usuarios[i][1]
        overall = float(reviews_usuarios[i][2])

        if id_usuario not in ratings_por_usuario:
            ratings_por_usuario[id_usuario] = {}

        ratings_por_usuario[id_usuario][id_articulo] = overall
        i = i + 1

    return ratings_por_usuario



def calcular_pearson_para_dos_usuarios(ratings_u, ratings_v):
    """
    Calcula la correlación de Pearson entre dos usuarios.

    ratings_u y ratings_v son diccionarios del tipo:
    {id_articulo: nota}

    Devuelve una tupla con:
    - similitud Pearson
    - número de artículos comunes

    Si no hay artículos comunes o el denominador queda a 0, se devuelve None.

    La fórmula del enunciado usa Iuv para las sumas, pero ru y rv son las medias
    de las valoraciones realizadas por cada usuario. Por eso la media se calcula
    con todas sus notas y no solo con las notas de los artículos comunes.
    """
    articulos_comunes = []

    for id_articulo in ratings_u:
        if id_articulo in ratings_v:
            articulos_comunes.append(id_articulo)

    if len(articulos_comunes) == 0:
        return None

    notas_totales_u = []
    for id_articulo in ratings_u:
        notas_totales_u.append(ratings_u[id_articulo])

    notas_totales_v = []
    for id_articulo in ratings_v:
        notas_totales_v.append(ratings_v[id_articulo])

    media_u = media_lista(notas_totales_u)
    media_v = media_lista(notas_totales_v)

    numerador = 0.0
    suma_u = 0.0
    suma_v = 0.0

    i = 0
    while i < len(articulos_comunes):
        id_articulo = articulos_comunes[i]
        diff_u = float(ratings_u[id_articulo]) - media_u
        diff_v = float(ratings_v[id_articulo]) - media_v
        numerador = numerador + (diff_u * diff_v)
        suma_u = suma_u + (diff_u * diff_u)
        suma_v = suma_v + (diff_v * diff_v)
        i = i + 1

    denominador = math.sqrt(suma_u) * math.sqrt(suma_v)

    if denominador == 0:
        return None

    pearson = numerador / denominador
    return (pearson, len(articulos_comunes))



def calcular_todas_las_similitudes(top_usuarios, ratings_por_usuario):
    """
    Calcula Pearson para todos los pares de usuarios del conjunto dado.
    """
    similitudes = []
    i = 0

    while i < len(top_usuarios):
        id_u = top_usuarios[i][0]
        j = i + 1

        while j < len(top_usuarios):
            id_v = top_usuarios[j][0]

            if id_u in ratings_por_usuario and id_v in ratings_por_usuario:
                resultado = calcular_pearson_para_dos_usuarios(
                    ratings_por_usuario[id_u],
                    ratings_por_usuario[id_v]
                )

                if resultado is not None:
                    pearson = resultado[0]
                    articulos_comunes = resultado[1]

                    similitudes.append({
                        "id_usuario_1": id_u,
                        "id_usuario_2": id_v,
                        "pearson": pearson,
                        "articulos_comunes": articulos_comunes
                    })

            j = j + 1
        i = i + 1

    return similitudes



def guardar_similitudes_en_csv(similitudes, top_usuarios, ruta_fichero):
    """
    Guarda las similitudes en un fichero auxiliar CSV.
    """
    mapa_usuarios = {}
    i = 0
    while i < len(top_usuarios):
        id_usuario = top_usuarios[i][0]
        reviewer_id = top_usuarios[i][1]
        reviewer_name = top_usuarios[i][2]
        mapa_usuarios[id_usuario] = {
            "reviewerID": reviewer_id,
            "reviewerName": reviewer_name
        }
        i = i + 1

    with open(ruta_fichero, "w", newline="", encoding="utf-8") as fichero:
        writer = csv.writer(fichero)
        writer.writerow([
            "id_usuario_1",
            "reviewerID_1",
            "reviewerName_1",
            "id_usuario_2",
            "reviewerID_2",
            "reviewerName_2",
            "pearson",
            "articulos_comunes"
        ])

        i = 0
        while i < len(similitudes):
            id_u = similitudes[i]["id_usuario_1"]
            id_v = similitudes[i]["id_usuario_2"]

            writer.writerow([
                id_u,
                mapa_usuarios[id_u]["reviewerID"],
                mapa_usuarios[id_u]["reviewerName"],
                id_v,
                mapa_usuarios[id_v]["reviewerID"],
                mapa_usuarios[id_v]["reviewerName"],
                similitudes[i]["pearson"],
                similitudes[i]["articulos_comunes"]
            ])
            i = i + 1


# ============================================================
# FUNCIONES AUXILIARES NEO4J
# ============================================================


def cargar_grafo_similitudes_en_neo4j(top_usuarios, similitudes):
    """
    Carga en Neo4J el grafo del apartado 4.1.
    """
    usuarios_neo4j = []
    i = 0
    while i < len(top_usuarios):
        usuarios_neo4j.append({
            "id_usuario": top_usuarios[i][0],
            "reviewerID": top_usuarios[i][1],
            "reviewerName": top_usuarios[i][2],
            "nombre_visible": nombre_visible_usuario(top_usuarios[i][1], top_usuarios[i][2]),
            "numero_reviews": int(top_usuarios[i][3])
        })
        i = i + 1

    with driver.session() as session:
        consulta_usuarios = """
        UNWIND $usuarios AS fila
        MERGE (u:Usuario {id_usuario: fila.id_usuario})
        SET u.reviewerID = fila.reviewerID,
            u.reviewerName = fila.reviewerName,
            u.nombre_visible = fila.nombre_visible,
            u.numero_reviews = fila.numero_reviews
        """
        session.run(consulta_usuarios, usuarios=usuarios_neo4j)

        consulta_relaciones = """
        UNWIND $similitudes AS fila
        MATCH (u1:Usuario {id_usuario: fila.id_usuario_1})
        MATCH (u2:Usuario {id_usuario: fila.id_usuario_2})
        MERGE (u1)-[r:SIMILARIDAD]-(u2)
        SET r.pearson = fila.pearson,
            r.articulos_comunes = fila.articulos_comunes
        """
        session.run(consulta_relaciones, similitudes=similitudes)



def cargar_grafo_articulos_usuarios_en_neo4j(reviews_articulos):
    """
    Carga en Neo4J el grafo del apartado 4.2.
    Solo se cargan articulos y usuarios con sus relaciones PUNTUO,
    tal como pide el enunciado.
    """
    with driver.session() as session:
        consulta_reviews = """
        UNWIND $filas AS fila
        MERGE (u:Usuario {id_usuario: fila.id_usuario})
        SET u.reviewerID = fila.reviewerID,
            u.reviewerName = fila.reviewerName,
            u.nombre_visible = fila.nombre_visible
        MERGE (a:Articulo {id_articulo: fila.id_articulo})
        SET a.asin = fila.asin
        MERGE (u)-[r:PUNTUO {id_review: fila.id_review}]->(a)
        SET r.overall = fila.overall,
            r.unixReviewTime = fila.unixReviewTime,
            r.reviewTime = fila.reviewTime
        """
        session.run(consulta_reviews, filas=reviews_articulos)

def cargar_grafo_usuarios_tipos_en_neo4j(filas_filtradas):
    """
    Carga en Neo4J el grafo del apartado 4.3.
    """
    with driver.session() as session:
        consulta = """
        UNWIND $filas AS fila
        MERGE (u:Usuario {id_usuario: fila.id_usuario})
        SET u.reviewerID = fila.reviewerID,
            u.reviewerName = fila.reviewerName,
            u.nombre_visible = fila.nombre_visible
        MERGE (t:TipoArticulo {id_categoria: fila.id_categoria})
        SET t.nombre_categoria = fila.nombre_categoria
        MERGE (u)-[r:CONSUMIO_TIPO]->(t)
        SET r.numero_articulos = fila.numero_articulos
        """
        session.run(consulta, filas=filas_filtradas)



def cargar_grafo_articulos_populares_en_neo4j(reviews_articulos, enlaces_comunes):
    """
    Carga en Neo4J el grafo del apartado 4.4.
    Solo se cargan articulos, usuarios, relaciones PUNTUO y
    enlaces ARTICULOS_EN_COMUN, tal como pide el enunciado.
    """
    with driver.session() as session:
        consulta_reviews = """
        UNWIND $filas AS fila
        MERGE (u:Usuario {id_usuario: fila.id_usuario})
        SET u.reviewerID = fila.reviewerID,
            u.reviewerName = fila.reviewerName,
            u.nombre_visible = fila.nombre_visible
        MERGE (a:Articulo {id_articulo: fila.id_articulo})
        SET a.asin = fila.asin
        MERGE (u)-[r:PUNTUO {id_review: fila.id_review}]->(a)
        SET r.overall = fila.overall,
            r.unixReviewTime = fila.unixReviewTime,
            r.reviewTime = fila.reviewTime
        """
        session.run(consulta_reviews, filas=reviews_articulos)

        consulta_enlaces = """
        UNWIND $enlaces AS fila
        MATCH (u1:Usuario {id_usuario: fila.id_usuario_1})
        MATCH (u2:Usuario {id_usuario: fila.id_usuario_2})
        MERGE (u1)-[r:ARTICULOS_EN_COMUN]-(u2)
        SET r.articulos_comunes = fila.articulos_comunes
        """
        session.run(consulta_enlaces, enlaces=enlaces_comunes)

def consulta_usuario_con_mas_vecinos_neo4j():
    """
    Consulta en Neo4J el usuario con más vecinos del apartado 4.1.
    """
    with driver.session() as session:
        consulta = """
        MATCH (u:Usuario)
        OPTIONAL MATCH (u)-[:SIMILARIDAD]-(v:Usuario)
        WITH u, COUNT(DISTINCT v) AS vecinos
        RETURN u.id_usuario AS id_usuario,
               u.reviewerID AS reviewerID,
               u.reviewerName AS reviewerName,
               vecinos
        ORDER BY vecinos DESC, id_usuario ASC
        LIMIT 1
        """
        resultado = session.run(consulta)
        return resultado.data()


# ============================================================
# PREPARACION DE DATOS PARA NEO4J
# ============================================================


def preparar_filas_reviews_para_neo4j(reviews_articulos):
    """
    Convierte las tuplas SQL en diccionarios fáciles de insertar con UNWIND.
    """
    filas = []
    i = 0

    while i < len(reviews_articulos):
        review_time = reviews_articulos[i][8]

        if review_time is not None:
            review_time = str(review_time)

        filas.append({
            "id_review": reviews_articulos[i][0],
            "id_usuario": reviews_articulos[i][1],
            "reviewerID": reviews_articulos[i][2],
            "reviewerName": reviews_articulos[i][3],
            "nombre_visible": nombre_visible_usuario(reviews_articulos[i][2], reviews_articulos[i][3]),
            "id_articulo": reviews_articulos[i][4],
            "asin": reviews_articulos[i][5],
            "overall": int(reviews_articulos[i][6]),
            "unixReviewTime": int(reviews_articulos[i][7]),
            "reviewTime": review_time
        })
        i = i + 1

    return filas


def filtrar_usuarios_multicategoria(filas_usuario_categoria, total_articulos_por_usuario):
    """
    Deja solo a los usuarios que han puntuado articulos de mas de un tipo.

    Para evitar falsos positivos con articulos multicategoria, se exige que
    el usuario haya puntuado al menos 2 articulos distintos en total Y que
    esos articulos pertenezcan a al menos 2 categorias distintas.
    De esta forma, un usuario que solo ha puntuado un unico articulo que
    pertenece a varias categorias no se considera multicategoria.
    """
    categorias_por_usuario = {}
    i = 0

    while i < len(filas_usuario_categoria):
        id_usuario = filas_usuario_categoria[i][0]
        id_categoria = filas_usuario_categoria[i][3]

        if id_usuario not in categorias_por_usuario:
            categorias_por_usuario[id_usuario] = []

        if id_categoria not in categorias_por_usuario[id_usuario]:
            categorias_por_usuario[id_usuario].append(id_categoria)

        i = i + 1

    filas_filtradas = []
    i = 0
    while i < len(filas_usuario_categoria):
        id_usuario = filas_usuario_categoria[i][0]
        total_articulos = total_articulos_por_usuario.get(id_usuario, 0)

        if len(categorias_por_usuario[id_usuario]) > 1 and total_articulos > 1:
            filas_filtradas.append({
                "id_usuario": filas_usuario_categoria[i][0],
                "reviewerID": filas_usuario_categoria[i][1],
                "reviewerName": filas_usuario_categoria[i][2],
                "nombre_visible": nombre_visible_usuario(filas_usuario_categoria[i][1], filas_usuario_categoria[i][2]),
                "id_categoria": filas_usuario_categoria[i][3],
                "nombre_categoria": filas_usuario_categoria[i][4],
                "numero_articulos": int(filas_usuario_categoria[i][5])
            })

        i = i + 1

    return filas_filtradas



def preparar_enlaces_articulos_comunes(enlaces_comunes):
    """
    Convierte las tuplas SQL en diccionarios para Neo4J.
    """
    enlaces = []
    i = 0

    while i < len(enlaces_comunes):
        enlaces.append({
            "id_usuario_1": enlaces_comunes[i][0],
            "id_usuario_2": enlaces_comunes[i][1],
            "articulos_comunes": int(enlaces_comunes[i][2])
        })
        i = i + 1

    return enlaces


# ============================================================
# OPCIONES DEL MENU
# ============================================================


def ejecutar_apartado_41(conexion_mysql):
    """
    Apartado 4.1 del enunciado.
    """
    print()
    print("Obteniendo los " + str(NUM_USUARIOS_SIMILITUD) + " usuarios con más reviews...")

    top_usuarios = consulta_top_usuarios(conexion_mysql, NUM_USUARIOS_SIMILITUD)

    if len(top_usuarios) == 0:
        print("No hay usuarios para procesar.")
        return

    ids_usuarios = []
    i = 0
    while i < len(top_usuarios):
        ids_usuarios.append(top_usuarios[i][0])
        i = i + 1

    print("Calculando las similitudes de Pearson...")
    reviews_usuarios = consulta_valoraciones_por_articulo_usuario(conexion_mysql, ids_usuarios)
    ratings_por_usuario = construir_estructura_ratings(reviews_usuarios)
    similitudes = calcular_todas_las_similitudes(top_usuarios, ratings_por_usuario)

    guardar_similitudes_en_csv(similitudes, top_usuarios, RUTA_FICHERO_SIMILITUDES)

    print("Limpiando Neo4J antes de cargar el nuevo grafo...")
    limpiar_neo4j()

    print("Cargando usuarios y relaciones de similitud en Neo4J...")
    cargar_grafo_similitudes_en_neo4j(top_usuarios, similitudes)

    print("Carga finalizada en Neo4J.")
    print("Se ha generado también el fichero auxiliar: " + RUTA_FICHERO_SIMILITUDES)
    print("Consulta recomendada en el browser de Neo4J: MATCH (n) RETURN n")

    resultado = consulta_usuario_con_mas_vecinos_neo4j()
    if len(resultado) > 0:
        print()
        print("Usuario con más vecinos según Neo4J:")
        print(resultado[0])



def ejecutar_apartado_42(conexion_mysql):
    """
    Apartado 4.2 del enunciado.
    """
    print()
    categoria = pedir_nombre_categoria(conexion_mysql)
    cantidad = pedir_entero_positivo("Introduce el número de artículos aleatorios: ")

    print("Buscando artículos aleatorios...")
    articulos = consulta_articulos_aleatorios_por_categoria(conexion_mysql, categoria, cantidad)

    if len(articulos) == 0:
        print("No hay artículos en esa categoría o el número pedido es demasiado grande.")
        return

    ids_articulos = []
    i = 0
    while i < len(articulos):
        ids_articulos.append(articulos[i][0])
        i = i + 1

    print("Recuperando usuarios y reviews de esos artículos...")
    reviews_articulos = consulta_reviews_de_articulos_por_categoria(
        conexion_mysql, ids_articulos, categoria
    )
    filas_neo4j = preparar_filas_reviews_para_neo4j(reviews_articulos)

    print("Limpiando Neo4J antes de cargar el nuevo grafo...")
    limpiar_neo4j()

    print("Cargando artículos, usuarios y enlaces en Neo4J...")
    cargar_grafo_articulos_usuarios_en_neo4j(filas_neo4j)

    print("Carga finalizada en Neo4J.")
    print("Consulta recomendada en el browser de Neo4J: MATCH (n) RETURN n")

def ejecutar_apartado_43(conexion_mysql):
    """
    Apartado 4.3 del enunciado.
    """
    print()
    print("Recuperando los primeros " + str(NUM_USUARIOS_ORDENADOS) + " usuarios ordenados por nombre...")

    usuarios = consulta_primeros_usuarios_ordenados_por_nombre(
        conexion_mysql,
        NUM_USUARIOS_ORDENADOS
    )

    if len(usuarios) == 0:
        print("No hay usuarios para procesar.")
        return

    ids_usuarios = []
    i = 0
    while i < len(usuarios):
        ids_usuarios.append(usuarios[i][0])
        i = i + 1

    print("Calculando los tipos de artículo puntuados por esos usuarios...")
    filas_usuario_categoria = consulta_articulos_distintos_por_tipo(conexion_mysql, ids_usuarios)

    datos_totales = consulta_total_articulos_distintos(conexion_mysql, ids_usuarios)
    total_articulos_por_usuario = {}
    i = 0
    while i < len(datos_totales):
        total_articulos_por_usuario[datos_totales[i][0]] = int(datos_totales[i][1])
        i = i + 1

    filas_filtradas = filtrar_usuarios_multicategoria(filas_usuario_categoria, total_articulos_por_usuario)

    if len(filas_filtradas) == 0:
        print("No se han encontrado usuarios con artículos de más de un tipo.")
        return

    print("Limpiando Neo4J antes de cargar el nuevo grafo...")
    limpiar_neo4j()

    print("Cargando usuarios, tipos de artículo y enlaces en Neo4J...")
    cargar_grafo_usuarios_tipos_en_neo4j(filas_filtradas)

    print("Carga finalizada en Neo4J.")
    print("Consulta recomendada en el browser de Neo4J: MATCH (n) RETURN n")



def ejecutar_apartado_44(conexion_mysql):
    """
    Apartado 4.4 del enunciado.
    """
    print()
    print("Buscando los artículos populares...")

    articulos = consulta_articulos_populares(conexion_mysql)

    if len(articulos) == 0:
        print("No se han encontrado artículos que cumplan la condición pedida.")
        return

    ids_articulos = []
    i = 0
    while i < len(articulos):
        ids_articulos.append(articulos[i][0])
        i = i + 1

    print("Recuperando usuarios y reviews de esos artículos...")
    reviews_articulos = consulta_reviews_de_articulos(conexion_mysql, ids_articulos)
    filas_neo4j = preparar_filas_reviews_para_neo4j(reviews_articulos)

    print("Calculando artículos en común entre usuarios...")
    enlaces_sql = consulta_articulos_en_comun_usuarios(conexion_mysql, ids_articulos)
    enlaces_neo4j = preparar_enlaces_articulos_comunes(enlaces_sql)

    print("Limpiando Neo4J antes de cargar el nuevo grafo...")
    limpiar_neo4j()

    print("Cargando artículos, usuarios y enlaces en Neo4J...")
    cargar_grafo_articulos_populares_en_neo4j(filas_neo4j, enlaces_neo4j)

    print("Carga finalizada en Neo4J.")
    print("Consulta recomendada en el browser de Neo4J: MATCH (n) RETURN n")

def main():
    """
    Menú principal del proyecto Neo4J.
    """
    conexion_mysql = None
    salir = False

    try:
        conexion_mysql = get_conexion_mysql()
        crear_restricciones_neo4j()

        while salir is False:
            opcion = pedir_opcion_menu()

            try:
                if opcion == "1":
                    ejecutar_apartado_41(conexion_mysql)
                elif opcion == "2":
                    ejecutar_apartado_42(conexion_mysql)
                elif opcion == "3":
                    ejecutar_apartado_43(conexion_mysql)
                elif opcion == "4":
                    ejecutar_apartado_44(conexion_mysql)
                elif opcion == "5":
                    salir = True
                    print("Saliendo del programa...")
            except KeyboardInterrupt:
                print()
                print("Operacion interrumpida por el usuario.")
            except Exception as error:
                print("Se ha producido un error durante la ejecucion:")
                print(error)

    finally:
        if conexion_mysql is not None:
            conexion_mysql.close()
        driver.close()


if __name__ == "__main__":
    main()
