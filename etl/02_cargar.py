import os
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ARCHIVO = Path("data/original/SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm")
LIMPIO = Path("data/limpio/base_limpia.csv")
PRIVADO = Path("data/privado")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

SUB_COL = {1: "Sub Codigo de paro 1", 3: "Subcodigo 3", 5: "Subcodigo 5"}
# Código 5: numeración antigua (4.x) -> vigente (5.x), según el nombre
MAPA_5 = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9}


def normalizar_nombre(s):
    s = re.sub(r"\s+", " ", str(s)).strip().strip(".").lower()
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------------
# Subcódigos: unificar formato y numeración
# ---------------------------------------------------------------------
def parsear_subcodigo(valor, codigo):
    """Devuelve (clave_subsistema, clave_componente, nombre) o None si no hay subcódigo."""
    if pd.isna(valor):
        return None
    v = str(valor).strip()
    if v.lower() == "sin especificar" or v == "":
        return None
    if codigo == 1:
        m = re.match(r"^1\.(\d+)(?:\.?([A-Za-z0-9]))?\s*(.*)$", v)
        if not m:
            return None
        sub = f"1.{m.group(1)}"
        comp = f"{sub}.{m.group(2).upper()}" if m.group(2) else None
        return sub, comp, normalizar_nombre(m.group(3))
    if codigo == 3:
        m = re.match(r"^3\.(\d+)\s*(.*)$", v)
        if not m:
            return None
        return f"3.{m.group(1)}", None, normalizar_nombre(m.group(2))
    if codigo == 5:
        m = re.match(r"^([45])\.(\d+)\s*(.*)$", v)
        if not m:
            return None
        n = int(m.group(2))
        if m.group(1) == "4":
            n = MAPA_5.get(n, n)
        return f"5.{n}", None, normalizar_nombre(m.group(3))
    return None


def construir_dim_codigo_paro(df):
    # Áreas y nombres de código desde TABLA CODIGOS (filas 5 a 21)
    wb = load_workbook(ARCHIVO, read_only=True, data_only=True)
    ws = wb["TABLA CODIGOS"]
    codigos = {}
    for fila in ws.iter_rows(min_row=5, max_row=21, values_only=True):
        area, nombre = fila[4], fila[5]
        m = re.match(r"^\[(\d+)\]", str(nombre))
        if m:
            codigos[int(m.group(1))] = (str(area).strip(), str(nombre).strip())
    # Código 18 (Desinfección) aparece en el formato del PDF, no en TABLA CODIGOS
    codigos[18] = ("Sin área definida", "[18] Desinfección")

    # Parsear todos los subcódigos usados (solo filas con horas > 0)
    parsed = {}        # (codigo, valor_original) -> (sub, comp, nombre)
    nombres_sub = {}   # (codigo, clave) -> Counter de nombres
    for cod, col in SUB_COL.items():
        horas = pd.to_numeric(df[f"Codigo {cod} en horas"], errors="coerce").fillna(0)
        for valor in df.loc[horas > 0, col].dropna().unique():
            parsed[(cod, valor)] = parsear_subcodigo(valor, cod)
        # contar nombres por frecuencia real (por fila)
        for valor in df.loc[horas > 0, col].dropna():
            p = parsed.get((cod, valor))
            if p is None:
                continue
            sub, comp, nombre = p
            clave = comp if comp else sub
            nombres_sub.setdefault((cod, clave), Counter())[nombre] += 1

    def nombre_de(cod, clave):
        c = nombres_sub.get((cod, clave))
        return c.most_common(1)[0][0] if c else None

    filas = {}      # (codigo, subsistema, subcodigo) -> None
    resolver = {}   # (codigo, valor_original) -> (subsistema, subcodigo)

    for (cod, valor), p in parsed.items():
        if p is None:
            continue
        sub, comp, _ = p
        if cod == 1:
            sub_txt = f"{sub} {nombre_de(1, sub) or 'Sin nombre'}"
            comp_txt = f"{comp} {nombre_de(1, comp)}" if comp else "Sin subcódigo"
            resolver[(cod, valor)] = (sub_txt, comp_txt)
        else:
            resolver[(cod, valor)] = ("No aplica", f"{sub} {nombre_de(cod, sub)}")

    for (cod, valor), res in resolver.items():
        filas[(cod, res[0], res[1])] = None
    # Fila por defecto de cada código (también para nulos y "Sin especificar")
    for cod in codigos:
        sub_def = "Sin subsistema" if cod == 1 else "No aplica"
        filas[(cod, sub_def, "Sin subcódigo")] = None

    dim = pd.DataFrame(sorted(filas.keys()),
                       columns=["codigo", "subsistema", "subcodigo"])
    dim["area_impacto"] = dim["codigo"].map(lambda c: codigos[c][0])
    dim["codigo_nombre"] = dim["codigo"].map(lambda c: codigos[c][1])
    dim.insert(0, "codigo_paro_key", range(1, len(dim) + 1))
    dim = dim[["codigo_paro_key", "area_impacto", "codigo", "codigo_nombre",
               "subsistema", "subcodigo"]]
    return dim, resolver


# ---------------------------------------------------------------------
# Construcción de todas las tablas
# ---------------------------------------------------------------------
def construir():
    df = pd.read_csv(LIMPIO, parse_dates=["Fecha"], encoding="utf-8-sig")
    df["Maquina"] = df["Maquina"].astype(str).str.strip()
    df["tipo_paro_equiv"] = df["tipo_paro_equiv"].astype("Int64")
    t = {}

    # dim_fecha (calendario continuo)
    fechas = pd.date_range(df["Fecha"].min(), df["Fecha"].max(), freq="D")
    t["dim_fecha"] = pd.DataFrame({
        "fecha_key": fechas.strftime("%Y%m%d").astype(int),
        "fecha": fechas.date,
        "anio": fechas.year,
        "trimestre": fechas.quarter,
        "mes": fechas.month,
        "nombre_mes": [MESES[m - 1] for m in fechas.month],
        "anio_mes": fechas.strftime("%Y-%m"),
        "dia": fechas.day,
        "dia_semana": fechas.dayofweek + 1,
        "nombre_dia": [DIAS[d] for d in fechas.dayofweek],
        "es_fin_semana": fechas.dayofweek >= 5,
    })

    # dim_maquina
    maq = sorted(df["Maquina"].unique())
    t["dim_maquina"] = pd.DataFrame({"maquina_key": range(1, len(maq) + 1),
                                     "maquina_nombre": maq})

    # dim_turno (la llave 0 "Sin turno registrado" ya existe por el DDL)
    tur = (df.loc[df["Turno"] != "Sin turno registrado",
                  ["Turno", "turno_inicio", "turno_fin", "turno_horas", "turno_tipo"]]
           .drop_duplicates().sort_values("Turno").reset_index(drop=True))
    tur.insert(0, "turno_key", range(1, len(tur) + 1))
    tur.columns = ["turno_key", "turno_nombre", "hora_inicio", "hora_fin",
                   "duracion_horas", "turno_tipo"]
    t["dim_turno"] = tur

    # dim_referencia (llave 0 = "Sin referencia")
    ref = sorted(df["Referencia"].dropna().astype(str).str.strip().unique())
    t["dim_referencia"] = pd.DataFrame({"referencia_key": range(1, len(ref) + 1),
                                        "referencia_nombre": ref})

    # dim_operario: seudónimo; el mapa nombre -> código queda en un archivo local
    ope = sorted(df["Operario"].dropna().astype(str).str.strip().unique())
    mapa_ope = pd.DataFrame({"operario_key": range(1, len(ope) + 1),
                             "operario_codigo": [f"OP-{i:03d}" for i in range(1, len(ope) + 1)],
                             "operario_nombre": ope})
    PRIVADO.mkdir(parents=True, exist_ok=True)
    mapa_ope.to_csv(PRIVADO / "operarios_mapa.csv", index=False, encoding="utf-8-sig")
    t["dim_operario"] = mapa_ope[["operario_key", "operario_codigo"]]

    # dim_motivo_no_trabajo
    mot = (df.groupby(["tipo_paro_catalogo", "tipo_paro_codigo"])
           .agg(nombre=("tipo_paro_nombre", lambda s: s.value_counts().index[0]),
                codigo_equivalente=("tipo_paro_equiv", "first"))
           .reset_index())
    mot.insert(0, "motivo_key", range(1, len(mot) + 1))
    mot.columns = ["motivo_key", "catalogo", "codigo", "nombre", "codigo_equivalente"]
    mot["codigo_equivalente"] = mot["codigo_equivalente"].astype("Int64")
    t["dim_motivo_no_trabajo"] = mot

    # dim_codigo_paro
    dim_cod, resolver = construir_dim_codigo_paro(df)
    t["dim_codigo_paro"] = dim_cod

    # ----- fact_produccion -----
    mk_maq = dict(zip(t["dim_maquina"]["maquina_nombre"], t["dim_maquina"]["maquina_key"]))
    mk_tur = dict(zip(tur["turno_nombre"], tur["turno_key"]))
    mk_ref = dict(zip(t["dim_referencia"]["referencia_nombre"], t["dim_referencia"]["referencia_key"]))
    mk_ope = dict(zip(mapa_ope["operario_nombre"], mapa_ope["operario_key"]))
    mk_mot = {(r.catalogo, r.codigo): r.motivo_key for r in mot.itertuples()}

    f = pd.DataFrame()
    f["produccion_key"] = range(1, len(df) + 1)
    f["fecha_key"] = df["Fecha"].dt.strftime("%Y%m%d").astype(int).values
    f["maquina_key"] = df["Maquina"].map(mk_maq).values
    f["turno_key"] = df["Turno"].map(mk_tur).fillna(0).astype(int).values
    f["referencia_key"] = df["Referencia"].astype("string").str.strip().map(mk_ref).fillna(0).astype(int).values
    f["operario_key"] = df["Operario"].astype("string").str.strip().map(mk_ope).fillna(0).astype(int).values
    f["motivo_key"] = [mk_mot[(c, k)] for c, k in zip(df["tipo_paro_catalogo"], df["tipo_paro_codigo"])]
    f["pacas_producidas"] = pd.to_numeric(df["Pacas producidas"], errors="coerce").values
    f["horas_trabajadas"] = pd.to_numeric(df["Horas trabajadas"], errors="coerce").values
    f["horas_no_trabajadas"] = pd.to_numeric(df["Horas no trabajadas"], errors="coerce").values
    f["tiempo_paro_horas"] = pd.to_numeric(df["Tiempo de Paro"], errors="coerce").fillna(0).values
    f["observacion_paro"] = df["Observaciones de paro"].astype("string").str.slice(0, 250).values
    f["sin_produccion"] = df["sin_produccion"].values
    f["pacas_atipica"] = df["pacas_atipica"].values
    f["horas_atipica"] = df["horas_atipica"].values
    t["fact_produccion"] = f

    # ----- fact_paro (formato largo: un registro x un código con horas > 0) -----
    mk_cod = {(r.codigo, r.subsistema, r.subcodigo): r.codigo_paro_key for r in dim_cod.itertuples()}
    area = (df["Área involucrada en subcodigo 5"].astype("string").str.strip()
            .str.replace("_", " ", regex=False).fillna("Sin dato"))
    partes = []
    for n in range(1, 19):
        horas = pd.to_numeric(df[f"Codigo {n} en horas"], errors="coerce").fillna(0)
        mask = (horas > 0).values
        if not mask.any():
            continue
        sub_def = ("Sin subsistema" if n == 1 else "No aplica", "Sin subcódigo")
        claves = []
        for i in df.index[mask]:
            if n in SUB_COL:
                res = resolver.get((n, df.at[i, SUB_COL[n]]), sub_def)
            else:
                res = sub_def
            claves.append(mk_cod[(n, res[0], res[1])])
        p = f.loc[mask, ["produccion_key", "fecha_key", "maquina_key", "turno_key",
                         "referencia_key", "operario_key"]].copy()
        p["codigo_paro_key"] = claves
        p["horas_paro"] = horas[mask].values
        p["area_involucrada"] = area[mask].values if n == 5 else None
        partes.append(p)
    fp = pd.concat(partes, ignore_index=True)
    fp = fp.sort_values(["produccion_key", "codigo_paro_key"]).reset_index(drop=True)
    fp.insert(0, "paro_key", range(1, len(fp) + 1))
    t["fact_paro"] = fp
    return t


# ---------------------------------------------------------------------
# Carga a PostgreSQL
# ---------------------------------------------------------------------
def conectar():
    clave = os.environ.get("PGPASSWORD")
    if not clave:
        raise SystemExit("Falta la variable PGPASSWORD. En PowerShell: "
                         '$env:PGPASSWORD="tu_clave"')
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("PGUSER", "postgres"),
        password=clave,
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        database=os.environ.get("PGDATABASE", "BI_Vinilos_Temperas"),
    )
    return create_engine(url)


def main():
    t = construir()
    engine = conectar()
    claves = {"dim_fecha": "fecha_key", "dim_maquina": "maquina_key",
              "dim_turno": "turno_key", "dim_referencia": "referencia_key",
              "dim_operario": "operario_key", "dim_codigo_paro": "codigo_paro_key",
              "dim_motivo_no_trabajo": "motivo_key"}
    orden = ["dim_fecha", "dim_maquina", "dim_turno", "dim_referencia", "dim_operario",
             "dim_codigo_paro", "dim_motivo_no_trabajo", "fact_produccion", "fact_paro"]

    with engine.begin() as con:
        # Vaciar (se puede ejecutar varias veces); se conservan los miembros con llave 0
        con.execute(text("TRUNCATE fact_paro, fact_produccion"))
        for tabla, k in claves.items():
            con.execute(text(f"DELETE FROM {tabla} WHERE {k} > 0"))
        for tabla in orden:
            t[tabla].to_sql(tabla, con, if_exists="append", index=False,
                            method="multi", chunksize=1000)
            print(f"{tabla:25s} filas cargadas: {len(t[tabla])}")

    print("\nControl rápido")
    print(f"Horas de paro en fact_produccion: {t['fact_produccion']['tiempo_paro_horas'].sum():.3f}")
    print(f"Horas de paro en fact_paro:       {t['fact_paro']['horas_paro'].sum():.3f}")
    print("\nCarga terminada.")


if __name__ == "__main__":
    main()