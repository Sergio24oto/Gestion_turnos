-- Expand migration: administrative CRUD fields for servicios.
-- Do not run in production without backup and deployment plan.

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

DELIMITER ;

CALL add_column_if_missing('servicios', 'descripcion', 'VARCHAR(255) NULL AFTER `nombre`');
CALL add_column_if_missing('servicios', 'categoria', 'VARCHAR(80) NULL AFTER `descripcion`');
CALL add_column_if_missing('servicios', 'creado_en', 'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP');
CALL add_column_if_missing('servicios', 'actualizado_en', 'DATETIME NULL DEFAULT NULL');

DROP PROCEDURE add_column_if_missing;

-- Verification queries.
SELECT
  column_name,
  column_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'servicios'
  AND column_name IN ('descripcion', 'categoria', 'creado_en', 'actualizado_en')
ORDER BY ordinal_position;

SELECT
  s.id,
  s.nombre,
  s.descripcion,
  s.categoria,
  s.activo,
  COUNT(DISTINCT ps.peluquero_id) AS profesionales_asignados,
  s.creado_en,
  s.actualizado_en
FROM servicios s
LEFT JOIN peluqueros_servicios ps ON ps.servicio_id = s.id
GROUP BY s.id, s.nombre, s.descripcion, s.categoria, s.activo, s.creado_en, s.actualizado_en
ORDER BY s.activo DESC, s.nombre;
