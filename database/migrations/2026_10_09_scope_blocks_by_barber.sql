-- Hace que los bloqueos de agenda sean por peluquero y no globales por fecha/hora.
-- Los bloqueos historicos no tenian peluquero; se asignan a Marcelo Navarro como valor compatible.

DELIMITER //

DROP PROCEDURE IF EXISTS add_column_if_missing//
CREATE PROCEDURE add_column_if_missing(
  IN table_name_value VARCHAR(64),
  IN column_name_value VARCHAR(64),
  IN ddl_value TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name_value
      AND COLUMN_NAME = column_name_value
  ) THEN
    SET @ddl := ddl_value;
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END//

DROP PROCEDURE IF EXISTS drop_index_if_exists//
CREATE PROCEDURE drop_index_if_exists(
  IN table_name_value VARCHAR(64),
  IN index_name_value VARCHAR(64)
)
BEGIN
  IF EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name_value
      AND INDEX_NAME = index_name_value
  ) THEN
    SET @ddl := CONCAT('ALTER TABLE `', table_name_value, '` DROP INDEX `', index_name_value, '`');
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END//

DROP PROCEDURE IF EXISTS add_index_if_missing//
CREATE PROCEDURE add_index_if_missing(
  IN table_name_value VARCHAR(64),
  IN index_name_value VARCHAR(64),
  IN ddl_value TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name_value
      AND INDEX_NAME = index_name_value
  ) THEN
    SET @ddl := ddl_value;
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END//

DROP PROCEDURE IF EXISTS add_fk_if_missing//
CREATE PROCEDURE add_fk_if_missing(
  IN table_name_value VARCHAR(64),
  IN constraint_name_value VARCHAR(64),
  IN ddl_value TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name_value
      AND CONSTRAINT_NAME = constraint_name_value
      AND CONSTRAINT_TYPE = 'FOREIGN KEY'
  ) THEN
    SET @ddl := ddl_value;
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END//

DELIMITER ;

CALL add_column_if_missing(
  'bloqueos_horarios',
  'peluquero_id',
  'ALTER TABLE bloqueos_horarios ADD COLUMN peluquero_id INT NULL AFTER id'
);

SET @default_barber_id := (
  SELECT id
  FROM peluqueros
  ORDER BY CASE WHEN nombre = 'Marcelo Navarro' THEN 0 ELSE 1 END, orden, id
  LIMIT 1
);

UPDATE bloqueos_horarios
SET peluquero_id = @default_barber_id
WHERE peluquero_id IS NULL;

ALTER TABLE bloqueos_horarios
  MODIFY peluquero_id INT NOT NULL;

CALL drop_index_if_exists('bloqueos_horarios', 'uq_bloqueos_fecha_hora');

CALL add_index_if_missing(
  'bloqueos_horarios',
  'ix_bloqueos_peluquero_id',
  'CREATE INDEX ix_bloqueos_peluquero_id ON bloqueos_horarios (peluquero_id)'
);

CALL add_index_if_missing(
  'bloqueos_horarios',
  'uq_bloqueos_peluquero_fecha_hora',
  'CREATE UNIQUE INDEX uq_bloqueos_peluquero_fecha_hora ON bloqueos_horarios (peluquero_id, fecha, hora_inicio)'
);

CALL add_fk_if_missing(
  'bloqueos_horarios',
  'fk_bloqueos_peluquero',
  'ALTER TABLE bloqueos_horarios ADD CONSTRAINT fk_bloqueos_peluquero FOREIGN KEY (peluquero_id) REFERENCES peluqueros(id)'
);

DROP PROCEDURE IF EXISTS add_fk_if_missing;
DROP PROCEDURE IF EXISTS add_index_if_missing;
DROP PROCEDURE IF EXISTS drop_index_if_exists;
DROP PROCEDURE IF EXISTS add_column_if_missing;

SELECT
  COLUMN_NAME,
  COLUMN_TYPE,
  IS_NULLABLE,
  COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'bloqueos_horarios'
  AND COLUMN_NAME IN ('peluquero_id', 'fecha', 'hora_inicio')
ORDER BY FIELD(COLUMN_NAME, 'peluquero_id', 'fecha', 'hora_inicio');

SELECT
  p.nombre AS peluquero,
  COUNT(b.id) AS bloqueos
FROM peluqueros p
LEFT JOIN bloqueos_horarios b ON b.peluquero_id = p.id
GROUP BY p.id, p.nombre
ORDER BY p.orden, p.id;
