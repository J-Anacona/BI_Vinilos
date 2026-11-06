-- =====================================================================
-- Modelo dimensional: producción y paros de vinilos y témperas
-- Se puede ejecutar varias veces (borra y recrea todo).
-- =====================================================================

DROP TABLE IF EXISTS fact_paro CASCADE;
DROP TABLE IF EXISTS fact_produccion CASCADE;
DROP TABLE IF EXISTS dim_motivo_no_trabajo CASCADE;
DROP TABLE IF EXISTS dim_codigo_paro CASCADE;
DROP TABLE IF EXISTS dim_operario CASCADE;
DROP TABLE IF EXISTS dim_referencia CASCADE;
DROP TABLE IF EXISTS dim_turno CASCADE;
DROP TABLE IF EXISTS dim_maquina CASCADE;
DROP TABLE IF EXISTS dim_fecha CASCADE;

-- ---------------------------------------------------------------------
-- DIMENSIONES
-- ---------------------------------------------------------------------

CREATE TABLE dim_fecha (
    fecha_key      INTEGER PRIMARY KEY,                 -- AAAAMMDD, ej. 20240315
    fecha          DATE NOT NULL UNIQUE,
    anio           SMALLINT NOT NULL,
    trimestre      SMALLINT NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mes            SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    nombre_mes     VARCHAR(12) NOT NULL,
    anio_mes       CHAR(7) NOT NULL,                    -- '2024-03'
    dia            SMALLINT NOT NULL CHECK (dia BETWEEN 1 AND 31),
    dia_semana     SMALLINT NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),  -- 1 = lunes
    nombre_dia     VARCHAR(12) NOT NULL,
    es_fin_semana  BOOLEAN NOT NULL
);

CREATE TABLE dim_maquina (
    maquina_key     INTEGER PRIMARY KEY,
    maquina_nombre  VARCHAR(30) NOT NULL UNIQUE         -- Vinilos_1 ... Vinilos_4
);

CREATE TABLE dim_turno (
    turno_key       INTEGER PRIMARY KEY,
    turno_nombre    VARCHAR(40) NOT NULL UNIQUE,
    hora_inicio     TIME,
    hora_fin        TIME,
    duracion_horas  NUMERIC(4,1),
    turno_tipo      VARCHAR(12) NOT NULL
                    CHECK (turno_tipo IN ('Estándar', 'Extendido', 'Sin dato'))
);

CREATE TABLE dim_referencia (
    referencia_key     INTEGER PRIMARY KEY,
    referencia_nombre  VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE dim_operario (
    operario_key     INTEGER PRIMARY KEY,
    operario_codigo  VARCHAR(10) NOT NULL UNIQUE        -- seudónimo: OP-001
);

-- Jerarquía de paros en una sola tabla: área -> código -> subcódigo
-- Jerarquía de paros en una sola tabla: área -> código -> subsistema -> subcódigo
CREATE TABLE dim_codigo_paro (
    codigo_paro_key  INTEGER PRIMARY KEY,
    area_impacto     VARCHAR(60) NOT NULL DEFAULT 'Sin área definida',
    codigo           SMALLINT NOT NULL CHECK (codigo BETWEEN 1 AND 18),
    codigo_nombre    VARCHAR(150) NOT NULL,
    subsistema       VARCHAR(150) NOT NULL DEFAULT 'No aplica',
    subcodigo        VARCHAR(150) NOT NULL DEFAULT 'Sin subcódigo',
    UNIQUE (codigo, subsistema, subcodigo)
);

-- Dimensión construida por nosotros: motivo de las horas no trabajadas
CREATE TABLE dim_motivo_no_trabajo (
    motivo_key           INTEGER PRIMARY KEY,
    catalogo             VARCHAR(10) NOT NULL CHECK (catalogo IN ('historico', 'vigente')),
    codigo               SMALLINT NOT NULL,
    nombre               VARCHAR(150) NOT NULL,
    codigo_equivalente   SMALLINT,                      -- equivalente en el catálogo vigente (si existe)
    UNIQUE (catalogo, codigo)
);

-- Miembros "desconocido" (llave 0) para no perder filas con nulos
INSERT INTO dim_turno (turno_key, turno_nombre, hora_inicio, hora_fin, duracion_horas, turno_tipo)
VALUES (0, 'Sin turno registrado', NULL, NULL, NULL, 'Sin dato');

INSERT INTO dim_referencia (referencia_key, referencia_nombre)
VALUES (0, 'Sin referencia');

INSERT INTO dim_operario (operario_key, operario_codigo)
VALUES (0, 'OP-000');

-- ---------------------------------------------------------------------
-- HECHOS
-- ---------------------------------------------------------------------

-- Grano: un registro de la hoja "Base De Datos"
-- (máquina, fecha, turno, referencia y operario)
CREATE TABLE fact_produccion (
    produccion_key        INTEGER PRIMARY KEY,
    fecha_key             INTEGER NOT NULL REFERENCES dim_fecha (fecha_key),
    maquina_key           INTEGER NOT NULL REFERENCES dim_maquina (maquina_key),
    turno_key             INTEGER NOT NULL REFERENCES dim_turno (turno_key),
    referencia_key        INTEGER NOT NULL REFERENCES dim_referencia (referencia_key),
    operario_key          INTEGER NOT NULL REFERENCES dim_operario (operario_key),
    motivo_key            INTEGER NOT NULL REFERENCES dim_motivo_no_trabajo (motivo_key),
    pacas_producidas      NUMERIC(12,2)  CHECK (pacas_producidas >= 0),
    horas_trabajadas      NUMERIC(10,6)  CHECK (horas_trabajadas >= 0),
    horas_no_trabajadas   NUMERIC(10,6)  CHECK (horas_no_trabajadas >= 0),
    tiempo_paro_horas     NUMERIC(10,6)  NOT NULL DEFAULT 0 CHECK (tiempo_paro_horas >= 0),
    observacion_paro      VARCHAR(250),
    sin_produccion        BOOLEAN NOT NULL DEFAULT FALSE,
    pacas_atipica         BOOLEAN NOT NULL DEFAULT FALSE,
    horas_atipica         BOOLEAN NOT NULL DEFAULT FALSE
);

-- Grano: un registro de producción x un código/subcódigo de paro con horas > 0
CREATE TABLE fact_paro (
    paro_key          INTEGER PRIMARY KEY,
    produccion_key    INTEGER NOT NULL REFERENCES fact_produccion (produccion_key),
    fecha_key         INTEGER NOT NULL REFERENCES dim_fecha (fecha_key),
    maquina_key       INTEGER NOT NULL REFERENCES dim_maquina (maquina_key),
    turno_key         INTEGER NOT NULL REFERENCES dim_turno (turno_key),
    referencia_key    INTEGER NOT NULL REFERENCES dim_referencia (referencia_key),
    operario_key      INTEGER NOT NULL REFERENCES dim_operario (operario_key),
    codigo_paro_key   INTEGER NOT NULL REFERENCES dim_codigo_paro (codigo_paro_key),
    horas_paro        NUMERIC(10,6) NOT NULL CHECK (horas_paro > 0),
    area_involucrada  VARCHAR(40),                      -- solo en el código 5
    UNIQUE (produccion_key, codigo_paro_key)
);

-- ---------------------------------------------------------------------
-- ÍNDICES (PostgreSQL no indexa las llaves foráneas automáticamente)
-- ---------------------------------------------------------------------

-- Series de tiempo y comparativos por máquina (Grafana, Power BI)
CREATE INDEX ix_prod_fecha_maquina ON fact_produccion (fecha_key, maquina_key);
-- Análisis por turno y por referencia
CREATE INDEX ix_prod_turno       ON fact_produccion (turno_key);
CREATE INDEX ix_prod_referencia  ON fact_produccion (referencia_key);
-- Análisis del motivo de horas no trabajadas
CREATE INDEX ix_prod_motivo      ON fact_produccion (motivo_key);

-- Series de tiempo de paros por máquina
CREATE INDEX ix_paro_fecha_maquina ON fact_paro (fecha_key, maquina_key);
-- Pareto y drill-down por código/subcódigo
CREATE INDEX ix_paro_codigo        ON fact_paro (codigo_paro_key);