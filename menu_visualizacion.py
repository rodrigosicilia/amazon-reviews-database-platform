# ============================================================
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodríguez
# ============================================================

"""
menu_visualizacion.py

Segunda parte del proyecto de Bases de Datos.
Menu por terminal para obtener las visualizaciones pedidas en el enunciado.

Esquema MySQL esperado:
- USUARIO(id_usuario, reviewerID, reviewerName)
- CATEGORIA(id_categoria, nombre_categoria)
- ARTICULO(id_articulo, asin)
- REVIEW(id_review, id_usuario, id_articulo, overall, unixReviewTime, reviewTime)
- REVIEW_CATEGORIA(id_review, id_categoria)

Colección MongoDB esperada:
- reviews_texto(_id, id_review, helpful, summary, reviewText)
"""

import re
from collections import Counter

import pymysql
from pymongo import MongoClient

import matplotlib.pyplot as plt
from wordcloud import WordCloud

from configuracion import (
    MYSQL_HOST,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    MONGO_HOST,
    MONGO_PORT,
    MONGO_DATABASE,
    MONGO_COLLECTION_REVIEWS
)


# ============================================================
# CONSTANTES
# ============================================================

# Tamano de lote para las consultas $in a MongoDB en la nube de palabras.
# Con 50000 se reducen los round trips de ~33 a ~4 para una categoria de
# 167000 reviews, lo que mejora sensiblemente el tiempo de generacion.
# El tamano es seguro: 50000 enteros ocupan ~400KB, muy por debajo del
# limite de 16MB por consulta de MongoDB.
TAMANO_LOTE = 50000


# ============================================================
# CONEXIONES
# ============================================================


def get_conexion_mysql():
    """
    Funcion para obtener la conexion a MySQL.
    Sigue el estilo del tutorial de PyMySQL.
    """
    conexion = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    return conexion



def get_client_mongo():
    """
    Funcion para obtener el cliente de MongoDB.
    Sigue el estilo del manual de MongoDB y Pymongo.
    """
    connection_string = "mongodb://" + str(MONGO_HOST) + ":" + str(MONGO_PORT)
    return MongoClient(connection_string)



def get_database_mongo(client):
    """
    Obtiene la base de datos de MongoDB.
    """
    return client[MONGO_DATABASE]



def get_collection_mongo(dbname):
    """
    Obtiene la coleccion de MongoDB con los textos de las reviews.
    """
    return dbname[MONGO_COLLECTION_REVIEWS]


# ============================================================
# FUNCIONES AUXILIARES DE ENTRADA
# ============================================================


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



def pedir_categoria(conexion, permitir_todo):
    """
    Pide al usuario una categoria.
    Si permitir_todo es True, devuelve None cuando se introduce todo.
    Muestra las categorias disponibles y valida contra la lista obtenida.
    """
    categorias = obtener_categorias(conexion)

    categoria = None
    correcta = False

    while correcta is False:
        print()
        print("Categorias disponibles:")
        i = 0
        while i < len(categorias):
            print("  - " + categorias[i])
            i = i + 1

        if permitir_todo is True:
            print("  - Todo")
        print()

        opcion = input("Categoria: ").strip()

        if permitir_todo is True:
            if opcion.lower() == "todo" or opcion.lower() == "todas":
                categoria = None
                correcta = True

        if correcta is False:
            if opcion == "":
                print("Debes introducir una categoria.")
            else:
                if opcion in categorias:
                    categoria = opcion
                    correcta = True
                else:
                    print("Esa categoria no existe.")

    return categoria



def pedir_asin():
    """
    Pide un ASIN al usuario.
    """
    asin = ""
    correcto = False

    while correcto is False:
        asin = input("Introduce el ASIN del articulo: ").strip()
        if asin != "":
            correcto = True
        else:
            print("Debes introducir un ASIN no vacio.")

    return asin


# ============================================================
# CONSULTAS MYSQL
# ============================================================


def consulta_reviews_por_anio(conexion, categoria):
    """
    Numero de reviews por anio.
    """
    cursor = conexion.cursor()

    if categoria is None:
        sql = """
        SELECT YEAR(reviewTime) AS anio, COUNT(*) AS numero_reviews
        FROM REVIEW
        WHERE reviewTime IS NOT NULL
        GROUP BY YEAR(reviewTime)
        ORDER BY anio;
        """
        cursor.execute(sql)
    else:
        sql = """
        SELECT YEAR(r.reviewTime) AS anio, COUNT(*) AS numero_reviews
        FROM REVIEW r
        INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
        INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
        WHERE c.nombre_categoria = %s AND r.reviewTime IS NOT NULL
        GROUP BY YEAR(r.reviewTime)
        ORDER BY anio;
        """
        cursor.execute(sql, [categoria])

    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_popularidad_articulos(conexion, categoria):
    """
    Numero de reviews por articulo, ordenado de mayor a menor.
    """
    cursor = conexion.cursor()

    if categoria is None:
        sql = """
        SELECT a.asin, COUNT(*) AS numero_reviews
        FROM REVIEW r
        INNER JOIN ARTICULO a ON r.id_articulo = a.id_articulo
        GROUP BY a.id_articulo, a.asin
        ORDER BY numero_reviews DESC, a.asin ASC;
        """
        cursor.execute(sql)
    else:
        sql = """
        SELECT a.asin, COUNT(*) AS numero_reviews
        FROM REVIEW r
        INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
        INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
        INNER JOIN ARTICULO a ON r.id_articulo = a.id_articulo
        WHERE c.nombre_categoria = %s
        GROUP BY a.id_articulo, a.asin
        ORDER BY numero_reviews DESC, a.asin ASC;
        """
        cursor.execute(sql, [categoria])

    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def articulo_existe(conexion, asin):
    """
    Comprueba si existe un articulo con ese ASIN.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT asin
    FROM ARTICULO
    WHERE asin = %s;
    """
    cursor.execute(sql, [asin])
    resultado = cursor.fetchone()
    cursor.close()

    if resultado is None:
        return False
    return True



def consulta_histograma_por_nota_todo(conexion):
    """
    Numero de reviews por nota para todos los productos.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT overall AS nota, COUNT(*) AS numero_reviews
    FROM REVIEW
    GROUP BY overall
    ORDER BY nota;
    """
    cursor.execute(sql)
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_histograma_por_nota_categoria(conexion, categoria):
    """
    Numero de reviews por nota para una categoria.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT r.overall AS nota, COUNT(*) AS numero_reviews
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    WHERE c.nombre_categoria = %s
    GROUP BY r.overall
    ORDER BY nota;
    """
    cursor.execute(sql, [categoria])
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_histograma_por_nota_articulo(conexion, asin):
    """
    Numero de reviews por nota para un articulo individual.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT r.overall AS nota, COUNT(*) AS numero_reviews
    FROM REVIEW r
    INNER JOIN ARTICULO a ON r.id_articulo = a.id_articulo
    WHERE a.asin = %s
    GROUP BY r.overall
    ORDER BY nota;
    """
    cursor.execute(sql, [asin])
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_reviews_tiempo_una_categoria(conexion, categoria):
    """
    Numero de reviews por timestamp para una sola categoria.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT r.unixReviewTime, COUNT(*) AS numero_reviews
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    WHERE c.nombre_categoria = %s
    GROUP BY r.unixReviewTime
    ORDER BY r.unixReviewTime ASC;
    """
    cursor.execute(sql, [categoria])
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_reviews_tiempo_global(conexion):
    """
    Numero de reviews por timestamp para todas las categorias sumadas.
    Cada review se cuenta una sola vez, sin hacer JOIN con categorias.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT r.unixReviewTime, COUNT(*) AS numero_reviews
    FROM REVIEW r
    GROUP BY r.unixReviewTime
    ORDER BY r.unixReviewTime ASC;
    """
    cursor.execute(sql)
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_reviews_tiempo_categorias(conexion):
    """
    Numero de reviews por categoria y timestamp.
    Luego se acumula en Python para la grafica.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT c.nombre_categoria, r.unixReviewTime, COUNT(*) AS numero_reviews
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    GROUP BY c.nombre_categoria, r.unixReviewTime
    ORDER BY c.nombre_categoria ASC, r.unixReviewTime ASC;
    """
    cursor.execute(sql)
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_reviews_por_usuario(conexion):
    """
    Histograma de reviews por usuario.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT t.numero_reviews, COUNT(*) AS numero_usuarios
    FROM (
        SELECT id_usuario, COUNT(*) AS numero_reviews
        FROM REVIEW
        GROUP BY id_usuario
    ) AS t
    GROUP BY t.numero_reviews
    ORDER BY t.numero_reviews;
    """
    cursor.execute(sql)
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_media_nota_por_categoria(conexion):
    """
    Visualizacion extra: media de nota por categoria.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT c.nombre_categoria, AVG(r.overall) AS media_nota
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    GROUP BY c.nombre_categoria
    ORDER BY c.nombre_categoria;
    """
    cursor.execute(sql)
    resultado = cursor.fetchall()
    cursor.close()
    return resultado



def consulta_ids_reviews_categoria(conexion, categoria):
    """
    Devuelve los id_review de una categoria.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT r.id_review
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    WHERE c.nombre_categoria = %s;
    """
    cursor.execute(sql, [categoria])
    resultado = cursor.fetchall()
    cursor.close()

    ids = []
    i = 0
    while i < len(resultado):
        ids.append(resultado[i][0])
        i = i + 1

    return ids


# ============================================================
# CONSULTAS MONGODB
# ============================================================


def obtener_frecuencias_palabras(collection, ids_review):
    """
    Obtiene las frecuencias de palabras de los summaries asociados
    a una lista de id_review. Se procesan por lotes para no saturar
    la consulta a MongoDB y se cuentan directamente en memoria
    sin construir una cadena de texto gigante.
    Solo se tienen en cuenta palabras de longitud mayor que 3.
    """
    frecuencias = Counter()
    inicio = 0

    while inicio < len(ids_review):
        fin = inicio + TAMANO_LOTE
        lote = ids_review[inicio:fin]

        resultados = collection.find(
            {"id_review": {"$in": lote}},
            {"summary": 1, "_id": 0}
        )

        for documento in resultados:
            summary = documento.get("summary")
            if summary is not None:
                texto = str(summary).strip()
                if texto != "":
                    palabras = re.findall(r"[A-Za-zÀ-ÿ0-9']+", texto)
                    for palabra in palabras:
                        p = palabra.lower()
                        if len(p) > 3:
                            frecuencias[p] += 1

        inicio = fin

    return frecuencias


# ============================================================
# FUNCIONES DE VISUALIZACION
# ============================================================


def comprobar_matplotlib():
    """
    Mantiene una comprobacion sencilla antes de dibujar.
    """
    return True



def mostrar_reviews_por_anio(conexion):
    """
    Opcion 1 del menu.
    """
    if comprobar_matplotlib() is False:
        return

    categoria = pedir_categoria(conexion, True)
    datos = consulta_reviews_por_anio(conexion, categoria)

    if len(datos) == 0:
        print("No hay datos para esa seleccion.")
        return

    anios = []
    numero_reviews = []

    i = 0
    while i < len(datos):
        anios.append(int(datos[i][0]))
        numero_reviews.append(datos[i][1])
        i = i + 1

    plt.figure(figsize=(10, 6))
    plt.bar(anios, numero_reviews)
    plt.xticks(anios)
    if categoria is None:
        plt.title("Reviews por año de todos los productos")
    else:
        plt.title("Reviews por año de " + categoria)
    plt.xlabel("Años")
    plt.ylabel("Numero de reviews")
    plt.tight_layout()
    plt.show()



def mostrar_popularidad_articulos(conexion):
    """
    Opcion 2 del menu.
    """
    if comprobar_matplotlib() is False:
        return

    categoria = pedir_categoria(conexion, True)
    datos = consulta_popularidad_articulos(conexion, categoria)

    if len(datos) == 0:
        print("No hay datos para esa seleccion.")
        return

    posiciones = []
    popularidad = []
    i = 0
    while i < len(datos):
        posiciones.append(i + 1)
        popularidad.append(datos[i][1])
        i = i + 1

    plt.figure(figsize=(10, 6))
    plt.plot(posiciones, popularidad)
    if categoria is None:
        plt.title("Evolucion de la popularidad de todos los productos")
    else:
        plt.title("Evolucion de la popularidad de " + categoria)
    plt.xlabel("Articulos ordenados por popularidad")
    plt.ylabel("Numero de reviews")
    plt.tight_layout()
    plt.show()



def mostrar_histograma_por_nota(conexion):
    """
    Opcion 3 del menu.
    """
    if comprobar_matplotlib() is False:
        return

    print()
    print("Selecciona el modo de consulta:")
    print("1. Todos los productos")
    print("2. Una categoria")
    print("3. Un articulo individual")

    opcion_valida = False
    opcion = ""
    while opcion_valida is False:
        opcion = input("Opcion: ").strip()
        if opcion == "1" or opcion == "2" or opcion == "3":
            opcion_valida = True
        else:
            print("Opcion no valida.")

    datos = []
    titulo = ""

    if opcion == "1":
        datos = consulta_histograma_por_nota_todo(conexion)
        titulo = "Reviews por nota de todos los productos"
    elif opcion == "2":
        categoria = pedir_categoria(conexion, False)
        datos = consulta_histograma_por_nota_categoria(conexion, categoria)
        titulo = "Reviews por nota de " + categoria
    else:
        asin = pedir_asin()
        existe = articulo_existe(conexion, asin)
        if existe is False:
            print("Ese articulo no existe.")
            return
        datos = consulta_histograma_por_nota_articulo(conexion, asin)
        titulo = "Reviews por nota del articulo " + asin

    if len(datos) == 0:
        print("No hay datos para esa seleccion.")
        return

    notas = [1, 2, 3, 4, 5]
    conteos = [0, 0, 0, 0, 0]

    i = 0
    while i < len(datos):
        nota = int(datos[i][0])
        if nota >= 1 and nota <= 5:
            conteos[nota - 1] = int(datos[i][1])
        i = i + 1

    plt.figure(figsize=(10, 6))
    plt.bar(notas, conteos)
    plt.title(titulo)
    plt.xlabel("Nota")
    plt.ylabel("Numero de reviews")
    plt.tight_layout()
    plt.show()



def mostrar_evolucion_tiempo(conexion):
    """
    Opcion 4 del menu.
    Ofrece tres modos: una sola categoria, todas juntas o todas separadas.
    """
    if comprobar_matplotlib() is False:
        return

    print()
    print("Selecciona el modo de consulta:")
    print("1. Una sola categoria")
    print("2. Todas juntas (suma global)")
    print("3. Todas a la vez, separadas por categoria")

    opcion_valida = False
    opcion = ""
    while opcion_valida is False:
        opcion = input("Opcion: ").strip()
        if opcion == "1" or opcion == "2" or opcion == "3":
            opcion_valida = True
        else:
            print("Opcion no valida.")

    if opcion == "1":
        categoria = pedir_categoria(conexion, False)
        datos = consulta_reviews_tiempo_una_categoria(conexion, categoria)

        if len(datos) == 0:
            print("No hay datos para esa categoria.")
            return

        tiempos = []
        acumulado = 0
        valores = []
        i = 0
        while i < len(datos):
            acumulado = acumulado + int(datos[i][1])
            tiempos.append(datos[i][0])
            valores.append(acumulado)
            i = i + 1

        plt.figure(figsize=(11, 6))
        plt.plot(tiempos, valores)
        plt.title("Evolucion de las reviews a lo largo del tiempo para " + categoria)
        plt.xlabel("Tiempo")
        plt.ylabel("Numero de reviews hasta ese momento")
        plt.tight_layout()
        plt.show()

    elif opcion == "2":
        datos = consulta_reviews_tiempo_global(conexion)

        if len(datos) == 0:
            print("No hay datos disponibles.")
            return

        tiempos = []
        acumulado = 0
        valores = []
        i = 0
        while i < len(datos):
            acumulado = acumulado + int(datos[i][1])
            tiempos.append(datos[i][0])
            valores.append(acumulado)
            i = i + 1

        plt.figure(figsize=(11, 6))
        plt.plot(tiempos, valores)
        plt.title("Evolucion de las reviews a lo largo del tiempo (todas las categorias)")
        plt.xlabel("Tiempo")
        plt.ylabel("Numero de reviews hasta ese momento")
        plt.tight_layout()
        plt.show()

    else:
        datos = consulta_reviews_tiempo_categorias(conexion)

        if len(datos) == 0:
            print("No hay datos disponibles.")
            return

        series_x = {}
        series_y = {}
        acumulados = {}

        i = 0
        while i < len(datos):
            categoria = datos[i][0]
            if categoria not in series_x:
                series_x[categoria] = []
                series_y[categoria] = []
                acumulados[categoria] = 0
            i = i + 1

        i = 0
        while i < len(datos):
            categoria = datos[i][0]
            tiempo = datos[i][1]
            numero = int(datos[i][2])

            acumulados[categoria] = acumulados[categoria] + numero
            series_x[categoria].append(tiempo)
            series_y[categoria].append(acumulados[categoria])

            i = i + 1

        plt.figure(figsize=(11, 6))
        categorias = list(series_x.keys())
        categorias.sort()

        i = 0
        while i < len(categorias):
            categoria = categorias[i]
            if len(series_x[categoria]) > 0:
                plt.plot(series_x[categoria], series_y[categoria], label=categoria)
            i = i + 1

        plt.title("Evolucion de las reviews a lo largo del tiempo por categoria")
        plt.xlabel("Tiempo")
        plt.ylabel("Numero de reviews hasta ese momento")
        plt.legend()
        plt.tight_layout()
        plt.show()



def mostrar_histograma_reviews_usuario(conexion):
    """
    Opcion 5 del menu.
    """
    if comprobar_matplotlib() is False:
        return

    datos = consulta_reviews_por_usuario(conexion)

    if len(datos) == 0:
        print("No hay datos disponibles.")
        return

    numero_reviews = []
    numero_usuarios = []

    i = 0
    while i < len(datos):
        numero_reviews.append(datos[i][0])
        numero_usuarios.append(datos[i][1])
        i = i + 1

    plt.figure(figsize=(10, 6))
    plt.bar(numero_reviews, numero_usuarios, width=1.0)
    plt.title("Histograma de reviews por usuario")
    plt.xlabel("Numero de reviews")
    plt.ylabel("Numero de usuarios")
    plt.tight_layout()
    plt.show()



def mostrar_nube_palabras(conexion, collection):
    """
    Opcion 6 del menu.
    Usa un Counter para contar frecuencias de palabras directamente
    al recibir cada summary de MongoDB, sin construir una cadena
    de texto gigante. Luego genera la nube con generate_from_frequencies.
    """
    if comprobar_matplotlib() is False:
        return

    categoria = pedir_categoria(conexion, False)
    ids_review = consulta_ids_reviews_categoria(conexion, categoria)

    if len(ids_review) == 0:
        print("No hay reviews para esa categoria.")
        return

    frecuencias = obtener_frecuencias_palabras(collection, ids_review)

    if len(frecuencias) == 0:
        print("No hay suficientes palabras validas para generar la nube.")
        return

    nube = WordCloud(
        width=1200,
        height=600,
        background_color="white",
        collocations=False
    ).generate_from_frequencies(frecuencias)

    plt.figure(figsize=(12, 6))
    plt.imshow(nube, interpolation="bilinear")
    plt.axis("off")
    plt.title("Nube de palabras de summary para " + categoria)
    plt.tight_layout()
    plt.show()



def mostrar_visualizacion_extra(conexion):
    """
    Opcion 7 del menu.
    Visualizacion libre: media de nota por categoria.
    """
    if comprobar_matplotlib() is False:
        return

    datos = consulta_media_nota_por_categoria(conexion)

    if len(datos) == 0:
        print("No hay datos disponibles.")
        return

    categorias = []
    medias = []

    i = 0
    while i < len(datos):
        categorias.append(datos[i][0])
        medias.append(float(datos[i][1]))
        i = i + 1

    plt.figure(figsize=(10, 6))
    plt.bar(categorias, medias)
    plt.title("Media de nota por categoria")
    plt.xlabel("Categoria")
    plt.ylabel("Media de nota")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.show()


# ============================================================
# MENU
# ============================================================


def imprimir_menu():
    """
    Muestra el menu principal.
    """
    print()
    print("============================================================")
    print("MENU DE VISUALIZACIONES")
    print("============================================================")
    print("1. Mostrar la evolucion de reviews por años")
    print("2. Evolucion de la popularidad de los articulos")
    print("3. Histograma por nota")
    print("4. Evolucion de las reviews a lo largo del tiempo")
    print("5. Histograma de reviews por usuario")
    print("6. Nube de palabras por categoria")
    print("7. Visualizacion extra: media de nota por categoria")
    print("0. Salir")



def ejecutar_menu(conexion_mysql, collection):
    """
    Ejecuta el bucle principal del menu.
    """
    seguir = True

    while seguir is True:
        imprimir_menu()
        opcion = input("Selecciona una opcion: ").strip()

        try:
            if opcion == "1":
                mostrar_reviews_por_anio(conexion_mysql)
            elif opcion == "2":
                mostrar_popularidad_articulos(conexion_mysql)
            elif opcion == "3":
                mostrar_histograma_por_nota(conexion_mysql)
            elif opcion == "4":
                mostrar_evolucion_tiempo(conexion_mysql)
            elif opcion == "5":
                mostrar_histograma_reviews_usuario(conexion_mysql)
            elif opcion == "6":
                mostrar_nube_palabras(conexion_mysql, collection)
            elif opcion == "7":
                mostrar_visualizacion_extra(conexion_mysql)
            elif opcion == "0":
                print("Saliendo del programa...")
                seguir = False
            else:
                print("Opcion no valida.")
        except KeyboardInterrupt:
            print()
            print("Operacion interrumpida por el usuario.")
        except Exception as error:
            print("Se ha producido un error durante la ejecucion:")
            print(error)


# ============================================================
# MAIN
# ============================================================


def main():
    """
    Funcion principal.
    """
    conexion_mysql = None
    client = None

    try:
        conexion_mysql = get_conexion_mysql()
        client = get_client_mongo()
        dbname = get_database_mongo(client)
        collection = get_collection_mongo(dbname)
        ejecutar_menu(conexion_mysql, collection)
    except Exception as error:
        print("No se ha podido iniciar el programa correctamente.")
        print(error)
    finally:
        if conexion_mysql is not None:
            conexion_mysql.close()
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
