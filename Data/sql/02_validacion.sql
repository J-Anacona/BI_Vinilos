-- Validación: totales de la base de datos frente a la fuente (Excel sin duplicados)
SELECT control,
       fuente,
       ROUND(base_datos, 3)           AS base_datos,
       ROUND(base_datos - fuente, 3)  AS diferencia,
       CASE WHEN ABS(base_datos - fuente) < 0.01 THEN 'OK' ELSE 'REVISAR' END AS estado
FROM (
    SELECT 1 AS orden, 'Registros de producción' AS control, 8166::numeric AS fuente,
           COUNT(*)::numeric AS base_datos FROM fact_produccion
    UNION ALL SELECT 2, 'Pacas producidas', 377759, SUM(pacas_producidas) FROM fact_produccion
    UNION ALL SELECT 3, 'Horas trabajadas', 37934.35, SUM(horas_trabajadas) FROM fact_produccion
    UNION ALL SELECT 4, 'Horas no trabajadas', 41343.85, SUM(horas_no_trabajadas) FROM fact_produccion
    UNION ALL SELECT 5, 'Horas de paro (fact_produccion)', 8431.535, SUM(tiempo_paro_horas) FROM fact_produccion
    UNION ALL SELECT 6, 'Horas de paro (fact_paro)', 8431.535, SUM(horas_paro) FROM fact_paro
    UNION ALL SELECT 7, 'Registros de paro (código con horas > 0)', 16482, COUNT(*) FROM fact_paro

    UNION ALL SELECT 10, 'Horas de paro 2022', 968.767, SUM(p.tiempo_paro_horas)
        FROM fact_produccion p JOIN dim_fecha d USING (fecha_key) WHERE d.anio = 2022
    UNION ALL SELECT 11, 'Horas de paro 2023', 2647.192, SUM(p.tiempo_paro_horas)
        FROM fact_produccion p JOIN dim_fecha d USING (fecha_key) WHERE d.anio = 2023
    UNION ALL SELECT 12, 'Horas de paro 2024', 3974.91, SUM(p.tiempo_paro_horas)
        FROM fact_produccion p JOIN dim_fecha d USING (fecha_key) WHERE d.anio = 2024
    UNION ALL SELECT 13, 'Horas de paro 2025', 840.667, SUM(p.tiempo_paro_horas)
        FROM fact_produccion p JOIN dim_fecha d USING (fecha_key) WHERE d.anio = 2025

    UNION ALL SELECT 20, 'Registros Vinilos_1', 1867, COUNT(*)
        FROM fact_produccion p JOIN dim_maquina m USING (maquina_key) WHERE m.maquina_nombre = 'Vinilos_1'
    UNION ALL SELECT 21, 'Registros Vinilos_2', 1249, COUNT(*)
        FROM fact_produccion p JOIN dim_maquina m USING (maquina_key) WHERE m.maquina_nombre = 'Vinilos_2'
    UNION ALL SELECT 22, 'Registros Vinilos_3', 2479, COUNT(*)
        FROM fact_produccion p JOIN dim_maquina m USING (maquina_key) WHERE m.maquina_nombre = 'Vinilos_3'
    UNION ALL SELECT 23, 'Registros Vinilos_4', 2571, COUNT(*)
        FROM fact_produccion p JOIN dim_maquina m USING (maquina_key) WHERE m.maquina_nombre = 'Vinilos_4'

    UNION ALL SELECT 30, 'Horas código 5 (Ajuste operativo)', 1813.693, SUM(f.horas_paro)
        FROM fact_paro f JOIN dim_codigo_paro c USING (codigo_paro_key) WHERE c.codigo = 5
    UNION ALL SELECT 31, 'Horas código 16 (Alimentación y aseo)', 2000.217, SUM(f.horas_paro)
        FROM fact_paro f JOIN dim_codigo_paro c USING (codigo_paro_key) WHERE c.codigo = 16
) t
ORDER BY orden;