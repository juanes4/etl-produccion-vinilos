-- Ejecutar UNA SOLA VEZ como root (MySQL Workbench o consola).
-- Cambia las contraseñas antes de ejecutarlo.

CREATE DATABASE IF NOT EXISTS temperas_vinilos
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Usuario que usa el ETL (lee y escribe solo en esta base)
CREATE USER IF NOT EXISTS 'etl_vinilos'@'localhost' IDENTIFIED BY 'CAMBIAR_CLAVE_ETL';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES, CREATE VIEW, SHOW VIEW, DROP
  ON temperas_vinilos.* TO 'etl_vinilos'@'localhost';

-- Usuario de solo lectura para Grafana
CREATE USER IF NOT EXISTS 'grafana'@'localhost' IDENTIFIED BY 'CAMBIAR_CLAVE_GRAFANA';
GRANT SELECT ON temperas_vinilos.* TO 'grafana'@'localhost';

FLUSH PRIVILEGES;
