import re
import pandas as pd
from pathlib import Path

ARCHIVO = Path("data/original/SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm")
SALIDA = Path("data/limpio")
SALIDA.mkdir(parents=True, exist_ok=True)

log = []


def registrar(regla, antes, despues, nota=""):
    log.append({
        "regla": regla,
        "antes": antes,
        "despues": despues,
        "efecto": round(antes - despues, 2),
        "nota": nota,
    })


# 1. Leer el Excel (sin modificarlo)
df = pd.read_excel(ARCHIVO, sheet_name="Base De Datos", header=8, engine="openpyxl")

# 2. Normalizar nombres de columnas (saltos de línea, espacios, error de "Codigode")
df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
df.columns = [c.replace("Codigode", "Codigo de") for c in df.columns]

# 3. Quitar filas totalmente vacías
antes = len(df)
df = df.dropna(how="all")
registrar("Filas totalmente vacías", antes, len(df))

filas_origen = len(df)
horas_paro_origen = df["Tiempo de Paro"].sum()

# 4. Eliminar duplicados exactos
antes_n = len(df)
antes_h = df["Tiempo de Paro"].sum()
df = df.drop_duplicates().copy()
registrar("Duplicados exactos (filas)", antes_n, len(df))
registrar("Duplicados exactos (horas de paro)", antes_h, df["Tiempo de Paro"].sum(),
          "Horas de paro que salen al quitar duplicados")

# 5. Quitar columnas 100% vacías
antes_c = df.shape[1]
df = df.dropna(axis=1, how="all")
registrar("Columnas totalmente vacías", antes_c, df.shape[1])

# 6. Valores centinela -> nulos reales
for col in ["Operario", "Referencia", "Turno"]:
    antes_v = df[col].notna().sum()
    df[col] = df[col].replace("No aplica", pd.NA)
    registrar(f"'No aplica' en {col} pasa a nulo", antes_v, df[col].notna().sum())

antes_v = df["Operario"].notna().sum()
df["Operario"] = df["Operario"].replace("No", pd.NA)
registrar("'No' en Operario pasa a nulo", antes_v, df["Operario"].notna().sum())

# 7. Fecha como fecha real
df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
registrar("Fechas inválidas", df["Fecha"].isna().sum(), 0)

# 8. TURNO: se conservan los 6 valores y se agregan atributos derivados del texto
TURNOS = {
    "6am-2pm (Turno 1)":  ("06:00", "14:00", 8.0,  "Estándar"),
    "2pm-10pm (Turno 2)": ("14:00", "22:00", 8.0,  "Estándar"),
    "10pm-6am (Turno 3)": ("22:00", "06:00", 8.0,  "Estándar"),
    "6am-4:30pm":         ("06:00", "16:30", 10.5, "Extendido"),
    "6am-6pm":            ("06:00", "18:00", 12.0, "Extendido"),
    "6pm-6am":            ("18:00", "06:00", 12.0, "Extendido"),
}
tt = pd.DataFrame.from_dict(
    TURNOS, orient="index",
    columns=["turno_inicio", "turno_fin", "turno_horas", "turno_tipo"],
)

df["Turno"] = df["Turno"].astype("string").str.strip()
df = df.join(tt, on="Turno")

desconocidos = df.loc[df["Turno"].notna() & df["turno_tipo"].isna(), "Turno"].unique()
if len(desconocidos) > 0:
    print("ATENCIÓN: turnos no reconocidos:", list(desconocidos))

nulos_turno = df["Turno"].isna().sum()
df["Turno"] = df["Turno"].fillna("Sin turno registrado")
df["turno_tipo"] = df["turno_tipo"].fillna("Sin dato")
registrar("Turno nulo pasa a 'Sin turno registrado'", nulos_turno, 0,
          "2022 no tiene ningún turno registrado")

# 9. TIPO DE PARO: separar número y nombre, identificar catálogo, unificar nulo con [19]
df["tipo_paro_original"] = df["Tipo de paro"]
tp = (
    df["Tipo de paro"].astype("string")
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
)
nulo = tp.isna()

nuevo = tp.str.extract(r"^\[(\d+)\]\s*(.*)$")   # formato vigente: [14] Falta de...
viejo = tp.str.extract(r"^(\d+)\.\s*(.*)$")     # formato histórico: 6. FALTA DE...
es_nuevo = nuevo[0].notna()
es_viejo = viejo[0].notna()

codigo = nuevo[0].where(es_nuevo, viejo[0])
nombre = nuevo[1].where(es_nuevo, viejo[1])
nombre = nombre.where(~es_viejo, nombre.str.capitalize())

codigo = codigo.mask(nulo, "19")
nombre = nombre.mask(nulo, "No aplica")

sin_formato = (~nulo) & (~es_nuevo) & (~es_viejo)
if sin_formato.sum() > 0:
    print("ATENCIÓN: tipos de paro con formato no reconocido:",
          list(tp[sin_formato].unique()))

df["tipo_paro_codigo"] = pd.to_numeric(codigo, errors="coerce").astype("Int64")
df["tipo_paro_nombre"] = nombre
df["tipo_paro_catalogo"] = es_viejo.map({True: "historico", False: "vigente"})
df["tipo_paro_era_nulo"] = nulo

# Equivalencia histórico -> vigente (solo los 6 casos aprobados)
EQUIV = {4: 5, 10: 12, 15: 13, 6: 14, 3: 3, 5: 7}
df["tipo_paro_equiv"] = pd.array(
    [c if cat == "vigente" else EQUIV.get(c, pd.NA)
     for c, cat in zip(df["tipo_paro_codigo"], df["tipo_paro_catalogo"])],
    dtype="Int64",
)

registrar("Tipo de paro: nulos unificados con [19] No aplica", nulo.sum(), 0)
registrar("Tipo de paro: valores distintos (texto original -> nombres limpios)",
          df["tipo_paro_original"].nunique(),
          df[["tipo_paro_catalogo", "tipo_paro_codigo", "tipo_paro_nombre"]]
          .drop_duplicates().shape[0])

# 10. OBSERVACIONES de paro: unificar mayúsculas y espacios
antes_o = df["Observaciones de paro"].nunique()
df["Observaciones de paro"] = (
    df["Observaciones de paro"].astype("string")
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
    .str.capitalize()
)
registrar("Observaciones de paro: valores distintos", antes_o,
          df["Observaciones de paro"].nunique())

# 11. Marcas (NO se borra nada): solo se señalan
df["sin_produccion"] = df["Pacas producidas"].isna() & df["Horas trabajadas"].isna()
df["pacas_atipica"] = df["Pacas producidas"] > 1000
df["horas_atipica"] = df["Horas trabajadas"] > 12

# 12. Guardar resultado y registro
df.to_csv(SALIDA / "base_limpia.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(log).to_csv(SALIDA / "log_limpieza.csv", index=False, encoding="utf-8-sig")

# 13. Resumen en pantalla
print("REGISTRO DE LIMPIEZA\n")
print(pd.DataFrame(log).to_string(index=False))
print(f"\nFilas origen: {filas_origen} | Filas finales: {len(df)}")
print(f"Horas de paro origen: {horas_paro_origen:.1f} | finales: {df['Tiempo de Paro'].sum():.1f}")
print(f"Filas sin producción: {df['sin_produccion'].sum()}")
print(f"Pacas atípicas (>1000): {df['pacas_atipica'].sum()}")
print(f"Horas atípicas (>12): {df['horas_atipica'].sum()}")

print("\nTURNO (conteo)\n")
print(df["Turno"].value_counts().to_string())

print("\nTIPO DE PARO por catálogo\n")
print(df["tipo_paro_catalogo"].value_counts().to_string())

print("\nFilas históricas SIN equivalencia en el catálogo vigente:",
      int(((df["tipo_paro_catalogo"] == "historico") & df["tipo_paro_equiv"].isna()).sum()))

print("\nArchivos creados en data/limpio/")