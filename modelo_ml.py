# ============================================================
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodriguez
# ============================================================

"""
modelo_ml.py

Opcional del proyecto de Bases de Datos (apartado 7).
Implementacion del modelo de Machine Learning propuesto en la
seccion 5.2 del informe: filtrado colaborativo basado en
similitud entre usuarios (user-based collaborative filtering)
con correlacion de Pearson.

El programa:
1. Recupera las valoraciones de MySQL.
2. Divide los datos en entrenamiento (80%) y test (20%).
3. Construye la matriz usuario-articulo con los datos de entrenamiento.
4. Para cada usuario del conjunto de test, busca los k vecinos mas
   similares (Pearson positiva) y predice la puntuacion.
5. Evalua el modelo con el error absoluto medio (MAE).
6. Permite al usuario solicitar recomendaciones interactivas.

Esquema MySQL esperado:
- USUARIO(id_usuario, reviewerID, reviewerName)
- CATEGORIA(id_categoria, nombre_categoria)
- ARTICULO(id_articulo, asin)
- REVIEW(id_review, id_usuario, id_articulo, overall, unixReviewTime, reviewTime)
- REVIEW_CATEGORIA(id_review, id_categoria)
"""

import math
import random
import pymysql

from configuracion import (
    MYSQL_HOST,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE
)


# ============================================================
# CONSTANTES
# ============================================================

# Numero de vecinos mas similares a considerar para la prediccion
K_VECINOS = 20

# Proporcion de datos que se usan para entrenamiento (el resto es test)
PROPORCION_ENTRENAMIENTO = 0.8

# Numero de recomendaciones a mostrar
NUM_RECOMENDACIONES = 10

# Semilla para reproducibilidad de la division entrenamiento/test
SEMILLA_RANDOM = 42


# ============================================================
# CONEXION
# ============================================================


def get_conexion_mysql():
    """
    Funcion para obtener la conexion a MySQL.
    """
    conexion = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    return conexion


# ============================================================
# CONSULTAS MYSQL
# ============================================================


def obtener_todas_las_valoraciones(conexion):
    """
    Obtiene todas las valoraciones de la tabla REVIEW.
    Si un usuario ha valorado el mismo articulo mas de una vez,
    se toma la media (coherente con el apartado 4.1 del proyecto).

    Devuelve una lista de tuplas (id_usuario, id_articulo, overall).
    """
    cursor = conexion.cursor()
    sql = """
    SELECT r.id_usuario,
           r.id_articulo,
           AVG(r.overall) AS valoracion_media
    FROM REVIEW r
    GROUP BY r.id_usuario, r.id_articulo
    ORDER BY r.id_usuario ASC, r.id_articulo ASC;
    """
    cursor.execute(sql)
    resultado = cursor.fetchall()
    cursor.close()
    return resultado


def obtener_asin_por_id(conexion, id_articulo):
    """
    Dado un id_articulo interno, devuelve su ASIN original.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT asin FROM ARTICULO WHERE id_articulo = %s;
    """
    cursor.execute(sql, [id_articulo])
    resultado = cursor.fetchone()
    cursor.close()

    if resultado is not None:
        return resultado[0]

    return None


def usuario_existe(conexion, reviewer_id):
    """
    Comprueba si un usuario existe en la tabla USUARIO a partir
    de su reviewerID original.
    Devuelve el id_usuario interno si existe, o None si no.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT id_usuario
    FROM USUARIO
    WHERE reviewerID = %s;
    """
    cursor.execute(sql, [reviewer_id])
    resultado = cursor.fetchone()
    cursor.close()

    if resultado is not None:
        return resultado[0]

    return None


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


def obtener_articulos_categoria(conexion, categoria):
    """
    Obtiene los id_articulo que pertenecen a una categoria
    (a traves de REVIEW_CATEGORIA).
    """
    cursor = conexion.cursor()
    sql = """
    SELECT DISTINCT r.id_articulo
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    WHERE c.nombre_categoria = %s;
    """
    cursor.execute(sql, [categoria])
    resultado = cursor.fetchall()
    cursor.close()

    articulos = {}
    i = 0
    while i < len(resultado):
        articulos[resultado[i][0]] = True
        i = i + 1

    return articulos


# ============================================================
# FASE 1: CONSTRUCCION DE LA MATRIZ USUARIO-ARTICULO
# ============================================================


def construir_estructura_ratings(valoraciones):
    """
    Construye un diccionario de diccionarios:
    ratings[id_usuario] = {id_articulo: overall, ...}
    """
    ratings = {}

    i = 0
    while i < len(valoraciones):
        id_usuario = valoraciones[i][0]
        id_articulo = valoraciones[i][1]
        overall = float(valoraciones[i][2])

        if id_usuario not in ratings:
            ratings[id_usuario] = {}

        ratings[id_usuario][id_articulo] = overall
        i = i + 1

    return ratings


# ============================================================
# DIVISION ENTRENAMIENTO / TEST
# ============================================================


def dividir_entrenamiento_test(ratings):
    """
    Divide las valoraciones de cada usuario en entrenamiento y test.

    Para cada usuario, se barajan sus valoraciones y se asigna un
    80% al entrenamiento y un 20% al test. Solo se incluyen en el
    test los usuarios que tienen al menos 5 valoraciones (para que
    haya suficiente informacion en entrenamiento).

    Devuelve dos diccionarios con la misma estructura que ratings.
    """
    random.seed(SEMILLA_RANDOM)

    entrenamiento = {}
    test = {}

    usuarios = list(ratings.keys())
    i = 0
    while i < len(usuarios):
        id_usuario = usuarios[i]
        articulos = list(ratings[id_usuario].keys())

        if len(articulos) < 5:
            # Usuarios con pocas valoraciones van completos a entrenamiento
            entrenamiento[id_usuario] = {}
            j = 0
            while j < len(articulos):
                id_articulo = articulos[j]
                entrenamiento[id_usuario][id_articulo] = ratings[id_usuario][id_articulo]
                j = j + 1
        else:
            # Barajar y dividir
            random.shuffle(articulos)
            corte = int(len(articulos) * PROPORCION_ENTRENAMIENTO)

            entrenamiento[id_usuario] = {}
            j = 0
            while j < corte:
                id_articulo = articulos[j]
                entrenamiento[id_usuario][id_articulo] = ratings[id_usuario][id_articulo]
                j = j + 1

            test[id_usuario] = {}
            j = corte
            while j < len(articulos):
                id_articulo = articulos[j]
                test[id_usuario][id_articulo] = ratings[id_usuario][id_articulo]
                j = j + 1

        i = i + 1

    return entrenamiento, test


# ============================================================
# FASE 2: CALCULO DE SIMILITUDES (PEARSON)
# ============================================================


def media_ratings(ratings_usuario):
    """
    Calcula la media de las valoraciones de un usuario.
    """
    if len(ratings_usuario) == 0:
        return 0.0

    suma = 0.0
    for id_articulo in ratings_usuario:
        suma = suma + ratings_usuario[id_articulo]

    return suma / len(ratings_usuario)


def calcular_pearson(ratings_u, ratings_v):
    """
    Calcula la correlacion de Pearson entre dos usuarios.
    Las medias se calculan con TODAS las valoraciones de cada
    usuario (no solo las comunes), coherente con la interpretacion
    adoptada en el apartado 4.1 del proyecto.

    Devuelve el valor de Pearson, o None si no hay articulos
    comunes o el denominador es 0.
    """
    # Buscar articulos en comun
    articulos_comunes = []
    for id_articulo in ratings_u:
        if id_articulo in ratings_v:
            articulos_comunes.append(id_articulo)

    if len(articulos_comunes) == 0:
        return None

    media_u = media_ratings(ratings_u)
    media_v = media_ratings(ratings_v)

    numerador = 0.0
    suma_u = 0.0
    suma_v = 0.0

    i = 0
    while i < len(articulos_comunes):
        id_articulo = articulos_comunes[i]
        diff_u = ratings_u[id_articulo] - media_u
        diff_v = ratings_v[id_articulo] - media_v
        numerador = numerador + (diff_u * diff_v)
        suma_u = suma_u + (diff_u * diff_u)
        suma_v = suma_v + (diff_v * diff_v)
        i = i + 1

    denominador = math.sqrt(suma_u) * math.sqrt(suma_v)

    if denominador == 0:
        return None

    return numerador / denominador


def obtener_k_vecinos(id_usuario_objetivo, ratings_entrenamiento, k):
    """
    Busca los k usuarios mas similares al usuario objetivo,
    considerando solo aquellos con Pearson positiva.

    Devuelve una lista de tuplas (id_vecino, similitud) ordenada
    de mayor a menor similitud.
    """
    similitudes = []

    if id_usuario_objetivo not in ratings_entrenamiento:
        return similitudes

    ratings_objetivo = ratings_entrenamiento[id_usuario_objetivo]

    usuarios = list(ratings_entrenamiento.keys())
    i = 0
    while i < len(usuarios):
        id_otro = usuarios[i]
        if id_otro != id_usuario_objetivo:
            pearson = calcular_pearson(ratings_objetivo, ratings_entrenamiento[id_otro])
            if pearson is not None and pearson > 0:
                similitudes.append((id_otro, pearson))
        i = i + 1

    # Ordenar de mayor a menor similitud
    similitudes.sort(key=lambda x: x[1], reverse=True)

    # Devolver solo los k primeros
    if len(similitudes) > k:
        return similitudes[0:k]

    return similitudes


# ============================================================
# FASE 3: PREDICCION DE PUNTUACIONES
# ============================================================


def predecir_puntuacion(id_usuario, id_articulo, ratings_entrenamiento, vecinos):
    """
    Predice la puntuacion que el usuario daria a un articulo
    usando la formula del informe (seccion 5.2.3, Fase 3)

    Solo se usan los vecinos que han puntuado el articulo.
    Si ningun vecino ha puntuado el articulo, devuelve None.
    """
    media_u = media_ratings(ratings_entrenamiento[id_usuario])

    numerador = 0.0
    denominador = 0.0

    i = 0
    while i < len(vecinos):
        id_vecino = vecinos[i][0]
        similitud = vecinos[i][1]

        if id_vecino in ratings_entrenamiento:
            if id_articulo in ratings_entrenamiento[id_vecino]:
                media_v = media_ratings(ratings_entrenamiento[id_vecino])
                r_vi = ratings_entrenamiento[id_vecino][id_articulo]
                numerador = numerador + similitud * (r_vi - media_v)
                denominador = denominador + abs(similitud)
        i = i + 1

    if denominador == 0:
        return None

    prediccion = media_u + (numerador / denominador)

    # Limitar al rango valido [1, 5]
    if prediccion < 1.0:
        prediccion = 1.0
    if prediccion > 5.0:
        prediccion = 5.0

    return prediccion


# ============================================================
# FASE 4: EVALUACION DEL MODELO (MAE)
# ============================================================


def evaluar_modelo(ratings_entrenamiento, ratings_test, k):
    """
    Evalua el modelo calculando el MAE (error absoluto medio)
    sobre el conjunto de test.

    Para cada valoracion del test, intenta predecirla usando
    los vecinos del entrenamiento.
    """
    suma_errores = 0.0
    total_predicciones = 0
    predicciones_fallidas = 0

    usuarios_test = list(ratings_test.keys())

    print("Evaluando modelo con " + str(len(usuarios_test))
          + " usuarios de test...")
    print()

    i = 0
    while i < len(usuarios_test):
        id_usuario = usuarios_test[i]

        # Mostrar progreso cada 100 usuarios
        if i % 100 == 0 and i > 0:
            print("  Procesados " + str(i) + " / "
                  + str(len(usuarios_test)) + " usuarios...")

        # Obtener vecinos para este usuario
        vecinos = obtener_k_vecinos(id_usuario, ratings_entrenamiento, k)

        # Intentar predecir cada valoracion del test
        articulos_test = list(ratings_test[id_usuario].keys())
        j = 0
        while j < len(articulos_test):
            id_articulo = articulos_test[j]
            real = ratings_test[id_usuario][id_articulo]

            prediccion = predecir_puntuacion(
                id_usuario, id_articulo, ratings_entrenamiento, vecinos
            )

            if prediccion is not None:
                error = abs(prediccion - real)
                suma_errores = suma_errores + error
                total_predicciones = total_predicciones + 1
            else:
                predicciones_fallidas = predicciones_fallidas + 1

            j = j + 1

        i = i + 1

    print()
    print("============================================================")
    print("RESULTADOS DE LA EVALUACION")
    print("============================================================")
    print("Numero de vecinos (k): " + str(k))
    print("Predicciones realizadas: " + str(total_predicciones))
    print("Predicciones no posibles (sin vecinos): " + str(predicciones_fallidas))

    if total_predicciones > 0:
        mae = suma_errores / total_predicciones
        print("MAE (error absoluto medio): " + str(round(mae, 4)))
        print()
        print("Interpretacion: de media, la prediccion se desvia "
              + str(round(mae, 2)) + " puntos")
        print("respecto a la puntuacion real (en una escala de 1 a 5).")
    else:
        mae = None
        print("No se pudo calcular el MAE (ninguna prediccion fue posible).")

    print("============================================================")

    return mae


# ============================================================
# RECOMENDACION INTERACTIVA
# ============================================================


def recomendar_articulos(id_usuario, ratings_entrenamiento, vecinos,
                         conexion, categoria=None):
    """
    Genera recomendaciones para un usuario.

    Busca articulos que el usuario no ha puntuado, predice la
    puntuacion y devuelve los mejores.

    Si se indica una categoria, solo se consideran articulos de
    esa categoria.
    """
    articulos_usuario = ratings_entrenamiento.get(id_usuario, {})

    # Recopilar todos los articulos candidatos (no consumidos por el usuario)
    candidatos = {}

    if categoria is not None:
        # Solo articulos de la categoria
        articulos_categoria = obtener_articulos_categoria(conexion, categoria)
        for id_articulo in articulos_categoria:
            if id_articulo not in articulos_usuario:
                candidatos[id_articulo] = True
    else:
        # Todos los articulos que aparecen en los ratings de los vecinos
        i = 0
        while i < len(vecinos):
            id_vecino = vecinos[i][0]
            if id_vecino in ratings_entrenamiento:
                for id_articulo in ratings_entrenamiento[id_vecino]:
                    if id_articulo not in articulos_usuario:
                        candidatos[id_articulo] = True
            i = i + 1

    # Predecir puntuacion para cada candidato
    predicciones = []
    lista_candidatos = list(candidatos.keys())

    i = 0
    while i < len(lista_candidatos):
        id_articulo = lista_candidatos[i]
        pred = predecir_puntuacion(
            id_usuario, id_articulo, ratings_entrenamiento, vecinos
        )
        if pred is not None:
            predicciones.append((id_articulo, pred))
        i = i + 1

    # Ordenar por prediccion descendente
    predicciones.sort(key=lambda x: x[1], reverse=True)

    # Devolver las mejores
    if len(predicciones) > NUM_RECOMENDACIONES:
        return predicciones[0:NUM_RECOMENDACIONES]

    return predicciones


# ============================================================
# FUNCIONES DE ENTRADA
# ============================================================


def pedir_reviewer_id(conexion):
    """
    Pide el reviewerID al usuario y lo valida contra la base de datos.
    """
    id_usuario = None

    while id_usuario is None:
        reviewer_id = input("Introduce el reviewerID del usuario: ").strip()

        if reviewer_id == "":
            print("Debes introducir un reviewerID no vacio.")
        else:
            id_usuario = usuario_existe(conexion, reviewer_id)
            if id_usuario is None:
                print("No se ha encontrado ningun usuario con ese reviewerID.")

    return reviewer_id, id_usuario


def pedir_categoria(conexion):
    """
    Pide la categoria al usuario. Muestra las disponibles y
    permite elegir 'Todo' para no filtrar.
    """
    categorias = obtener_categorias(conexion)

    print()
    print("Categorias disponibles:")
    i = 0
    while i < len(categorias):
        print("  - " + categorias[i])
        i = i + 1
    print("  - Todo (sin filtrar por categoria)")
    print()

    categoria = None

    while categoria is None:
        opcion = input("Introduce la categoria (o 'Todo'): ").strip()

        if opcion == "":
            print("Debes introducir una categoria.")
        elif opcion == "Todo" or opcion == "todo":
            categoria = "Todo"
        elif opcion in categorias:
            categoria = opcion
        else:
            print("Esa categoria no existe.")

    return categoria


# ============================================================
# MENU
# ============================================================


def imprimir_menu():
    """
    Muestra el menu principal.
    """
    print()
    print("============================================================")
    print("MODELO DE MACHINE LEARNING - FILTRADO COLABORATIVO")
    print("============================================================")
    print("1. Evaluar el modelo (entrenamiento/test con MAE)")
    print("2. Obtener recomendaciones para un usuario")
    print("0. Salir")


def ejecutar_menu(conexion):
    """
    Ejecuta el bucle principal del menu.
    """
    # Cargar todos los datos al inicio
    print("Cargando valoraciones de la base de datos...")
    valoraciones = obtener_todas_las_valoraciones(conexion)
    print("Se han cargado " + str(len(valoraciones)) + " valoraciones.")

    print("Construyendo matriz usuario-articulo...")
    ratings = construir_estructura_ratings(valoraciones)
    print("Usuarios en la matriz: " + str(len(ratings)))

    print("Dividiendo datos en entrenamiento (80%) y test (20%)...")
    entrenamiento, test = dividir_entrenamiento_test(ratings)
    print("Usuarios en test: " + str(len(test)))
    print()
    print("Datos cargados correctamente.")

    seguir = True

    while seguir is True:
        imprimir_menu()
        opcion = input("Selecciona una opcion: ").strip()

        try:
            if opcion == "1":
                print()
                evaluar_modelo(entrenamiento, test, K_VECINOS)

            elif opcion == "2":
                print()
                reviewer_id, id_usuario = pedir_reviewer_id(conexion)

                if id_usuario not in entrenamiento:
                    print("Este usuario no tiene valoraciones suficientes")
                    print("en el conjunto de entrenamiento.")
                else:
                    categoria = pedir_categoria(conexion)

                    print()
                    print("Buscando vecinos similares...")
                    vecinos = obtener_k_vecinos(
                        id_usuario, entrenamiento, K_VECINOS
                    )
                    print("Vecinos encontrados: " + str(len(vecinos)))

                    if len(vecinos) == 0:
                        print("No se han encontrado vecinos similares.")
                        print("No es posible generar recomendaciones.")
                    else:
                        cat = None
                        if categoria != "Todo":
                            cat = categoria

                        print("Calculando predicciones...")
                        recomendaciones = recomendar_articulos(
                            id_usuario, entrenamiento, vecinos, conexion, cat
                        )

                        if len(recomendaciones) == 0:
                            print("No se han podido generar recomendaciones.")
                        else:
                            print()
                            texto_cat = categoria
                            print("Top " + str(len(recomendaciones))
                                  + " recomendaciones para " + reviewer_id
                                  + " (" + texto_cat + "):")
                            print()
                            print("  {:>4}   {:<15}  {}".format(
                                "#", "ASIN", "Pred. puntuacion"))
                            print("  " + "-" * 45)

                            j = 0
                            while j < len(recomendaciones):
                                id_art = recomendaciones[j][0]
                                pred = recomendaciones[j][1]
                                asin = obtener_asin_por_id(conexion, id_art)
                                if asin is None:
                                    asin = "???"
                                print("  {:>4}   {:<15}  {:.2f}".format(
                                    j + 1, asin, pred))
                                j = j + 1

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

    try:
        conexion_mysql = get_conexion_mysql()
        ejecutar_menu(conexion_mysql)
    except Exception as error:
        print("No se ha podido iniciar el programa correctamente.")
        print(error)
    finally:
        if conexion_mysql is not None:
            conexion_mysql.close()


if __name__ == "__main__":
    main()
