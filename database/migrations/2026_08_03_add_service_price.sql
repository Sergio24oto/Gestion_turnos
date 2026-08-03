-- Agrega precio informativo a los servicios existentes.
-- Compatible con MySQL/Railway.
-- No borra servicios, no recrea tablas y no modifica turnos existentes.

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'servicios'
    AND COLUMN_NAME = 'precio'
);

SET @add_price_column := IF(
  @column_exists = 0,
  'ALTER TABLE servicios ADD COLUMN precio DECIMAL(10,2) NOT NULL DEFAULT 0.00',
  'SELECT ''La columna servicios.precio ya existe'' AS info'
);

PREPARE stmt FROM @add_price_column;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE servicios
SET precio = 0.00
WHERE precio IS NULL;

SET @check_exists := (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'servicios'
    AND CONSTRAINT_NAME = 'ck_servicios_precio_no_negativo'
    AND CONSTRAINT_TYPE = 'CHECK'
);

SET @add_price_check := IF(
  @check_exists = 0,
  'ALTER TABLE servicios ADD CONSTRAINT ck_servicios_precio_no_negativo CHECK (precio >= 0)',
  'SELECT ''El constraint ck_servicios_precio_no_negativo ya existe'' AS info'
);

PREPARE stmt FROM @add_price_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT id, nombre, duracion, activo, precio
FROM servicios
ORDER BY id;

SELECT COUNT(*) AS total_servicios
FROM servicios;
