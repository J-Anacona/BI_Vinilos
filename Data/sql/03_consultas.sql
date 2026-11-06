-- C1. % de productividad por máquina y mes (misma fórmula del informe P-MTO-22)
SELECT d.anio_mes,
       m.maquina_nombre,
       ROUND(SUM(p.horas_trabajadas), 1)  AS horas_trabajadas,
       ROUND(SUM(p.tiempo_paro_horas), 1) AS horas_paro,
       ROUND(100.0 * (SUM(p.horas_trabajadas) - SUM(p.tiempo_paro_horas))
             / NULLIF(SUM(p.horas_trabajadas), 0), 1) AS pct_productividad
FROM fact_produccion p
JOIN dim_fecha d   USING (fecha_key)
JOIN dim_maquina m USING (maquina_key)
GROUP BY d.anio_mes, m.maquina_nombre
ORDER BY d.anio_mes, m.maquina_nombre;

-- C2. Pareto de causas de paro: horas, % y % acumulado
WITH causas AS (
    SELECT c.codigo_nombre, SUM(f.horas_paro) AS horas
    FROM fact_paro f
    JOIN dim_codigo_paro c USING (codigo_paro_key)
    GROUP BY c.codigo_nombre
)
SELECT codigo_nombre,
       ROUND(horas, 1) AS horas,
       ROUND(100.0 * horas / SUM(horas) OVER (), 1) AS pct,
       ROUND(100.0 * SUM(horas) OVER (ORDER BY horas DESC, codigo_nombre)
             / SUM(horas) OVER (), 1) AS pct_acumulado
FROM causas
ORDER BY horas DESC;

-- C3. Ranking de máquinas por horas de paro en cada año (RANK)
SELECT d.anio,
       m.maquina_nombre,
       ROUND(SUM(f.horas_paro), 1) AS horas_paro,
       RANK() OVER (PARTITION BY d.anio ORDER BY SUM(f.horas_paro) DESC) AS posicion
FROM fact_paro f
JOIN dim_fecha d   USING (fecha_key)
JOIN dim_maquina m USING (maquina_key)
GROUP BY d.anio, m.maquina_nombre
ORDER BY d.anio, posicion;

-- C4. Comparativo: productividad de cada mes frente al mismo mes del año anterior (LAG)
WITH mensual AS (
    SELECT d.anio, d.mes, d.nombre_mes,
           100.0 * (SUM(p.horas_trabajadas) - SUM(p.tiempo_paro_horas))
           / NULLIF(SUM(p.horas_trabajadas), 0) AS prod
    FROM fact_produccion p
    JOIN dim_fecha d USING (fecha_key)
    GROUP BY d.anio, d.mes, d.nombre_mes
)
SELECT anio, nombre_mes,
       ROUND(prod, 1) AS pct_productividad,
       ROUND(LAG(prod) OVER (PARTITION BY mes ORDER BY anio), 1) AS mismo_mes_anio_anterior,
       ROUND(prod - LAG(prod) OVER (PARTITION BY mes ORDER BY anio), 1) AS variacion_pp
FROM mensual
ORDER BY anio, mes;

-- C5. Horas de paro por máquina con media móvil de 3 meses (ventana deslizante)
WITH mensual AS (
    SELECT m.maquina_nombre, d.anio_mes,
           SUM(p.tiempo_paro_horas) AS horas_paro
    FROM fact_produccion p
    JOIN dim_fecha d   USING (fecha_key)
    JOIN dim_maquina m USING (maquina_key)
    GROUP BY m.maquina_nombre, d.anio_mes
)
SELECT maquina_nombre, anio_mes,
       ROUND(horas_paro, 1) AS horas_paro,
       ROUND(AVG(horas_paro) OVER (PARTITION BY maquina_nombre ORDER BY anio_mes
                                   ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS media_movil_3m
FROM mensual
ORDER BY maquina_nombre, anio_mes;

-- C6. Los 3 subcódigos con más horas dentro de los códigos 1, 3 y 5 (ROW_NUMBER)
SELECT *
FROM (
    SELECT c.codigo,
           c.subcodigo,
           ROUND(SUM(f.horas_paro), 1) AS horas,
           ROW_NUMBER() OVER (PARTITION BY c.codigo ORDER BY SUM(f.horas_paro) DESC) AS pos
    FROM fact_paro f
    JOIN dim_codigo_paro c USING (codigo_paro_key)
    WHERE c.codigo IN (1, 3, 5)
      AND c.subcodigo <> 'Sin subcódigo'
    GROUP BY c.codigo, c.subcodigo
) t
WHERE pos <= 3
ORDER BY codigo, pos;

-- C7. Horas no trabajadas por motivo y año, con su % dentro del año
SELECT d.anio,
       mo.catalogo,
       mo.nombre AS motivo,
       ROUND(SUM(p.horas_no_trabajadas), 0) AS horas_no_trabajadas,
       ROUND(100.0 * SUM(p.horas_no_trabajadas)
             / SUM(SUM(p.horas_no_trabajadas)) OVER (PARTITION BY d.anio), 1) AS pct_del_anio
FROM fact_produccion p
JOIN dim_fecha d                USING (fecha_key)
JOIN dim_motivo_no_trabajo mo   USING (motivo_key)
WHERE mo.nombre <> 'No aplica'
  AND p.horas_no_trabajadas > 0
GROUP BY d.anio, mo.catalogo, mo.nombre
ORDER BY d.anio, horas_no_trabajadas DESC;