-- CONTRACT FUTURA: eliminar servicios.precio legacy.
-- NO ejecutar todavia.
-- Ejecutar solo despues de verificar que ninguna version desplegada del backend
-- lee, escribe o valida servicios.precio.
-- La fuente vigente debe ser peluqueros_servicios.precio y la historica turnos.precio_servicio.

SET @legacy_price_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'servicios'
    AND COLUMN_NAME = 'precio'
);

SET @legacy_check_exists := (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'servicios'
    AND CONSTRAINT_NAME = 'ck_servicios_precio_no_negativo'
    AND CONSTRAINT_TYPE = 'CHECK'
);

SET @drop_legacy_check := IF(
  @legacy_check_exists = 1,
  'ALTER TABLE servicios DROP CHECK ck_servicios_precio_no_negativo',
  'SELECT ''El constraint ck_servicios_precio_no_negativo no existe'' AS info'
);

PREPARE stmt FROM @drop_legacy_check;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @drop_legacy_price := IF(
  @legacy_price_exists = 1,
  'ALTER TABLE servicios DROP COLUMN precio',
  'SELECT ''La columna servicios.precio ya fue eliminada'' AS info'
);

PREPARE stmt FROM @drop_legacy_price;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT
  COLUMN_NAME,
  COLUMN_TYPE,
  IS_NULLABLE,
  COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'servicios'
  AND COLUMN_NAME = 'precio';
