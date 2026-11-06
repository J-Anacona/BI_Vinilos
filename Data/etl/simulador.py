"""
Simulador de lecturas hora a hora para Grafana.

Cada ciclo representa UNA HORA de planta y se genera una lectura por máquina.
Por defecto se genera un ciclo cada 10 segundos reales (tiempo acelerado).
Los valores se basan en el comportamiento histórico de cada máquina.

Uso:
    python etl/simulador.py
    python etl/simulador.py --incidente Vinilos_2 --despues 6 --duracion 8
"""
import argparse
import os
import random
import time
from datetime import datetime, timedelta

import psycopg2


def conectar():
    params = dict(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "BI_Vinilos"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )
    try:
        return psycopg2.connect(**params)
    except UnicodeDecodeError as e:
        raise SystemExit("Error de conexión: " + e.object.decode("cp1252", errors="replace"))


def cargar_base(cur):
    """Comportamiento histórico por máquina: pacas/hora, fracción de paro y causas."""
    cur.execute("""
        SELECT m.maquina_key, m.maquina_nombre,
               SUM(p.pacas_producidas) / NULLIF(SUM(p.horas_trabajadas), 0),
               SUM(p.tiempo_paro_horas) / NULLIF(SUM(p.horas_trabajadas), 0)
        FROM fact_produccion p
        JOIN dim_maquina m USING (maquina_key)
        WHERE p.horas_trabajadas > 0 AND p.pacas_producidas > 0
          AND p.pacas_atipica = FALSE
        GROUP BY m.maquina_key, m.maquina_nombre
        ORDER BY m.maquina_nombre
    """)
    base = {}
    for key, nombre, pacas_h, frac in cur.fetchall():
        base[key] = {
            "nombre": nombre,
            "pacas_hora": float(pacas_h),
            "min_paro_medio": 60 * min(max(float(frac), 0.05), 0.5),
            "causas": [], "pesos": [],
        }
    cur.execute("""
        SELECT maquina_key, codigo_paro_key, SUM(horas_paro)
        FROM fact_paro GROUP BY maquina_key, codigo_paro_key
    """)
    for mk, ck, h in cur.fetchall():
        if mk in base:
            base[mk]["causas"].append(ck)
            base[mk]["pesos"].append(float(h))
    return base


def generar(b, incidente, causa_incidente):
    """Devuelve (pacas, minutos_paro, codigo_paro_key) de una hora de operación."""
    if incidente:
        minutos = round(random.uniform(45, 60), 2)
        causa = causa_incidente
    elif random.random() < 0.5:
        minutos = round(min(random.expovariate(1 / (2 * b["min_paro_medio"])), 60), 2)
        causa = random.choices(b["causas"], weights=b["pesos"])[0]
    else:
        minutos, causa = 0.0, None
    if minutos == 0:
        causa = None
    pacas = b["pacas_hora"] * (60 - minutos) / 60 * random.uniform(0.9, 1.1)
    return round(pacas, 2), minutos, causa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=float, default=10, help="segundos reales por hora simulada")
    ap.add_argument("--incidente", help="máquina que tendrá un incidente, ej. Vinilos_2")
    ap.add_argument("--despues", type=int, default=6, help="horas normales antes del incidente")
    ap.add_argument("--duracion", type=int, default=6, help="horas que dura el incidente")
    ap.add_argument("--horas", type=int, default=0, help="detenerse tras N horas (0 = sin límite)")
    args = ap.parse_args()

    con = conectar()
    cur = con.cursor()
    base = cargar_base(cur)
    if not base:
        raise SystemExit("No hay datos históricos en fact_produccion.")

    cur.execute("SELECT turno_nombre, turno_key FROM dim_turno")
    turnos = dict(cur.fetchall())
    cur.execute("SELECT codigo_paro_key FROM dim_codigo_paro "
                "WHERE codigo = 1 AND subsistema = 'Sin subsistema'")
    causa_incidente = cur.fetchone()[0]

    maq_incidente = None
    if args.incidente:
        for k, b in base.items():
            if b["nombre"] == args.incidente:
                maq_incidente = k
        if maq_incidente is None:
            raise SystemExit(f"Máquina no encontrada: {args.incidente}")

    def turno_de(hora):
        if 6 <= hora < 14:
            return turnos["6am-2pm (Turno 1)"]
        if 14 <= hora < 22:
            return turnos["2pm-10pm (Turno 2)"]
        return turnos["10pm-6am (Turno 3)"]

    hora_sim = datetime.now().replace(minute=0, second=0, microsecond=0)
    ciclo = 0
    print(f"Simulando 1 hora de planta cada {args.intervalo:g} s. Ctrl+C para detener.\n")
    try:
        while True:
            en_incidente = (maq_incidente is not None and
                            args.despues <= ciclo < args.despues + args.duracion)
            for mk, b in base.items():
                inc = en_incidente and mk == maq_incidente
                pacas, minutos, causa = generar(b, inc, causa_incidente)
                cur.execute(
                    "INSERT INTO fact_lectura_hora "
                    "(maquina_key, turno_key, codigo_paro_key, pacas_producidas, minutos_paro) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (mk, turno_de(hora_sim.hour), causa, pacas, minutos),
                )
                prod = 100 * (60 - minutos) / 60
                marca = "  <-- INCIDENTE" if inc else ""
                print(f"{hora_sim:%d/%m %H:00} | {b['nombre']} | pacas {pacas:7.1f} | "
                      f"paro {minutos:5.1f} min | productividad {prod:5.1f} %{marca}")
            con.commit()
            ciclo += 1
            hora_sim += timedelta(hours=1)
            if args.horas and ciclo >= args.horas:
                break
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nSimulación detenida.")
    finally:
        con.close()


if __name__ == "__main__":
    main()