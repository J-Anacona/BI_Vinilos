# BI Vinilos: productividad, producción y paros de las líneas de envasado

Solución de Business Intelligence para una empresa fabricante de vinilos. Integra los registros históricos de producción y paros de cuatro líneas de envasado (`Vinilos_1` a `Vinilos_4`) en una base de datos PostgreSQL con modelo dimensional y los ofrece en dos capas de consumo:

- **Power BI**: análisis histórico y estratégico para la gerencia.
- **Grafana**: monitoreo operativo casi en tiempo real, con una alerta de productividad baja (`Máquina detenida`).

## 1. El problema

Las operarias registran a mano, hora a hora, la producción y los paros de cada máquina (procedimiento P-MTO-22). Mantenimiento transcribe esos formatos a un libro de Excel, del que salen los gráficos del informe mensual. Ese esquema solo permite análisis mensuales y predefinidos, y no avisa cuando una línea se desvía durante la operación. Esta solución carga esos datos en una base analítica y los publica en dos tableros, cada uno para un tipo de usuario y de decisión.

## 2. Arquitectura

```
Excel (.xlsm) ──> ETL en Python ──> PostgreSQL (BI_Vinilos) ──┬──> Power BI  (análisis histórico)
 + P-MTO-22        Data/etl          modelo dimensional         │
                                                                └──> Grafana   (monitoreo y alerta)
                                                                       ▲
              simulador.py ──> fact_lectura_hora ──────────────────────┘
```

| Capa | Componente |
|---|---|
| Fuente | Archivo `SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm` |
| ETL | Scripts de Python en `Data/etl` (limpieza y carga) |
| Almacenamiento | PostgreSQL, base de datos `BI_Vinilos`, modelo dimensional con tablas de hechos (`fact_produccion`, `fact_paro`, `fact_lectura_hora`) y dimensiones (`dim_*`) |
| Análisis histórico | Power BI, conectado a PostgreSQL en modo Importar |
| Monitoreo operativo | Grafana, conectado a PostgreSQL |
| Simulación | `simulador.py` inserta lecturas hora a hora para demostrar el tablero y la alerta |

## 3. Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `Data/etl/` | `01_limpiar.py`, `02_cargar.py` y `simulador.py` |
| `Data/sql/` | Scripts SQL (modelo y tiempo real) |
| `Data/limpio/` | Base limpia generada por el ETL |
| `notebooks/` | Perfilado de columnas de la fuente |
| `Grafana/` | Dashboard exportado en JSON |
| [COMPLETAR: carpeta] | Proyecto de Power BI en formato PBIP |

## 4. Cómo reproducir la solución desde cero

**Requisitos:** Python 3, PostgreSQL, Power BI Desktop, Grafana y Git.

**1. Clonar el repositorio**

```powershell
git clone https://github.com/J-Anacona/BI_Vinilos.git
cd BI_Vinilos
```

**2. Crear la base de datos**

```powershell
psql -U postgres -c 'CREATE DATABASE "BI_Vinilos";'
```

**3. Crear el entorno virtual e instalar dependencias**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**4. Configurar la conexión.** Cree un archivo `.env` en la raíz (no se versiona) con los datos de su PostgreSQL local:

```
PGHOST=localhost
PGPORT=5432
PGDATABASE=BI_Vinilos
PGUSER=postgres
PGPASSWORD=su_contraseña
```

**5. Colocar el Excel.** Copie el archivo `.xlsm` en [COMPLETAR: ruta que espera `01_limpiar.py`].Se incluye en el repositorio.

**6. Ejecutar el ETL**

```powershell
python Data/etl/01_limpiar.py
python Data/etl/02_cargar.py
```

**7. Habilitar el monitoreo en tiempo real**

```powershell
psql -U postgres -d BI_Vinilos -f Data/sql/04_tiempo_real.sql
python Data/etl/simulador.py
```

**8. Grafana.** Cree una fuente de datos PostgreSQL (`localhost:5432`, base `BI_Vinilos`) e importe el JSON de la carpeta `Grafana/` en *Dashboards → New → Import*.

**9. Power BI.** Abra el proyecto PBIP, configure la conexión a `localhost:5432`, base `BI_Vinilos`, modo Importar, y pulse *Actualizar*.

## 5. Formato de Power BI: PBIP

El proyecto de Power BI se versiona en formato **PBIP**, que guarda el informe y el modelo semántico como carpetas de archivos de texto. Así, Git muestra qué cambió en cada commit (medidas, relaciones, páginas) y permite revisar y fusionar el trabajo de varias personas. El formato `.pbix` es un archivo binario único que Git no puede comparar ni fusionar.

## 6. Seguridad

Ninguna contraseña ni cadena de conexión se guarda en el repositorio: las credenciales se leen del archivo `.env`, excluido en `.gitignore`, junto con el Excel original y el entorno virtual.



- [COMPLETAR: integrante 1]
- [COMPLETAR: integrante 2]
