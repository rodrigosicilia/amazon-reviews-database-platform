# ============================================================
# NOMBRES COMPLETOS DE LOS ESTUDIANTES:
# - Rodrigo Alejandro Sicilia Maroto
# - Claudia Moya Rodriguez
# ============================================================

"""
dashboard.py

Opcional 8 del proyecto de Bases de Datos.
Interfaz grafica interactiva para las visualizaciones de la
segunda parte del proyecto, como alternativa al menu por terminal
de menu_visualizacion.py.

Se utiliza Tkinter para la interfaz y matplotlib para las graficas,
ambas librerias ya disponibles en el entorno del proyecto.

Las funciones de consulta SQL y MongoDB se importan directamente
de menu_visualizacion.py, sin duplicar codigo ni modificar el
fichero original.
"""

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from wordcloud import WordCloud

# Importar las funciones de consulta de menu_visualizacion.py
# (no se modifica nada del fichero original)
from menu_visualizacion import (
    get_conexion_mysql,
    get_client_mongo,
    get_database_mongo,
    get_collection_mongo,
    obtener_categorias,
    consulta_reviews_por_anio,
    consulta_popularidad_articulos,
    consulta_histograma_por_nota_todo,
    consulta_histograma_por_nota_categoria,
    consulta_histograma_por_nota_articulo,
    consulta_reviews_tiempo_global,
    consulta_reviews_tiempo_categorias,
    consulta_reviews_por_usuario,
    consulta_media_nota_por_categoria,
    consulta_ids_reviews_categoria,
    obtener_frecuencias_palabras,
    articulo_existe
)


# ============================================================
# CLASE PRINCIPAL DEL DASHBOARD
# ============================================================


class Dashboard:
    """
    Ventana principal del dashboard interactivo.
    Contiene un panel izquierdo con los controles (seleccion de
    grafica, categoria, etc.) y un panel derecho donde se dibuja
    la grafica de matplotlib.
    """

    def __init__(self, root):
        """
        Inicializa la ventana, las conexiones y los widgets.
        """
        self.root = root
        self.root.title("Dashboard de Visualizacion - Proyecto BBDD")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)

        # Conexiones
        self.conexion_mysql = get_conexion_mysql()
        self.client_mongo = get_client_mongo()
        self.db_mongo = get_database_mongo(self.client_mongo)
        self.collection_mongo = get_collection_mongo(self.db_mongo)

        # Obtener categorias de la base de datos
        self.categorias = obtener_categorias(self.conexion_mysql)

        # Crear la interfaz
        self.crear_interfaz()

        # Canvas actual de matplotlib (para poder limpiarlo)
        self.canvas_actual = None

    def crear_interfaz(self):
        """
        Construye todos los widgets de la ventana.
        """
        # ----- Panel izquierdo (controles) -----
        panel_izquierdo = tk.Frame(self.root, width=300, padx=15, pady=15)
        panel_izquierdo.pack(side=tk.LEFT, fill=tk.Y)
        panel_izquierdo.pack_propagate(False)

        titulo = tk.Label(
            panel_izquierdo,
            text="Dashboard de\nVisualizacion",
            font=("Arial", 16, "bold"),
            justify=tk.CENTER
        )
        titulo.pack(pady=(0, 20))

        # Selector de grafica
        tk.Label(
            panel_izquierdo,
            text="Selecciona la grafica:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)

        self.opciones_graficas = [
            "1. Reviews por anio",
            "2. Popularidad de articulos",
            "3. Histograma por nota",
            "4. Evolucion temporal",
            "5. Reviews por usuario",
            "6. Nube de palabras",
            "7. Media de nota por categoria"
        ]

        self.combo_grafica = ttk.Combobox(
            panel_izquierdo,
            values=self.opciones_graficas,
            state="readonly",
            width=32
        )
        self.combo_grafica.current(0)
        self.combo_grafica.pack(pady=(5, 15))
        self.combo_grafica.bind("<<ComboboxSelected>>", self.al_cambiar_grafica)

        # Selector de categoria
        tk.Label(
            panel_izquierdo,
            text="Categoria:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)

        opciones_categoria = ["Todo"] + self.categorias
        self.combo_categoria = ttk.Combobox(
            panel_izquierdo,
            values=opciones_categoria,
            state="readonly",
            width=32
        )
        self.combo_categoria.current(0)
        self.combo_categoria.pack(pady=(5, 15))

        # Campo ASIN (solo para histograma por nota de articulo)
        self.frame_asin = tk.Frame(panel_izquierdo)
        self.frame_asin.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            self.frame_asin,
            text="ASIN del articulo (opcional):",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)

        self.entry_asin = tk.Entry(self.frame_asin, width=34)
        self.entry_asin.pack(pady=(5, 0))

        # Selector de modo para evolucion temporal
        self.frame_modo_tiempo = tk.Frame(panel_izquierdo)
        self.frame_modo_tiempo.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            self.frame_modo_tiempo,
            text="Modo evolucion temporal:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W)

        self.modos_tiempo = [
            "Todas juntas (global)",
            "Todas separadas por categoria"
        ]
        self.combo_modo_tiempo = ttk.Combobox(
            self.frame_modo_tiempo,
            values=self.modos_tiempo,
            state="readonly",
            width=32
        )
        self.combo_modo_tiempo.current(0)
        self.combo_modo_tiempo.pack(pady=(5, 0))

        # Boton de generar
        self.boton_generar = tk.Button(
            panel_izquierdo,
            text="Generar grafica",
            font=("Arial", 12, "bold"),
            bg="#4285f4",
            fg="white",
            activebackground="#3367d6",
            activeforeground="white",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.generar_grafica
        )
        self.boton_generar.pack(pady=(10, 15))

        # Etiqueta de estado
        self.label_estado = tk.Label(
            panel_izquierdo,
            text="Listo.",
            font=("Arial", 9),
            fg="gray",
            wraplength=260,
            justify=tk.LEFT
        )
        self.label_estado.pack(anchor=tk.W, pady=(10, 0))

        # ----- Panel derecho (grafica) -----
        self.panel_grafica = tk.Frame(self.root, bg="white")
        self.panel_grafica.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Mostrar controles adecuados al inicio
        self.al_cambiar_grafica(None)

    def al_cambiar_grafica(self, evento):
        """
        Muestra u oculta controles segun la grafica seleccionada.
        """
        indice = self.combo_grafica.current()

        # El campo ASIN solo se muestra para histograma por nota (opcion 3)
        if indice == 2:
            self.frame_asin.pack(fill=tk.X, pady=(0, 15))
        else:
            self.frame_asin.pack_forget()

        # El modo temporal solo se muestra para evolucion temporal (opcion 4)
        if indice == 3:
            self.frame_modo_tiempo.pack(fill=tk.X, pady=(0, 15))
        else:
            self.frame_modo_tiempo.pack_forget()

        # La categoria no aplica para reviews por usuario (opcion 5)
        # ni para media de nota por categoria (opcion 7)
        if indice == 4 or indice == 6:
            self.combo_categoria.config(state="disabled")
        else:
            self.combo_categoria.config(state="readonly")

    def limpiar_grafica(self):
        """
        Elimina la grafica actual del panel derecho.
        """
        if self.canvas_actual is not None:
            self.canvas_actual.get_tk_widget().destroy()
            self.canvas_actual = None

    def dibujar_en_panel(self, fig):
        """
        Incrusta una figura de matplotlib en el panel derecho.
        """
        self.limpiar_grafica()
        canvas = FigureCanvasTkAgg(fig, master=self.panel_grafica)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas_actual = canvas

    def obtener_categoria_seleccionada(self):
        """
        Devuelve la categoria seleccionada en el combo.
        Si es 'Todo', devuelve None (convencion de las consultas).
        """
        valor = self.combo_categoria.get()
        if valor == "Todo":
            return None
        return valor

    def generar_grafica(self):
        """
        Lee la opcion seleccionada y genera la grafica correspondiente.
        """
        indice = self.combo_grafica.current()
        self.label_estado.config(text="Generando grafica...", fg="blue")
        self.root.update()

        try:
            if indice == 0:
                self.grafica_reviews_por_anio()
            elif indice == 1:
                self.grafica_popularidad()
            elif indice == 2:
                self.grafica_histograma_nota()
            elif indice == 3:
                self.grafica_evolucion_temporal()
            elif indice == 4:
                self.grafica_reviews_por_usuario()
            elif indice == 5:
                self.grafica_nube_palabras()
            elif indice == 6:
                self.grafica_media_nota_categoria()

            self.label_estado.config(text="Grafica generada.", fg="green")

        except Exception as error:
            self.label_estado.config(
                text="Error: " + str(error), fg="red"
            )

    # ============================================================
    # GRAFICAS INDIVIDUALES
    # ============================================================

    def grafica_reviews_por_anio(self):
        """
        Opcion 1: histograma de reviews por anio.
        """
        categoria = self.obtener_categoria_seleccionada()
        datos = consulta_reviews_por_anio(self.conexion_mysql, categoria)

        if len(datos) == 0:
            messagebox.showinfo("Sin datos", "No hay datos para esa seleccion.")
            return

        anios = []
        cantidades = []
        i = 0
        while i < len(datos):
            anios.append(str(datos[i][0]))
            cantidades.append(int(datos[i][1]))
            i = i + 1

        titulo = "Reviews por anio"
        if categoria is not None:
            titulo = titulo + " de " + categoria
        else:
            titulo = titulo + " de todos los productos"

        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        ax.bar(anios, cantidades, color="#4285f4")
        ax.set_title(titulo)
        ax.set_xlabel("Anios")
        ax.set_ylabel("Numero de reviews")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()

        self.dibujar_en_panel(fig)

    def grafica_popularidad(self):
        """
        Opcion 2: curva de popularidad de articulos.
        """
        categoria = self.obtener_categoria_seleccionada()
        datos = consulta_popularidad_articulos(self.conexion_mysql, categoria)

        if len(datos) == 0:
            messagebox.showinfo("Sin datos", "No hay datos para esa seleccion.")
            return

        posiciones = []
        cantidades = []
        i = 0
        while i < len(datos):
            posiciones.append(i + 1)
            cantidades.append(int(datos[i][1]))
            i = i + 1

        titulo = "Evolucion de la popularidad"
        if categoria is not None:
            titulo = titulo + " de " + categoria
        else:
            titulo = titulo + " de todos los productos"

        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        ax.plot(posiciones, cantidades, color="#4285f4", linewidth=1)
        ax.set_title(titulo)
        ax.set_xlabel("Articulos ordenados por popularidad")
        ax.set_ylabel("Numero de reviews")
        fig.tight_layout()

        self.dibujar_en_panel(fig)

    def grafica_histograma_nota(self):
        """
        Opcion 3: histograma por nota (todo, categoria o articulo).
        """
        asin = self.entry_asin.get().strip()

        if asin != "":
            # Modo articulo individual
            if articulo_existe(self.conexion_mysql, asin) is False:
                messagebox.showwarning(
                    "Articulo no encontrado",
                    "No existe ningun articulo con ASIN: " + asin
                )
                return
            datos = consulta_histograma_por_nota_articulo(
                self.conexion_mysql, asin
            )
            titulo = "Reviews por nota del articulo " + asin
        else:
            categoria = self.obtener_categoria_seleccionada()
            if categoria is None:
                datos = consulta_histograma_por_nota_todo(self.conexion_mysql)
                titulo = "Reviews por nota de todos los productos"
            else:
                datos = consulta_histograma_por_nota_categoria(
                    self.conexion_mysql, categoria
                )
                titulo = "Reviews por nota de " + categoria

        # Construir diccionario nota -> cantidad
        notas_dict = {}
        i = 0
        while i < len(datos):
            notas_dict[int(datos[i][0])] = int(datos[i][1])
            i = i + 1

        # Forzar las 5 notas (1 a 5) aunque alguna no aparezca
        notas = [1, 2, 3, 4, 5]
        cantidades = []
        i = 0
        while i < len(notas):
            if notas[i] in notas_dict:
                cantidades.append(notas_dict[notas[i]])
            else:
                cantidades.append(0)
            i = i + 1

        etiquetas = ["1", "2", "3", "4", "5"]

        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        ax.bar(etiquetas, cantidades, color="#4285f4")
        ax.set_title(titulo)
        ax.set_xlabel("Nota")
        ax.set_ylabel("Numero de reviews")
        fig.tight_layout()

        self.dibujar_en_panel(fig)

    def grafica_evolucion_temporal(self):
        """
        Opcion 4: evolucion acumulada de reviews a lo largo del tiempo.
        Dos modos: global o separado por categoria.
        """
        modo = self.combo_modo_tiempo.current()

        if modo == 0:
            # Todas juntas (global)
            datos = consulta_reviews_tiempo_global(self.conexion_mysql)

            if len(datos) == 0:
                messagebox.showinfo("Sin datos", "No hay datos disponibles.")
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

            fig = Figure(figsize=(8, 5))
            ax = fig.add_subplot(111)
            ax.plot(tiempos, valores, color="#4285f4", linewidth=1)
            ax.set_title("Evolucion de las reviews a lo largo del tiempo"
                         " (todas las categorias)")
            ax.set_xlabel("Tiempo")
            ax.set_ylabel("Numero de reviews hasta ese momento")
            fig.tight_layout()

        else:
            # Todas separadas por categoria
            datos = consulta_reviews_tiempo_categorias(self.conexion_mysql)

            if len(datos) == 0:
                messagebox.showinfo("Sin datos", "No hay datos disponibles.")
                return

            series_x = {}
            series_y = {}
            acumulados = {}

            i = 0
            while i < len(datos):
                cat = datos[i][0]
                if cat not in series_x:
                    series_x[cat] = []
                    series_y[cat] = []
                    acumulados[cat] = 0
                i = i + 1

            i = 0
            while i < len(datos):
                cat = datos[i][0]
                tiempo = datos[i][1]
                numero = int(datos[i][2])
                acumulados[cat] = acumulados[cat] + numero
                series_x[cat].append(tiempo)
                series_y[cat].append(acumulados[cat])
                i = i + 1

            fig = Figure(figsize=(8, 5))
            ax = fig.add_subplot(111)

            cats = list(series_x.keys())
            cats.sort()
            i = 0
            while i < len(cats):
                cat = cats[i]
                if len(series_x[cat]) > 0:
                    ax.plot(series_x[cat], series_y[cat], label=cat,
                            linewidth=1)
                i = i + 1

            ax.set_title("Evolucion de las reviews a lo largo del tiempo"
                         " por categoria")
            ax.set_xlabel("Tiempo")
            ax.set_ylabel("Numero de reviews hasta ese momento")
            ax.legend()
            fig.tight_layout()

        self.dibujar_en_panel(fig)

    def grafica_reviews_por_usuario(self):
        """
        Opcion 5: histograma de reviews por usuario.
        """
        datos = consulta_reviews_por_usuario(self.conexion_mysql)

        if len(datos) == 0:
            messagebox.showinfo("Sin datos", "No hay datos disponibles.")
            return

        num_reviews = []
        num_usuarios = []
        i = 0
        while i < len(datos):
            num_reviews.append(int(datos[i][0]))
            num_usuarios.append(int(datos[i][1]))
            i = i + 1

        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        ax.bar(num_reviews, num_usuarios, width=1, color="#4285f4",
               edgecolor="#4285f4")
        ax.set_title("Histograma de reviews por usuario")
        ax.set_xlabel("Numero de reviews")
        ax.set_ylabel("Numero de usuarios")
        fig.tight_layout()

        self.dibujar_en_panel(fig)

    def grafica_nube_palabras(self):
        """
        Opcion 6: nube de palabras por categoria.
        """
        categoria = self.obtener_categoria_seleccionada()

        if categoria is None:
            messagebox.showwarning(
                "Categoria requerida",
                "Para la nube de palabras es necesario"
                " seleccionar una categoria concreta."
            )
            return

        self.label_estado.config(
            text="Obteniendo reviews de " + categoria + "...", fg="blue"
        )
        self.root.update()

        ids = consulta_ids_reviews_categoria(self.conexion_mysql, categoria)

        if len(ids) == 0:
            messagebox.showinfo("Sin datos", "No hay reviews para esa categoria.")
            return

        self.label_estado.config(
            text="Calculando frecuencias de palabras...", fg="blue"
        )
        self.root.update()

        frecuencias = obtener_frecuencias_palabras(self.collection_mongo, ids)

        if len(frecuencias) == 0:
            messagebox.showinfo("Sin datos", "No se encontraron palabras.")
            return

        nube = WordCloud(
            width=800,
            height=400,
            background_color="white",
            collocations=False,
            max_words=200
        ).generate_from_frequencies(frecuencias)

        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        ax.imshow(nube, interpolation="bilinear")
        ax.set_title("Nube de palabras de summary para " + categoria)
        ax.axis("off")
        fig.tight_layout()

        self.dibujar_en_panel(fig)

    def grafica_media_nota_categoria(self):
        """
        Opcion 7: media de nota por categoria.
        """
        datos = consulta_media_nota_por_categoria(self.conexion_mysql)

        if len(datos) == 0:
            messagebox.showinfo("Sin datos", "No hay datos disponibles.")
            return

        categorias_nombre = []
        medias = []
        i = 0
        while i < len(datos):
            categorias_nombre.append(datos[i][0])
            medias.append(float(datos[i][1]))
            i = i + 1

        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        ax.bar(categorias_nombre, medias, color="#4285f4")
        ax.set_title("Media de nota por categoria")
        ax.set_xlabel("Categoria")
        ax.set_ylabel("Media de nota")
        ax.set_ylim(0, 5)
        ax.tick_params(axis="x", rotation=15)
        fig.tight_layout()

        self.dibujar_en_panel(fig)

    def cerrar(self):
        """
        Cierra las conexiones y la ventana.
        """
        try:
            if self.conexion_mysql is not None:
                self.conexion_mysql.close()
        except Exception:
            pass

        try:
            if self.client_mongo is not None:
                self.client_mongo.close()
        except Exception:
            pass

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================


def main():
    """
    Funcion principal. Crea la ventana y lanza el bucle de eventos.
    """
    root = tk.Tk()

    try:
        app = Dashboard(root)
        root.protocol("WM_DELETE_WINDOW", app.cerrar)
        root.mainloop()
    except Exception as error:
        messagebox.showerror(
            "Error",
            "No se ha podido iniciar el dashboard:\n" + str(error)
        )


if __name__ == "__main__":
    main()
