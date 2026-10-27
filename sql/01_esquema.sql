-- Modelo estrella. El ETL ejecuta este script en cada corrida (es idempotente).
-- Las columnas de nombres usan collation sensible a mayúsculas/tildes para que
-- coincidan exactamente con los valores limpiados en Python.

CREATE TABLE IF NOT EXISTS dim_fecha (
  fecha          DATE        NOT NULL PRIMARY KEY,
  anio           SMALLINT    NOT NULL,
  trimestre      TINYINT     NOT NULL,
  mes            TINYINT     NOT NULL,
  nombre_mes     VARCHAR(12) NOT NULL,
  semana_iso     TINYINT     NOT NULL,
  dia_semana     TINYINT     NOT NULL COMMENT '1 = lunes ... 7 = domingo',
  nombre_dia     VARCHAR(12) NOT NULL,
  es_fin_semana  BOOLEAN     NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_maquina (
  id_maquina  SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre      VARCHAR(50) COLLATE utf8mb4_0900_as_cs NOT NULL,
  UNIQUE KEY uq_maquina (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_operario (
  id_operario  SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre       VARCHAR(100) COLLATE utf8mb4_0900_as_cs NOT NULL,
  UNIQUE KEY uq_operario (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_producto (
  id_producto  SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  referencia   VARCHAR(100) COLLATE utf8mb4_0900_as_cs NOT NULL,
  linea        VARCHAR(60)  NOT NULL,
  volumen_cc   SMALLINT UNSIGNED NULL,
  num_colores  TINYINT  UNSIGNED NULL,
  UNIQUE KEY uq_producto (referencia)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_turno (
  id_turno        SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nombre          VARCHAR(50) COLLATE utf8mb4_0900_as_cs NOT NULL,
  hora_inicio     TIME NULL,
  hora_fin        TIME NULL,
  duracion_horas  DECIMAL(4,2) NULL,
  UNIQUE KEY uq_turno (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dim_paro (
  id_paro        TINYINT UNSIGNED NOT NULL PRIMARY KEY COMMENT 'Código de paro 1-18',
  descripcion    VARCHAR(120) NOT NULL,
  area_impacto   VARCHAR(60)  NOT NULL,
  es_programado  BOOLEAN      NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Un renglón por turno de máquina
CREATE TABLE IF NOT EXISTS fact_produccion (
  id_registro            INT UNSIGNED NOT NULL PRIMARY KEY,
  fila_excel             INT UNSIGNED NOT NULL COMMENT 'Primera fila del turno en el Excel (trazabilidad)',
  fecha                  DATE NOT NULL,
  id_maquina             SMALLINT UNSIGNED NOT NULL,
  id_operario            SMALLINT UNSIGNED NOT NULL,
  id_producto            SMALLINT UNSIGNED NOT NULL,
  id_turno               SMALLINT UNSIGNED NOT NULL,
  pacas_producidas       DECIMAL(10,2) NULL COMMENT 'NULL = no se registró (no es lo mismo que 0)',
  horas_trabajadas       DECIMAL(5,2)  NULL,
  horas_paro             DECIMAL(9,6)  NOT NULL DEFAULT 0,
  horas_paro_programado  DECIMAL(9,6)  NOT NULL DEFAULT 0,
  num_paros              TINYINT UNSIGNED NOT NULL DEFAULT 0,
  es_atipico             BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Pacas/hora fuera del rango configurado',
  es_inconsistente       BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Horas de paro > horas trabajadas',
  KEY ix_fecha_maquina (fecha, id_maquina),
  CONSTRAINT fk_prod_fecha    FOREIGN KEY (fecha)       REFERENCES dim_fecha (fecha),
  CONSTRAINT fk_prod_maquina  FOREIGN KEY (id_maquina)  REFERENCES dim_maquina (id_maquina),
  CONSTRAINT fk_prod_operario FOREIGN KEY (id_operario) REFERENCES dim_operario (id_operario),
  CONSTRAINT fk_prod_producto FOREIGN KEY (id_producto) REFERENCES dim_producto (id_producto),
  CONSTRAINT fk_prod_turno    FOREIGN KEY (id_turno)    REFERENCES dim_turno (id_turno)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Un renglón por (turno, código de paro)
CREATE TABLE IF NOT EXISTS fact_paro (
  id_registro  INT UNSIGNED NOT NULL,
  id_paro      TINYINT UNSIGNED NOT NULL,
  horas_paro   DECIMAL(9,6) NOT NULL,
  PRIMARY KEY (id_registro, id_paro),
  KEY ix_paro (id_paro),
  CONSTRAINT fk_paro_registro FOREIGN KEY (id_registro) REFERENCES fact_produccion (id_registro) ON DELETE CASCADE,
  CONSTRAINT fk_paro_codigo   FOREIGN KEY (id_paro)     REFERENCES dim_paro (id_paro)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Bitácora de ejecuciones del ETL
CREATE TABLE IF NOT EXISTS etl_ejecuciones (
  id_ejecucion   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  inicio         DATETIME NOT NULL,
  fin            DATETIME NULL,
  estado         ENUM('EXITO', 'SIN_CAMBIOS', 'ERROR') NOT NULL,
  archivo        VARCHAR(255) NOT NULL,
  hash_archivo   CHAR(64) NULL,
  filas_leidas   INT UNSIGNED NULL,
  registros      INT UNSIGNED NULL,
  paros          INT UNSIGNED NULL,
  calidad        JSON NULL,
  mensaje        TEXT NULL,
  KEY ix_estado_inicio (estado, inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
