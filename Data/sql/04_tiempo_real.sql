-- Hecho operativo para el monitoreo casi en tiempo real (Grafana)
-- Grano: una lectura por máquina y hora de operación.
DROP TABLE IF EXISTS fact_lectura_hora;

CREATE TABLE fact_lectura_hora (
    lectura_key        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    maquina_key        INTEGER NOT NULL REFERENCES dim_maquina (maquina_key),
    turno_key          INTEGER NOT NULL REFERENCES dim_turno (turno_key),
    codigo_paro_key    INTEGER REFERENCES dim_codigo_paro (codigo_paro_key),  -- causa del paro (si hubo)
    pacas_producidas   NUMERIC(10,2) NOT NULL CHECK (pacas_producidas >= 0),
    minutos_paro       NUMERIC(5,2)  NOT NULL CHECK (minutos_paro BETWEEN 0 AND 60),
    -- Misma fórmula del P-MTO-22 aplicada a una hora (60 minutos)
    productividad_pct  NUMERIC(5,2) GENERATED ALWAYS AS
                       (ROUND(100.0 * (60 - minutos_paro) / 60, 2)) STORED,
    estado             VARCHAR(10) GENERATED ALWAYS AS
                       (CASE WHEN minutos_paro >= 60 THEN 'Parada'
                             WHEN minutos_paro > 0   THEN 'Con paros'
                             ELSE 'Operando' END) STORED
);

-- Series de tiempo filtradas por rango y máquina (paneles de Grafana)
CREATE INDEX ix_lectura_ts ON fact_lectura_hora (ts);
-- Última lectura de cada máquina (estado actual)
CREATE INDEX ix_lectura_maquina_ts ON fact_lectura_hora (maquina_key, ts DESC);