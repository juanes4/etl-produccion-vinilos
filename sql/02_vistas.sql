-- Vistas para los dashboards. El ETL las recrea en cada corrida.

-- Turnos con nombres de dimensiones y métricas derivadas.
-- horas_productivas: las horas de paro están DENTRO de las horas trabajadas.
-- horas_planeadas:   horas trabajadas menos paros programados (pausas, aseo, insumos...).
CREATE OR REPLACE VIEW vw_produccion AS
SELECT
  r.id_registro,
  r.fecha,
  f.anio, f.mes, f.nombre_mes, f.nombre_dia, f.es_fin_semana,
  m.nombre       AS maquina,
  o.nombre       AS operario,
  p.referencia,
  p.linea,
  p.volumen_cc,
  t.nombre       AS turno,
  r.pacas_producidas,
  r.horas_trabajadas,
  r.horas_paro,
  r.horas_paro_programado,
  r.horas_paro - r.horas_paro_programado               AS horas_paro_no_programado,
  GREATEST(r.horas_trabajadas - r.horas_paro, 0)        AS horas_productivas,
  r.horas_trabajadas - r.horas_paro_programado          AS horas_planeadas,
  r.num_paros,
  r.es_atipico,
  r.es_inconsistente,
  -- Filas válidas para calcular KPIs (tienen producción registrada y datos coherentes)
  (r.pacas_producidas IS NOT NULL AND r.horas_trabajadas > 0
     AND NOT r.es_atipico AND NOT r.es_inconsistente)  AS es_valido_kpi
FROM fact_produccion r
JOIN dim_fecha    f ON f.fecha       = r.fecha
JOIN dim_maquina  m ON m.id_maquina  = r.id_maquina
JOIN dim_operario o ON o.id_operario = r.id_operario
JOIN dim_producto p ON p.id_producto = r.id_producto
JOIN dim_turno    t ON t.id_turno    = r.id_turno;

-- Cada paro con el contexto del turno en que ocurrió.
CREATE OR REPLACE VIEW vw_paros AS
SELECT
  r.id_registro,
  r.fecha,
  m.nombre                        AS maquina,
  o.nombre                        AS operario,
  p.referencia,
  t.nombre                        AS turno,
  d.id_paro,
  CONCAT('[', LPAD(d.id_paro, 2, '0'), '] ', d.descripcion) AS tipo_paro,
  d.area_impacto,
  d.es_programado,
  fp.horas_paro,
  fp.horas_paro * 60              AS minutos_paro
FROM fact_paro fp
JOIN fact_produccion r ON r.id_registro = fp.id_registro
JOIN dim_paro     d ON d.id_paro     = fp.id_paro
JOIN dim_maquina  m ON m.id_maquina  = r.id_maquina
JOIN dim_operario o ON o.id_operario = r.id_operario
JOIN dim_producto p ON p.id_producto = r.id_producto
JOIN dim_turno    t ON t.id_turno    = r.id_turno;

-- KPIs diarios por máquina (base para tendencias).
CREATE OR REPLACE VIEW vw_kpi_diario_maquina AS
SELECT
  fecha,
  maquina,
  COUNT(*)                                   AS turnos,
  SUM(pacas_producidas)                      AS pacas,
  SUM(horas_trabajadas)                      AS horas_trabajadas,
  SUM(horas_paro)                            AS horas_paro,
  SUM(horas_paro_no_programado)              AS horas_paro_no_programado,
  SUM(pacas_producidas) / NULLIF(SUM(horas_trabajadas), 0)                         AS pacas_por_hora,
  SUM(horas_trabajadas - horas_paro) / NULLIF(SUM(horas_planeadas), 0)             AS disponibilidad
FROM vw_produccion
WHERE es_valido_kpi
GROUP BY fecha, maquina;
