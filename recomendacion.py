# ============================================================
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodríguez
# ============================================================

"""
recomendacion.py

Quinta parte del proyecto de Bases de Datos (apartado 5.3).
Dado el identificador original de un usuario (reviewerID) y un tipo
de articulo (categoria), devuelve los 10 articulos mas populares
de esa categoria que el usuario no ha consumido.

La popularidad se define como el numero de reviews que tiene cada
articulo dentro de esa categoria, utilizando REVIEW_CATEGORIA como
fuente de procedencia categorica (coherente con el resto del proyecto).

Esquema MySQL esperado:
- USUARIO(id_usuario, reviewerID, reviewerName)
- CATEGORIA(id_categoria, nombre_categoria)
- ARTICULO(id_articulo, asin)
- REVIEW(id_review, id_usuario, id_articulo, overall, unixReviewTime, reviewTime)
- REVIEW_CATEGORIA(id_review, id_categoria)
"""

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

NUM_RECOMENDACIONES = 10


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
# FUNCIONES DE VALIDACION
# ============================================================


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


# ============================================================
# CONSULTA PRINCIPAL
# ============================================================


def consulta_recomendaciones(conexion, id_usuario, categoria, limite):
    """
    Obtiene los articulos mas populares de una categoria que el
    usuario no ha consumido.

    La popularidad se mide como el numero de reviews del articulo
    dentro de esa categoria (a traves de REVIEW_CATEGORIA).

    Se excluyen los articulos que el usuario ya ha puntuado,
    independientemente de la categoria en la que los puntuo.
    """
    cursor = conexion.cursor()
    sql = """
    SELECT a.asin, COUNT(*) AS numero_reviews
    FROM REVIEW r
    INNER JOIN REVIEW_CATEGORIA rc ON r.id_review = rc.id_review
    INNER JOIN CATEGORIA c ON rc.id_categoria = c.id_categoria
    INNER JOIN ARTICULO a ON r.id_articulo = a.id_articulo
    WHERE c.nombre_categoria = %s
      AND r.id_articulo NOT IN (
          SELECT id_articulo
          FROM REVIEW
          WHERE id_usuario = %s
      )
    GROUP BY a.id_articulo, a.asin
    ORDER BY numero_reviews DESC
    LIMIT %s;
    """
    cursor.execute(sql, [categoria, id_usuario, limite])
    resultado = cursor.fetchall()
    cursor.close()
    return resultado


# ============================================================
# FUNCIONES DE ENTRADA
# ============================================================


def pedir_reviewer_id(conexion):
    """
    Pide el reviewerID al usuario y lo valida contra la base de datos.
    Devuelve una tupla (reviewer_id, id_usuario).
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
    Pide la categoria al usuario y la valida contra la base de datos.
    Muestra las categorias disponibles antes de pedir la seleccion.
    """
    categorias = obtener_categorias(conexion)

    print()
    print("Categorias disponibles:")
    i = 0
    while i < len(categorias):
        print("  - " + categorias[i])
        i = i + 1
    print()

    categoria = None

    while categoria is None:
        opcion = input("Introduce la categoria: ").strip()

        if opcion == "":
            print("Debes introducir una categoria.")
        else:
            if opcion in categorias:
                categoria = opcion
            else:
                print("Esa categoria no existe.")

    return categoria


# ============================================================
# FUNCION DE RECOMENDACION
# ============================================================


def recomendar(conexion):
    """
    Ejecuta el flujo completo de recomendacion:
    1. Pide el reviewerID del usuario
    2. Pide la categoria
    3. Consulta los articulos mas populares no consumidos
    4. Muestra los resultados
    """
    reviewer_id, id_usuario = pedir_reviewer_id(conexion)
    categoria = pedir_categoria(conexion)

    print()
    print("Buscando recomendaciones para el usuario " + reviewer_id
          + " en la categoria " + categoria + "...")
    print()

    resultados = consulta_recomendaciones(
        conexion, id_usuario, categoria, NUM_RECOMENDACIONES
    )

    if len(resultados) == 0:
        print("No se han encontrado articulos para recomendar.")
        print("Es posible que el usuario ya haya consumido todos los")
        print("articulos de esta categoria.")
        return

    print("Los " + str(len(resultados)) + " articulos mas populares de "
          + categoria + " que el usuario no ha consumido:")
    print()
    print("  {:>4}   {:<15}  {}".format("#", "ASIN", "Num. reviews"))
    print("  " + "-" * 40)

    i = 0
    while i < len(resultados):
        asin = resultados[i][0]
        numero_reviews = resultados[i][1]
        print("  {:>4}   {:<15}  {}".format(i + 1, asin, numero_reviews))
        i = i + 1


# ============================================================
# MENU
# ============================================================


def imprimir_menu():
    """
    Muestra el menu principal.
    """
    print()
    print("============================================================")
    print("SISTEMA DE RECOMENDACION")
    print("============================================================")
    print("1. Obtener recomendaciones para un usuario")
    print("0. Salir")


def ejecutar_menu(conexion):
    """
    Ejecuta el bucle principal del menu.
    """
    seguir = True

    while seguir is True:
        imprimir_menu()
        opcion = input("Selecciona una opcion: ").strip()

        try:
            if opcion == "1":
                recomendar(conexion)
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
