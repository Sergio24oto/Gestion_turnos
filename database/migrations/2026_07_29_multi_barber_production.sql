-- Migracion de produccion: multiples peluqueros
-- Fecha: 2026-07-29
-- Motor esperado: MySQL / Railway
--
-- Importante:
-- - No borra turnos existentes.
-- - No borra bloqueos existentes.
-- - No modifica tokens de cancelacion.
-- - No recrea tablas completas.
-- - No ejecuta DROP TABLE.
-- - No asume IDs fijos: obtiene el ID de Marcelo despues de insertarlo/verificarlo.
--
-- Ejecutar sobre la base de datos de produccion una sola vez, luego revisar las
-- consultas de verificacion al final antes de desplegar el backend/frontend nuevo.

START TRANSACTION;

-- 1. Crear la tabla peluqueros.
CREATE TABLE IF NOT EXISTS peluqueros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL,
    descripcion VARCHAR(180) NULL,
    foto_url VARCHAR(255) NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    orden INT NOT NULL DEFAULT 0,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_peluqueros_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Insertar al peluquero existente Marcelo Navarro sin duplicarlo.
INSERT INTO peluqueros (nombre, descripcion, foto_url, activo, orden)
SELECT
    'Marcelo Navarro',
    'Cortes clásicos, barba y atención unisex.',
    '/barbers/marcelo.jpeg',
    TRUE,
    1
WHERE NOT EXISTS (
    SELECT 1 FROM peluqueros WHERE nombre = 'Marcelo Navarro'
);

-- 3. Insertar a Jeremías Vivas sin duplicarlo.
INSERT INTO peluqueros (nombre, descripcion, foto_url, activo, orden)
SELECT
    'Jeremías Vivas',
    'Atención unisex, cortes actuales y turnos de apoyo.',
    '/barbers/jeremias.jpeg',
    TRUE,
    2
WHERE NOT EXISTS (
    SELECT 1 FROM peluqueros WHERE nombre = 'Jeremías Vivas'
);

-- Normalizar datos visuales si los peluqueros ya existian.
UPDATE peluqueros
SET
    descripcion = 'Cortes clásicos, barba y atención unisex.',
    foto_url = '/barbers/marcelo.jpeg',
    activo = TRUE,
    orden = 1
WHERE nombre = 'Marcelo Navarro';

UPDATE peluqueros
SET
    descripcion = 'Atención unisex, cortes actuales y turnos de apoyo.',
    foto_url = '/barbers/jeremias.jpeg',
    activo = TRUE,
    orden = 2
WHERE nombre = 'Jeremías Vivas';

-- Obtener el ID real de Marcelo sin asumir valores fijos.
SET @marcelo_id := (
    SELECT id
    FROM peluqueros
    WHERE nombre = 'Marcelo Navarro'
    ORDER BY id
    LIMIT 1
);

-- 4. Agregar peluquero_id a turnos si aun no existe.
SET @turnos_has_peluquero_id := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'turnos'
      AND COLUMN_NAME = 'peluquero_id'
);

SET @sql := IF(
    @turnos_has_peluquero_id = 0,
    'ALTER TABLE turnos ADD COLUMN peluquero_id INT NULL',
    'SELECT ''turnos.peluquero_id ya existe'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. Asignar a Marcelo los turnos historicos que actualmente no tienen peluquero.
UPDATE turnos
SET peluquero_id = @marcelo_id
WHERE peluquero_id IS NULL;

-- El modelo actual requiere turnos.peluquero_id NOT NULL.
ALTER TABLE turnos MODIFY peluquero_id INT NOT NULL;

-- 6 y 7. Bloqueos:
-- El modelo actual de bloqueos_horarios NO requiere peluquero_id.
-- Los bloqueos existentes se conservan como bloqueos globales por fecha + hora_inicio.
-- Por eso no se agrega columna a bloqueos_horarios en esta migracion.

-- 8 y 9. Reemplazar el indice unico anterior por el compatible con multiples peluqueros.
-- Indice viejo esperado:
--   uq_turnos_fecha_hora_activo(fecha_activa, hora_activa)
-- Ese indice impide que dos peluqueros distintos tengan turnos en el mismo horario.
--
-- Indice nuevo:
--   uq_turnos_peluquero_fecha_hora_activo(peluquero_id, fecha_activa, hora_activa)
-- Este indice impide duplicados para el mismo peluquero, pero permite el mismo horario
-- para peluqueros distintos. Como fecha_activa/hora_activa son NULL cuando el turno
-- esta Cancelado, la cancelacion sigue liberando el horario.

SET @old_turnos_index_exists := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'turnos'
      AND INDEX_NAME = 'uq_turnos_fecha_hora_activo'
);

SET @sql := IF(
    @old_turnos_index_exists > 0,
    'DROP INDEX uq_turnos_fecha_hora_activo ON turnos',
    'SELECT ''uq_turnos_fecha_hora_activo no existe'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @new_turnos_index_exists := (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'turnos'
      AND INDEX_NAME = 'uq_turnos_peluquero_fecha_hora_activo'
);

SET @sql := IF(
    @new_turnos_index_exists = 0,
    'CREATE UNIQUE INDEX uq_turnos_peluquero_fecha_hora_activo ON turnos (peluquero_id, fecha_activa, hora_activa)',
    'SELECT ''uq_turnos_peluquero_fecha_hora_activo ya existe'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 10. Crear la clave foranea turnos.peluquero_id -> peluqueros.id si aun no existe.
SET @fk_turnos_peluquero_exists := (
    SELECT COUNT(*)
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'turnos'
      AND COLUMN_NAME = 'peluquero_id'
      AND REFERENCED_TABLE_NAME = 'peluqueros'
);

SET @sql := IF(
    @fk_turnos_peluquero_exists = 0,
    'ALTER TABLE turnos ADD CONSTRAINT fk_turnos_peluquero FOREIGN KEY (peluquero_id) REFERENCES peluqueros(id)',
    'SELECT ''fk_turnos_peluquero ya existe'' AS info'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

COMMIT;

-- Consultas de verificacion.
SELECT
    'peluqueros' AS verificacion,
    id,
    nombre,
    descripcion,
    foto_url,
    activo,
    orden
FROM peluqueros
ORDER BY orden, id;

SELECT
    'turnos_sin_peluquero' AS verificacion,
    COUNT(*) AS cantidad
FROM turnos
WHERE peluquero_id IS NULL;

SELECT
    'turnos_por_peluquero' AS verificacion,
    p.id AS peluquero_id,
    p.nombre AS peluquero,
    COUNT(t.id) AS turnos
FROM peluqueros p
LEFT JOIN turnos t ON t.peluquero_id = p.id
GROUP BY p.id, p.nombre
ORDER BY p.orden, p.id;

SELECT
    'indices_turnos' AS verificacion,
    INDEX_NAME,
    NON_UNIQUE,
    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS columnas
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'turnos'
  AND INDEX_NAME IN (
      'uq_turnos_fecha_hora_activo',
      'uq_turnos_peluquero_fecha_hora_activo',
      'uq_turnos_cancelacion_token_hash'
  )
GROUP BY INDEX_NAME, NON_UNIQUE
ORDER BY INDEX_NAME;

SELECT
    'foreign_keys_turnos' AS verificacion,
    CONSTRAINT_NAME,
    COLUMN_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'turnos'
  AND COLUMN_NAME = 'peluquero_id';

SELECT
    'bloqueos_sin_cambios' AS verificacion,
    COUNT(*) AS bloqueos_totales
FROM bloqueos_horarios;
