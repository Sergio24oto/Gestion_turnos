-- Gestion diaria de ventas por peluquero.
-- Agrega datos operativos de venta al turno sin borrar ni recrear tablas.

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

DROP PROCEDURE IF EXISTS add_check_if_missing//
CREATE PROCEDURE add_check_if_missing(
  IN table_name_value VARCHAR(64),
  IN constraint_name_value VARCHAR(64),
  IN check_expression TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name_value
      AND CONSTRAINT_NAME = constraint_name_value
      AND CONSTRAINT_TYPE = 'CHECK'
  ) THEN
    SET @ddl := CONCAT(
      'ALTER TABLE `', table_name_value,
      '` ADD CONSTRAINT `', constraint_name_value,
      '` CHECK (', check_expression, ')'
    );
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

DELIMITER ;

CALL add_column_if_missing(
  'turnos',
  'venta_monto',
  'ALTER TABLE turnos ADD COLUMN venta_monto DECIMAL(10,2) NULL DEFAULT NULL AFTER no_show'
);

CALL add_column_if_missing(
  'turnos',
  'metodo_pago',
  'ALTER TABLE turnos ADD COLUMN metodo_pago VARCHAR(20) NOT NULL DEFAULT ''SIN_REGISTRAR'' AFTER venta_monto'
);

CALL add_column_if_missing(
  'turnos',
  'venta_actualizada_en',
  'ALTER TABLE turnos ADD COLUMN venta_actualizada_en DATETIME NULL DEFAULT NULL AFTER metodo_pago'
);

UPDATE turnos
SET venta_monto = precio_servicio
WHERE venta_monto IS NULL
  AND precio_servicio IS NOT NULL;

UPDATE turnos
SET metodo_pago = 'SIN_REGISTRAR'
WHERE metodo_pago IS NULL
   OR metodo_pago NOT IN ('SIN_REGISTRAR', 'EFECTIVO', 'TRANSFERENCIA');

CALL add_check_if_missing(
  'turnos',
  'ck_turnos_venta_monto_no_negativo',
  'venta_monto IS NULL OR venta_monto >= 0'
);

CALL add_check_if_missing(
  'turnos',
  'ck_turnos_metodo_pago_valido',
  'metodo_pago IN (''SIN_REGISTRAR'', ''EFECTIVO'', ''TRANSFERENCIA'')'
);

CALL add_index_if_missing(
  'turnos',
  'ix_turnos_fecha_estado_peluquero',
  'CREATE INDEX ix_turnos_fecha_estado_peluquero ON turnos (fecha, estado, peluquero_id)'
);

DROP PROCEDURE IF EXISTS add_index_if_missing;
DROP PROCEDURE IF EXISTS add_check_if_missing;
DROP PROCEDURE IF EXISTS add_column_if_missing;

SELECT
  COLUMN_NAME,
  COLUMN_TYPE,
  IS_NULLABLE,
  COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'turnos'
  AND COLUMN_NAME IN ('venta_monto', 'metodo_pago', 'venta_actualizada_en')
ORDER BY FIELD(COLUMN_NAME, 'venta_monto', 'metodo_pago', 'venta_actualizada_en');

SELECT
  metodo_pago,
  COUNT(*) AS turnos,
  COALESCE(SUM(venta_monto), 0) AS total
FROM turnos
GROUP BY metodo_pago;
