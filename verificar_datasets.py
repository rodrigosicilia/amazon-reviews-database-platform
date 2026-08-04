# ============================================================
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodriguez
# ============================================================

"""
verificar_datasets.py

Script auxiliar de la primera parte del proyecto de Bases de Datos.
Recorre los cuatro ficheros JSON linea a linea (sin cargarlos en
memoria) y realiza las comprobaciones empiricas que se describen
en la seccion 1.3 del informe:

1. reviewerName: detecta reviewerID con varios nombres distintos
   y reviewerID que aparecen con nombre vacio y no vacio.

2. Reviews duplicadas: identifica tripletas (reviewerID, asin,
   unixReviewTime) que se repiten, diferenciando entre duplicados
   exactos y conflictivos (distinto contenido).

3. Reviews en varios ficheros: detecta reviews que aparecen en
   mas de un dataset, para justificar la tabla REVIEW_CATEGORIA.

4. reviewTime y unixReviewTime: comprueba que ambos campos son
   validos y que son coherentes entre si.

5. helpful: valida que sea una lista de dos enteros no negativos
   con helpful[0] <= helpful[1].

Los resultados se muestran por pantalla y se exportan a CSV
para facilitar su revision.
"""

import json
import csv
import hashlib
from datetime import datetime

from configuracion import DATASETS


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================


def normalizar_texto(valor):
    """
    Convierte un valor a texto limpio. Si es None, devuelve cadena vacia.
    """
    if valor is None:
        return ""
    return str(valor).strip()


def hash_review(review):
    """
    Genera un hash SHA1 del contenido completo de una review.
    Permite comparar si dos ocurrencias son identicas o no.
    """
    texto = json.dumps(review, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()


def guardar_csv(nombre_fichero, cabecera, filas):
    """
    Escribe una lista de filas en un fichero CSV.
    """
    with open(nombre_fichero, "w", newline="", encoding="utf-8") as fichero:
        writer = csv.writer(fichero)
        writer.writerow(cabecera)

        i = 0
        while i < len(filas):
            writer.writerow(filas[i])
            i = i + 1


def unir_con_separador(lista):
    """
    Une los elementos de una lista en un texto separado por ' | '.
    """
    texto = ""
    i = 0
    while i < len(lista):
        texto = texto + str(lista[i])
        if i < len(lista) - 1:
            texto = texto + " | "
        i = i + 1
    return texto


# ============================================================
# LECTURA DE LOS DATASETS
# ============================================================


def leer_todos_los_datasets():
    """
    Lee todos los ficheros JSON linea a linea y devuelve la
    informacion necesaria para las comprobaciones posteriores.

    Devuelve un diccionario con todas las estructuras de datos
    recopiladas durante la lectura.
    """
    total_reviews = 0

    # Para comprobar reviewerName
    nombres_por_reviewer = {}
    estado_nombre_por_reviewer = {}

    # Para comprobar tripletas y duplicados
    tripletas = {}

    # Para comprobar reviews en varios ficheros
    ficheros_por_clave = {}

    # Para comprobar articulos multicategoria
    categorias_por_asin = {}

    # Problemas detectados
    reviewtime_invalido = []
    reviewtime_inconsistente = []
    helpful_invalido = []
    campos_clave_invalidos = []

    for nombre_categoria, ruta_fichero in DATASETS:
        print("Leyendo: " + ruta_fichero + " (" + nombre_categoria + ")")

        with open(ruta_fichero, "r", encoding="utf-8") as fichero:
            numero_linea = 0

            for linea in fichero:
                numero_linea = numero_linea + 1

                if linea.strip() == "":
                    continue

                review = json.loads(linea)
                total_reviews = total_reviews + 1

                reviewer_id = normalizar_texto(review.get("reviewerID"))
                reviewer_name = normalizar_texto(review.get("reviewerName"))
                asin = normalizar_texto(review.get("asin"))
                unix_review_time = review.get("unixReviewTime")
                review_time_texto = normalizar_texto(review.get("reviewTime"))
                helpful = review.get("helpful")
                unix_texto = normalizar_texto(unix_review_time)

                # --- reviewerName ---
                if reviewer_id != "":
                    if reviewer_id not in nombres_por_reviewer:
                        nombres_por_reviewer[reviewer_id] = set()
                        estado_nombre_por_reviewer[reviewer_id] = {
                            "tiene_vacio": False,
                            "tiene_no_vacio": False
                        }

                    if reviewer_name == "":
                        estado_nombre_por_reviewer[reviewer_id]["tiene_vacio"] = True
                    else:
                        estado_nombre_por_reviewer[reviewer_id]["tiene_no_vacio"] = True
                        nombres_por_reviewer[reviewer_id].add(reviewer_name)

                # --- Articulos multicategoria ---
                if asin != "":
                    if asin not in categorias_por_asin:
                        categorias_por_asin[asin] = set()
                    categorias_por_asin[asin].add(nombre_categoria)

                # --- Campos clave ---
                if reviewer_id == "" or asin == "" or unix_texto == "":
                    campos_clave_invalidos.append([
                        nombre_categoria, numero_linea,
                        reviewer_id, asin, unix_texto,
                        "Falta reviewerID, asin o unixReviewTime"
                    ])
                    continue

                clave = (reviewer_id, asin, unix_texto)
                hash_actual = hash_review(review)

                # --- Tripletas duplicadas ---
                if clave not in tripletas:
                    tripletas[clave] = {
                        "conteo": 1,
                        "hash_primero": hash_actual,
                        "hay_variacion": False,
                        "primera_categoria": nombre_categoria,
                        "primera_linea": numero_linea
                    }
                else:
                    tripletas[clave]["conteo"] = tripletas[clave]["conteo"] + 1
                    if tripletas[clave]["hash_primero"] != hash_actual:
                        tripletas[clave]["hay_variacion"] = True

                # --- Reviews en varios ficheros ---
                if clave not in ficheros_por_clave:
                    ficheros_por_clave[clave] = {
                        "categorias": [],
                        "hashes": []
                    }
                ficheros_por_clave[clave]["categorias"].append(nombre_categoria)
                ficheros_por_clave[clave]["hashes"].append(hash_actual)

                # --- reviewTime ---
                comprobar_reviewtime(
                    review_time_texto, unix_review_time, unix_texto,
                    nombre_categoria, numero_linea, reviewer_id, asin,
                    reviewtime_invalido, reviewtime_inconsistente
                )

                # --- helpful ---
                motivo = validar_helpful(helpful)
                if motivo != "":
                    helpful_invalido.append([
                        nombre_categoria, numero_linea,
                        reviewer_id, asin, str(helpful), motivo
                    ])

    return {
        "total_reviews": total_reviews,
        "nombres_por_reviewer": nombres_por_reviewer,
        "estado_nombre_por_reviewer": estado_nombre_por_reviewer,
        "tripletas": tripletas,
        "ficheros_por_clave": ficheros_por_clave,
        "categorias_por_asin": categorias_por_asin,
        "reviewtime_invalido": reviewtime_invalido,
        "reviewtime_inconsistente": reviewtime_inconsistente,
        "helpful_invalido": helpful_invalido,
        "campos_clave_invalidos": campos_clave_invalidos
    }


# ============================================================
# COMPROBACIONES INDIVIDUALES
# ============================================================


def validar_helpful(helpful):
    """
    Comprueba que el campo helpful sea una lista de dos enteros
    no negativos con helpful[0] <= helpful[1].
    Devuelve cadena vacia si es valido, o el motivo del error.
    """
    if helpful is None:
        return "helpful nulo"
    if type(helpful) is not list:
        return "helpful no es una lista"
    if len(helpful) != 2:
        return "helpful no tiene longitud 2"
    if type(helpful[0]) is not int or type(helpful[1]) is not int:
        return "helpful no contiene dos enteros"
    if helpful[0] < 0 or helpful[1] < 0:
        return "helpful tiene valores negativos"
    if helpful[0] > helpful[1]:
        return "helpful[0] es mayor que helpful[1]"
    return ""


def comprobar_reviewtime(review_time_texto, unix_review_time, unix_texto,
                         nombre_categoria, numero_linea, reviewer_id, asin,
                         lista_invalido, lista_inconsistente):
    """
    Valida reviewTime y su coherencia con unixReviewTime.
    Anade los problemas encontrados a las listas correspondientes.
    """
    fila_base = [nombre_categoria, numero_linea, reviewer_id, asin,
                 review_time_texto, unix_texto]

    if review_time_texto == "":
        lista_invalido.append(fila_base + ["reviewTime vacio o nulo"])
        return

    try:
        fecha_review_time = datetime.strptime(
            review_time_texto, "%m %d, %Y"
        ).date()
    except ValueError:
        lista_invalido.append(fila_base + ["Formato invalido en reviewTime"])
        return

    if unix_texto == "":
        lista_invalido.append(fila_base + ["unixReviewTime vacio o nulo"])
        return

    try:
        fecha_unix = datetime.utcfromtimestamp(int(unix_review_time)).date()
        if fecha_review_time != fecha_unix:
            lista_inconsistente.append(
                fila_base + [str(fecha_review_time), str(fecha_unix)]
            )
    except (ValueError, OverflowError, OSError):
        lista_invalido.append(fila_base + ["unixReviewTime no convertible"])


# ============================================================
# ANALISIS DE RESULTADOS
# ============================================================


def analizar_reviewer_names(nombres_por_reviewer, estado_nombre_por_reviewer):
    """
    Detecta reviewerID con varios nombres distintos y reviewerID
    que aparecen con nombre vacio y no vacio.
    """
    varios_nombres = []
    vacio_y_no_vacio = []

    for reviewer_id in nombres_por_reviewer:
        nombres = list(nombres_por_reviewer[reviewer_id])
        nombres.sort()

        if len(nombres) > 1:
            varios_nombres.append([
                reviewer_id, len(nombres), unir_con_separador(nombres)
            ])

    for reviewer_id in estado_nombre_por_reviewer:
        estado = estado_nombre_por_reviewer[reviewer_id]
        if estado["tiene_vacio"] and estado["tiene_no_vacio"]:
            nombres = list(nombres_por_reviewer[reviewer_id])
            nombres.sort()
            vacio_y_no_vacio.append([
                reviewer_id, unir_con_separador(nombres)
            ])

    varios_nombres.sort()
    vacio_y_no_vacio.sort()
    return varios_nombres, vacio_y_no_vacio


def analizar_tripletas_duplicadas(tripletas):
    """
    Extrae las tripletas que aparecen mas de una vez.
    """
    duplicadas = []

    for clave in tripletas:
        info = tripletas[clave]
        if info["conteo"] > 1:
            tipo = "duplicado exacto"
            if info["hay_variacion"]:
                tipo = "duplicado conflictivo"

            duplicadas.append([
                clave[0], clave[1], clave[2],
                info["conteo"], tipo,
                info["primera_categoria"], info["primera_linea"]
            ])

    duplicadas.sort()
    return duplicadas


def analizar_reviews_varios_ficheros(ficheros_por_clave):
    """
    Detecta reviews que aparecen en mas de un dataset distinto.
    """
    repetidas = []

    for clave in ficheros_por_clave:
        info = ficheros_por_clave[clave]

        # Obtener categorias unicas
        categorias_unicas = []
        i = 0
        while i < len(info["categorias"]):
            cat = info["categorias"][i]
            if cat not in categorias_unicas:
                categorias_unicas.append(cat)
            i = i + 1

        if len(categorias_unicas) < 2:
            continue

        # Comprobar si son exactas o conflictivas
        hashes_unicos = []
        i = 0
        while i < len(info["hashes"]):
            h = info["hashes"][i]
            if h not in hashes_unicos:
                hashes_unicos.append(h)
            i = i + 1

        tipo = "exacta"
        if len(hashes_unicos) > 1:
            tipo = "conflictiva"

        repetidas.append([
            clave[0], clave[1], clave[2],
            len(categorias_unicas), tipo,
            unir_con_separador(categorias_unicas)
        ])

    repetidas.sort()
    return repetidas


def analizar_articulos_multicategoria(categorias_por_asin):
    """
    Detecta articulos (ASIN) que aparecen en mas de una categoria.
    Justifica que la relacion ARTICULO-CATEGORIA no puede ser 1:N.
    """
    multicategoria = []

    for asin in categorias_por_asin:
        categorias = list(categorias_por_asin[asin])
        categorias.sort()

        if len(categorias) > 1:
            multicategoria.append([
                asin, len(categorias), unir_con_separador(categorias)
            ])

    multicategoria.sort()
    return multicategoria


# ============================================================
# MOSTRAR Y EXPORTAR RESULTADOS
# ============================================================


def mostrar_y_exportar(datos):
    """
    Muestra el resumen por pantalla y genera los CSV de apoyo.
    """
    varios_nombres, vacio_y_no_vacio = analizar_reviewer_names(
        datos["nombres_por_reviewer"],
        datos["estado_nombre_por_reviewer"]
    )
    duplicadas = analizar_tripletas_duplicadas(datos["tripletas"])
    en_varios_ficheros = analizar_reviews_varios_ficheros(
        datos["ficheros_por_clave"]
    )
    multicategoria = analizar_articulos_multicategoria(
        datos["categorias_por_asin"]
    )

    # Contar exactas y conflictivas entre ficheros
    exactas = 0
    conflictivas = 0
    i = 0
    while i < len(en_varios_ficheros):
        if en_varios_ficheros[i][4] == "exacta":
            exactas = exactas + 1
        else:
            conflictivas = conflictivas + 1
        i = i + 1

    # --- Resumen por pantalla ---
    print()
    print("============================================================")
    print("RESUMEN DE COMPROBACIONES")
    print("============================================================")
    print()
    print("Total de reviews leidas: " + str(datos["total_reviews"]))
    print()

    print("--- Articulos multicategoria ---")
    print("ASIN distintos totales: " + str(len(datos["categorias_por_asin"])))
    print("ASIN en varias categorias: " + str(len(multicategoria)))
    print()

    print("--- reviewerName ---")
    print("reviewerID con varios nombres distintos: "
          + str(len(varios_nombres)))
    print("reviewerID con nombre vacio y no vacio:  "
          + str(len(vacio_y_no_vacio)))
    print()

    print("--- Reviews duplicadas (tripleta) ---")
    print("Tripletas repetidas: " + str(len(duplicadas)))
    print()

    print("--- Reviews en varios ficheros ---")
    print("Reviews en mas de un dataset: " + str(len(en_varios_ficheros)))
    print("  Exactas (mismo contenido):   " + str(exactas))
    print("  Conflictivas (distinto):     " + str(conflictivas))
    print()

    print("--- reviewTime ---")
    print("reviewTime invalido:       " + str(len(datos["reviewtime_invalido"])))
    print("reviewTime inconsistente:  "
          + str(len(datos["reviewtime_inconsistente"])))
    print()

    print("--- helpful ---")
    print("helpful invalido: " + str(len(datos["helpful_invalido"])))
    print()

    print("--- Campos clave ---")
    print("Campos clave invalidos: " + str(len(datos["campos_clave_invalidos"])))
    print()

    # --- Exportar CSV ---
    ficheros_generados = []

    if len(multicategoria) > 0:
        guardar_csv(
            "articulos_multicategoria.csv",
            ["asin", "numero_categorias", "categorias"],
            multicategoria
        )
        ficheros_generados.append("articulos_multicategoria.csv")

    if len(varios_nombres) > 0:
        guardar_csv(
            "reviewer_varios_nombres.csv",
            ["reviewerID", "numero_nombres", "nombres"],
            varios_nombres
        )
        ficheros_generados.append("reviewer_varios_nombres.csv")

    if len(vacio_y_no_vacio) > 0:
        guardar_csv(
            "reviewer_nombre_vacio_y_no_vacio.csv",
            ["reviewerID", "nombres_no_vacios"],
            vacio_y_no_vacio
        )
        ficheros_generados.append("reviewer_nombre_vacio_y_no_vacio.csv")

    if len(duplicadas) > 0:
        guardar_csv(
            "reviews_duplicadas.csv",
            ["reviewerID", "asin", "unixReviewTime",
             "apariciones", "tipo", "primera_categoria", "primera_linea"],
            duplicadas
        )
        ficheros_generados.append("reviews_duplicadas.csv")

    if len(en_varios_ficheros) > 0:
        guardar_csv(
            "reviews_en_varios_ficheros.csv",
            ["reviewerID", "asin", "unixReviewTime",
             "num_categorias", "tipo", "categorias"],
            en_varios_ficheros
        )
        ficheros_generados.append("reviews_en_varios_ficheros.csv")

    if len(datos["reviewtime_invalido"]) > 0:
        guardar_csv(
            "reviewtime_invalido.csv",
            ["categoria", "linea", "reviewerID", "asin",
             "reviewTime", "unixReviewTime", "motivo"],
            datos["reviewtime_invalido"]
        )
        ficheros_generados.append("reviewtime_invalido.csv")

    if len(datos["reviewtime_inconsistente"]) > 0:
        guardar_csv(
            "reviewtime_inconsistente.csv",
            ["categoria", "linea", "reviewerID", "asin",
             "reviewTime", "unixReviewTime",
             "fecha_reviewTime", "fecha_unixReviewTime"],
            datos["reviewtime_inconsistente"]
        )
        ficheros_generados.append("reviewtime_inconsistente.csv")

    if len(datos["helpful_invalido"]) > 0:
        guardar_csv(
            "helpful_invalido.csv",
            ["categoria", "linea", "reviewerID", "asin",
             "helpful", "motivo"],
            datos["helpful_invalido"]
        )
        ficheros_generados.append("helpful_invalido.csv")

    if len(datos["campos_clave_invalidos"]) > 0:
        guardar_csv(
            "campos_clave_invalidos.csv",
            ["categoria", "linea", "reviewerID", "asin",
             "unixReviewTime", "motivo"],
            datos["campos_clave_invalidos"]
        )
        ficheros_generados.append("campos_clave_invalidos.csv")

    # Mostrar ficheros generados
    if len(ficheros_generados) > 0:
        print("Ficheros CSV generados:")
        i = 0
        while i < len(ficheros_generados):
            print("  - " + ficheros_generados[i])
            i = i + 1
    else:
        print("No se ha generado ningun CSV (sin incidencias).")

    print()
    print("Comprobacion terminada.")


# ============================================================
# MAIN
# ============================================================


def main():
    """
    Funcion principal. Lee los datasets y ejecuta todas las
    comprobaciones.
    """
    datos = leer_todos_los_datasets()
    mostrar_y_exportar(datos)


if __name__ == "__main__":
    main()
