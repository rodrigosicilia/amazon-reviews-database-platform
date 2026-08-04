# Amazon Reviews Data Platform

Hybrid database project for storing, analysing, visualising and recommending products from Amazon review data. The system combines **MySQL**, **MongoDB** and **Neo4j**, with all database creation, loading, querying and graph generation implemented in Python.

This project was developed by **Rodrigo Alejandro Sicilia Maroto** and **Claudia Moya Rodríguez** as the final project for the Databases course in the second year of the Mathematical Engineering and Artificial Intelligence degree at ICAI – Universidad Pontificia Comillas (2025/2026).

## Project overview

The project works with four Amazon 5-core review datasets:

- Toys and Games — 167,597 reviews
- Video Games — 231,780 reviews
- Digital Music — 64,706 reviews
- Musical Instruments — 10,261 reviews

The original data is split between two database systems according to its structure:

- **MySQL** stores users, products, categories and the structured part of each review.
- **MongoDB** stores the textual and flexible fields of each review, including the review text, summary and helpfulness information.
- **Neo4j** is used to build and explore several graph representations involving users, products, categories and user similarity.

The relational design preserves the source category of each review through the `REVIEW_CATEGORIA` table. This is necessary because the same product, and even the same logical review, may appear in more than one source dataset.

## Main features

### Data validation and loading

- Processes the JSON files line by line instead of loading them fully into memory.
- Creates the MySQL database, tables, keys and constraints from Python.
- Creates and populates the MongoDB collection from Python.
- Detects duplicate reviews and preserves their source categories.
- Validates assumptions about duplicated reviews, multicategory products and reviewer names.
- Supports incremental insertion of an additional review dataset.

### Data visualisation

The project provides seven visual analyses:

1. Number of reviews by year.
2. Product popularity distribution.
3. Rating histogram.
4. Cumulative review evolution over time.
5. Number of reviews per user.
6. Word cloud by product category.
7. Average rating by category.

The visualisations are available through both:

- A terminal menu in `menu_visualizacion.py`.
- An interactive Tkinter dashboard in `dashboard.py`.

### Neo4j graph analysis

`neo4JProyecto.py` implements four graph-based analyses:

- Pearson similarity between the most active users.
- User-product relationships for randomly selected products.
- Relationships between users and the different product categories they reviewed.
- Popular products, their reviewers and the number of products reviewed in common by each pair of users.

### Recommendation systems

Two recommendation approaches are included:

- `recomendacion.py`: recommends the ten most popular products in a category that a user has not previously reviewed.
- `modelo_ml.py`: implements user-based collaborative filtering with Pearson correlation, rating prediction and model evaluation using MAE.

## Repository structure

```text
.
├── configuracion.py           # Database credentials, database names and dataset paths
├── load_data.py               # Creates and loads the MySQL and MongoDB infrastructure
├── verificar_datasets.py      # Validates assumptions about the source datasets
├── menu_visualizacion.py      # Terminal-based visualisation menu
├── dashboard.py               # Tkinter graphical dashboard
├── neo4JProyecto.py           # Neo4j graph generation and analysis
├── recomendacion.py           # Popularity-based recommender
├── modelo_ml.py               # Collaborative-filtering recommender
├── inserta_dataset.py         # Inserts an additional product category
├── requirements.txt           # Third-party Python dependencies
├── Informe_Proyecto_BD.pdf    # Full technical report
└── Poster_Proyecto_BD.pdf     # Project poster
```

## Requirements

The project requires:

- Python 3.9 or newer
- MySQL Server
- MongoDB Community Server
- Neo4j Desktop or Neo4j Server

Install the Python dependencies with:

```bash
python -m pip install -r requirements.txt
```

The supplied `requirements.txt` installs:

- PyMySQL
- PyMongo
- Neo4j Python Driver
- Matplotlib
- WordCloud

Tkinter is part of the standard Python distribution on Windows. On some Linux distributions it may need to be installed separately.

## Dataset setup

The raw datasets are **not included in this repository**. Download the corresponding Amazon 5-core review files and place them in the repository root, alongside the Python scripts:

```text
Toys_and_Games_5.json
Video_Games_5.json
Digital_Music_5.json
Musical_Instruments_5.json
```

The optional incremental-loading script also expects:

```text
Office_Products_5.json
```

The data source used for the project is the Amazon Product Data collection maintained by Julian McAuley at UCSD:

<https://jmcauley.ucsd.edu/data/amazon/index_2014.html>

Do not rename the files unless the corresponding paths are also updated in `configuracion.py` or `inserta_dataset.py`.

## Configuration

Before running the project, open `configuracion.py` and set the local connection parameters for MySQL, MongoDB and Neo4j:

```python
MYSQL_HOST = "localhost"
MYSQL_USER = "your_mysql_user"
MYSQL_PASSWORD = "your_mysql_password"

MONGO_HOST = "localhost"
MONGO_PORT = 27017

NEO4J_HOST = "localhost"
NEO4J_PORT = 7687
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your_neo4j_password"
```

The database servers must be running before executing the scripts. Run all commands from the repository root because the project uses relative paths for the JSON files.

> **Security note:** do not publish real database passwords. Keep the repository private or replace local credentials with non-sensitive placeholder values before making it public.

## Execution

### 1. Optional dataset validation

The validation script examines the source files line by line and checks the assumptions used in the database design:

```bash
python verificar_datasets.py
```

### 2. Create and load the databases

```bash
python load_data.py
```

> **Warning:** this script recreates the project tables in MySQL and clears the MongoDB review collection before loading the data again. Do not point it at databases containing information that must be preserved.

### 3. Run the visualisation menu

```bash
python menu_visualizacion.py
```

### 4. Run the graphical dashboard

```bash
python dashboard.py
```

### 5. Run the Neo4j analysis

```bash
python neo4JProyecto.py
```

Some Neo4j menu options clear the existing graph before loading a new representation. Use a dedicated project database if the existing Neo4j data must be preserved.

### 6. Run the popularity-based recommender

```bash
python recomendacion.py
```

### 7. Run the collaborative-filtering model

```bash
python modelo_ml.py
```

### 8. Insert the additional dataset

After placing `Office_Products_5.json` in the repository root:

```bash
python inserta_dataset.py
```

## Database design

The main MySQL tables are:

- `USUARIO`: unique reviewers.
- `ARTICULO`: unique products identified by ASIN.
- `CATEGORIA`: source product categories.
- `REVIEW`: structured review information and links to users and products.
- `REVIEW_CATEGORIA`: many-to-many relationship that records every source category in which a review appeared.

The MongoDB collection stores the document-oriented portion of each review and uses the MySQL review identifier to connect both representations.

## Authors and contributions

### Rodrigo Alejandro Sicilia Maroto

- Designed and implemented the MySQL data model and backend.
- Analysed the source JSON files to validate the design assumptions.
- Developed `load_data.py`, `configuracion.py`, `neo4JProyecto.py` and `inserta_dataset.py`.
- Implemented the popularity-based recommendation mechanism.

### Claudia Moya Rodríguez

- Developed the seven visualisation functions and the complete terminal menu in `menu_visualizacion.py`.
- Produced the Power BI visualisations.
- Led the writing and documentation of the technical report.
- Participated in the validation and documentation of the database design.

### Joint work

- Key design decisions, including the use of `REVIEW_CATEGORIA`.
- Code review, correction and integration.
- Optional components, conclusions and final delivery preparation.

## Documentation

The repository includes two additional documents:

- [Full project report](Informe_Proyecto_BD.pdf)
- [Project poster](Poster_Proyecto_BD.pdf)

The report contains the complete design justification, database diagrams, implementation decisions, screenshots, results and discussion.

## Limitations

- The project depends on three external database servers and is not a single-command deployment.
- Connection settings and dataset paths must be configured manually.
- The raw datasets are not distributed with the repository.
- The collaborative-filtering model is affected by the sparsity of the user-product matrix.
- The implementation was developed as an academic project and is not intended as a production service.

## Academic use

This repository is provided as an academic portfolio project. The source datasets belong to their respective authors and distributors. The code and accompanying documents were produced jointly by Rodrigo Alejandro Sicilia Maroto and Claudia Moya Rodríguez.
