import pandas as pd

df = pd.read_csv("data/limpio/base_limpia.csv", parse_dates=["Fecha"])
df["anio"] = df["Fecha"].dt.year

print("TURNO (conteo por año)\n")
print(pd.crosstab(df["Turno"].fillna("(nulo)"), df["anio"]).to_string())

print("\n\nTIPO DE PARO (conteo por año)\n")
print(pd.crosstab(df["Tipo de paro"].fillna("(nulo)"), df["anio"]).to_string())