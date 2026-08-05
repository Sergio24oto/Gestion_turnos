-- Expand migration: flexible service configuration by barber.
-- Safe to run on MySQL 8 / Railway MySQL. Do not run before backing up production.

DELIMITER //

DROP PROCEDURE IF EXISTS add_column_if_missing//
CREATE PROCEDURE add_column_if_missing(
  IN table_name_value VARCHAR(64),
  IN column_name_value VARCHAR(64),
  IN column_definition_value TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = table_name_value
      AND column_name = column_name_value
  ) THEN
    SET @ddl = CONCAT(
      'ALTER TABLE `',
      table_name_value,
      '` ADD COLUMN `',
      column_name_value,
      '` ',
      column_definition_value
    );
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END//

DROP PROCEDURE IF EXISTS add_check_if_missing//
CREATE PROCEDURE add_check_if_missing(
  IN table_name_value VARCHAR(64),
  IN constraint_name_value VARCHAR(64),
  IN check_sql_value TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = DATABASE()
      AND table_name = table_name_value
      AND constraint_name = constraint_name_value
      AND constraint_type = 'CHECK'
  ) THEN
    SET @ddl = CONCAT(
      'ALTER TABLE `',
      table_name_value,
      '` ADD CONSTRAINT `',
      constraint_name_value,
      '` CHECK (',
      check_sql_value,
      ')'
    );
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END//

DELIMITER ;

CALL add_column_if_missing('peluqueros', 'intervalo_turnos_minutos', 'INT NOT NULL DEFAULT 20');

UPDATE peluqueros
SET intervalo_turnos_minutos = 20
WHERE nombre = 'Marcelo Navarro';

UPDATE peluqueros
SET intervalo_turnos_minutos = 30,
    nombre = 'Jeremías Vivas',
    descripcion = COALESCE(descripcion, 'Atención unisex, cortes actuales y turnos de apoyo.'),
    foto_url = COALESCE(foto_url, '/barbers/jeremias.jpeg')
WHERE nombre IN ('Jeremías Vivas', 'Jeremias Vivas', 'Equipo Marcelo Navarro')
   OR orden = 2;

UPDATE peluqueros
SET intervalo_turnos_minutos = 20
WHERE intervalo_turnos_minutos IS NULL OR intervalo_turnos_minutos <= 0;

CALL add_column_if_missing('peluqueros_servicios', 'duracion_visible_minutos', 'INT NULL AFTER `precio`');
CALL add_column_if_missing('peluqueros_servicios', 'duracion_bloqueo_minutos', 'INT NOT NULL DEFAULT 20 AFTER `duracion_visible_minutos`');

ALTER TABLE peluqueros_servicios
  MODIFY COLUMN precio DECIMAL(10,2) NULL DEFAULT NULL;

UPDATE peluqueros_servicios ps
JOIN servicios s ON s.id = ps.servicio_id
SET ps.duracion_visible_minutos = s.duracion
WHERE ps.duracion_visible_minutos IS NULL
  AND s.duracion IS NOT NULL
  AND s.duracion > 0;

UPDATE peluqueros_servicios ps
JOIN peluqueros p ON p.id = ps.peluquero_id
SET ps.duracion_bloqueo_minutos = p.intervalo_turnos_minutos
WHERE ps.duracion_bloqueo_minutos IS NULL
   OR ps.duracion_bloqueo_minutos <= 0;

CALL add_column_if_missing('turnos', 'duracion_visible_servicio', 'INT NULL AFTER `precio_servicio`');
CALL add_column_if_missing('turnos', 'duracion_bloqueo_servicio', 'INT NOT NULL DEFAULT 20 AFTER `duracion_visible_servicio`');

ALTER TABLE turnos
  MODIFY COLUMN precio_servicio DECIMAL(10,2) NULL DEFAULT NULL;

UPDATE turnos t
JOIN servicios s ON s.id = t.servicio_id
SET t.duracion_visible_servicio = s.duracion
WHERE t.duracion_visible_servicio IS NULL
  AND s.duracion IS NOT NULL
  AND s.duracion > 0;

UPDATE turnos t
JOIN peluqueros p ON p.id = t.peluquero_id
SET t.duracion_bloqueo_servicio = p.intervalo_turnos_minutos
WHERE t.duracion_bloqueo_servicio IS NULL
   OR t.duracion_bloqueo_servicio <= 0;

CALL add_check_if_missing('peluqueros', 'ck_peluqueros_intervalo_turnos_positivo', 'intervalo_turnos_minutos > 0');
CALL add_check_if_missing('peluqueros_servicios', 'ck_peluqueros_servicios_precio_nullable_no_negativo', 'precio IS NULL OR precio >= 0');
CALL add_check_if_missing('peluqueros_servicios', 'ck_peluqueros_servicios_duracion_visible_positiva', 'duracion_visible_minutos IS NULL OR duracion_visible_minutos > 0');
CALL add_check_if_missing('peluqueros_servicios', 'ck_peluqueros_servicios_duracion_bloqueo_positiva', 'duracion_bloqueo_minutos > 0');
CALL add_check_if_missing('turnos', 'ck_turnos_precio_servicio_no_negativo', 'precio_servicio IS NULL OR precio_servicio >= 0');
CALL add_check_if_missing('turnos', 'ck_turnos_duracion_visible_servicio_positiva', 'duracion_visible_servicio IS NULL OR duracion_visible_servicio > 0');
CALL add_check_if_missing('turnos', 'ck_turnos_duracion_bloqueo_servicio_positiva', 'duracion_bloqueo_servicio > 0');

DROP PROCEDURE add_check_if_missing;
DROP PROCEDURE add_column_if_missing;

-- Verification queries.
SELECT id, nombre, intervalo_turnos_minutos
FROM peluqueros
ORDER BY orden, id;

SELECT
  p.nombre AS peluquero,
  s.nombre AS servicio,
  ps.precio,
  ps.duracion_visible_minutos,
  ps.duracion_bloqueo_minutos,
  ps.activo
FROM peluqueros_servicios ps
JOIN peluqueros p ON p.id = ps.peluquero_id
JOIN servicios s ON s.id = ps.servicio_id
ORDER BY p.orden, p.id, s.id;

SELECT
  COUNT(*) AS turnos_total,
  SUM(duracion_bloqueo_servicio IS NULL OR duracion_bloqueo_servicio <= 0) AS turnos_con_bloqueo_invalido,
  SUM(precio_servicio < 0) AS turnos_con_precio_negativo
FROM turnos;

SELECT
  COUNT(*) AS combinaciones_total,
  SUM(precio IS NULL) AS combinaciones_a_consultar,
  SUM(duracion_visible_minutos IS NULL) AS combinaciones_duracion_a_consultar,
  SUM(duracion_bloqueo_minutos <= 0) AS combinaciones_bloqueo_invalido
FROM peluqueros_servicios;
