import pandas as pd
from pathlib import Path

archivo = Path(
    "data/original/SEGUIMIENTO TEMPERAS Y VINILOS Actividad.xlsm"
)

df = pd.read_excel(
    archivo,
    sheet_name="Base De Datos",
    header=8,
    engine="openpyxl"
)

df = df.drop_duplicates().copy()

print("REVISIÓN DE REGISTROS CON DIFERENCIAS\n")

for numero in [1, 5, 16, 17]:

    columna_codigo = f"Codigo de paro {numero}"
    columna_horas = f"Codigo {numero} en horas"

    codigos = pd.to_numeric(df[columna_codigo], errors="coerce")
    horas = pd.to_numeric(df[columna_horas], errors="coerce")

    # Registros con código, pero sin horas positivas
    diferencia = df[
        codigos.notna() & (horas <= 0)
    ]

    print(f"\nCÓDIGO {numero}")
    print("Registros con código:", codigos.notna().sum())
    print("Registros con horas positivas:", horas.gt(0).sum())
    print("Registros con código y horas cero:", len(diferencia))

    if not diferencia.empty:
        print(
            diferencia[
                ["Fecha", "Maquina", columna_codigo, columna_horas,
                 "Tiempo de Paro"]
            ].head(10).to_string(index=False)
        )

print("\nREVISIÓN FINALIZADA.")