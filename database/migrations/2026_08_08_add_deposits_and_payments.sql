-- Expand migration: señas, reservas pendientes de pago y tabla de pagos.
-- Compatible con MySQL/Railway. No borra turnos, bloqueos ni tokens existentes.

SET @db_name := DATABASE();

-- 1) Configuración de seña por servicio-profesional.
SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'peluqueros_servicios'
    AND COLUMN_NAME = 'requiere_senia'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE peluqueros_servicios ADD COLUMN requiere_senia BOOLEAN NOT NULL DEFAULT FALSE AFTER activo',
  'SELECT ''peluqueros_servicios.requiere_senia ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'peluqueros_servicios'
    AND COLUMN_NAME = 'tipo_senia'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE peluqueros_servicios ADD COLUMN tipo_senia ENUM(''fijo'', ''porcentaje'') NULL AFTER requiere_senia',
  'SELECT ''peluqueros_servicios.tipo_senia ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'peluqueros_servicios'
    AND COLUMN_NAME = 'monto_senia'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE peluqueros_servicios ADD COLUMN monto_senia DECIMAL(10,2) NULL AFTER tipo_senia',
  'SELECT ''peluqueros_servicios.monto_senia ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'peluqueros_servicios'
    AND COLUMN_NAME = 'porcentaje_senia'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE peluqueros_servicios ADD COLUMN porcentaje_senia DECIMAL(5,2) NULL AFTER monto_senia',
  'SELECT ''peluqueros_servicios.porcentaje_senia ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE peluqueros_servicios
SET requiere_senia = FALSE
WHERE requiere_senia IS NULL;

-- 2) Estados nuevos para turnos. Conserva valores legacy existentes.
ALTER TABLE turnos
  MODIFY estado ENUM(
    'Confirmado',
    'Cancelado',
    'Completado',
    'PENDING_PAYMENT',
    'CONFIRMED',
    'CANCELLED',
    'EXPIRED',
    'COMPLETED'
  ) NOT NULL DEFAULT 'CONFIRMED';

-- 3) Campos históricos de seña en turnos.
SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND COLUMN_NAME = 'monto_senia'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE turnos ADD COLUMN monto_senia DECIMAL(10,2) NULL AFTER duracion_bloqueo_servicio',
  'SELECT ''turnos.monto_senia ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND COLUMN_NAME = 'saldo_pendiente'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE turnos ADD COLUMN saldo_pendiente DECIMAL(10,2) NULL AFTER monto_senia',
  'SELECT ''turnos.saldo_pendiente ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND COLUMN_NAME = 'payment_expires_at'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE turnos ADD COLUMN payment_expires_at DATETIME NULL AFTER saldo_pendiente',
  'SELECT ''turnos.payment_expires_at ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND COLUMN_NAME = 'payment_status_token_hash'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE turnos ADD COLUMN payment_status_token_hash VARCHAR(64) NULL AFTER payment_expires_at',
  'SELECT ''turnos.payment_status_token_hash ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @payment_status_token_index_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND INDEX_NAME = 'ux_turnos_payment_status_token_hash'
);
SET @sql := IF(
  @payment_status_token_index_exists = 0,
  'CREATE UNIQUE INDEX ux_turnos_payment_status_token_hash ON turnos (payment_status_token_hash)',
  'SELECT ''ux_turnos_payment_status_token_hash ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND COLUMN_NAME = 'no_show'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE turnos ADD COLUMN no_show BOOLEAN NOT NULL DEFAULT FALSE AFTER payment_status_token_hash',
  'SELECT ''turnos.no_show ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4) Reemplazar expresión de columnas activas para liberar CANCELLED y EXPIRED.
-- Las reservas PENDING_PAYMENT vencidas se marcan EXPIRED on-demand desde la app.
-- Antes de eliminar el índice compuesto, garantizar un índice independiente
-- que pueda soportar la FK turnos.peluquero_id.
SET @barber_fk_support_index_exists := (
  SELECT COUNT(DISTINCT INDEX_NAME)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND COLUMN_NAME = 'peluquero_id'
    AND SEQ_IN_INDEX = 1
    AND INDEX_NAME <> 'uq_turnos_peluquero_fecha_hora_activo'
);
SET @sql := IF(
  @barber_fk_support_index_exists = 0,
  'CREATE INDEX ix_turnos_peluquero_id ON turnos (peluquero_id)',
  'SELECT ''turnos.peluquero_id ya tiene índice de soporte para la FK'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @index_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND INDEX_NAME = 'uq_turnos_peluquero_fecha_hora_activo'
);
SET @sql := IF(
  @index_exists > 0,
  'ALTER TABLE turnos DROP INDEX uq_turnos_peluquero_fecha_hora_activo',
  'SELECT ''uq_turnos_peluquero_fecha_hora_activo no existe antes de modificar columnas generadas'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

ALTER TABLE turnos
  MODIFY fecha_activa DATE
    GENERATED ALWAYS AS (
      CASE
        WHEN estado NOT IN ('Cancelado', 'CANCELLED', 'EXPIRED') THEN fecha
        ELSE NULL
      END
    ) STORED;

ALTER TABLE turnos
  MODIFY hora_activa TIME
    GENERATED ALWAYS AS (
      CASE
        WHEN estado NOT IN ('Cancelado', 'CANCELLED', 'EXPIRED') THEN hora_inicio
        ELSE NULL
      END
    ) STORED;

SET @active_unique_index_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'turnos'
    AND INDEX_NAME = 'uq_turnos_peluquero_fecha_hora_activo'
);
SET @sql := IF(
  @active_unique_index_exists = 0,
  'CREATE UNIQUE INDEX uq_turnos_peluquero_fecha_hora_activo ON turnos (peluquero_id, fecha_activa, hora_activa)',
  'SELECT ''uq_turnos_peluquero_fecha_hora_activo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 5) Tabla de pagos. Un turno puede tener múltiples intentos.
CREATE TABLE IF NOT EXISTS pagos (
  id INT NOT NULL AUTO_INCREMENT,
  turno_id INT NOT NULL,
  proveedor VARCHAR(40) NOT NULL DEFAULT 'mercadopago',
  external_payment_id VARCHAR(120) NULL,
  external_preference_id VARCHAR(120) NULL,
  checkout_url VARCHAR(500) NULL,
  monto DECIMAL(10,2) NOT NULL,
  moneda VARCHAR(3) NOT NULL DEFAULT 'ARS',
  estado ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'REFUNDED') NOT NULL DEFAULT 'PENDING',
  raw_status TEXT NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en DATETIME NULL,
  aprobado_en DATETIME NULL,
  PRIMARY KEY (id),
  INDEX ix_pagos_turno_id (turno_id),
  UNIQUE INDEX ux_pagos_external_payment_id (external_payment_id),
  INDEX ix_pagos_external_preference_id (external_preference_id),
  CONSTRAINT fk_pagos_turno FOREIGN KEY (turno_id) REFERENCES turnos(id)
);

-- Asegura que external_payment_id sea UNIQUE si una ejecución previa creó un índice común.
SET @column_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'pagos'
    AND COLUMN_NAME = 'checkout_url'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE pagos ADD COLUMN checkout_url VARCHAR(500) NULL AFTER external_preference_id',
  'SELECT ''pagos.checkout_url ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @plain_payment_index_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'pagos'
    AND INDEX_NAME = 'ix_pagos_external_payment_id'
);
SET @sql := IF(
  @plain_payment_index_exists > 0,
  'ALTER TABLE pagos DROP INDEX ix_pagos_external_payment_id',
  'SELECT ''ix_pagos_external_payment_id no existe o ya fue reemplazado'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @unique_payment_index_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = @db_name
    AND TABLE_NAME = 'pagos'
    AND INDEX_NAME = 'ux_pagos_external_payment_id'
);
SET @sql := IF(
  @unique_payment_index_exists = 0,
  'CREATE UNIQUE INDEX ux_pagos_external_payment_id ON pagos (external_payment_id)',
  'SELECT ''ux_pagos_external_payment_id ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 6) Checks idempotentes cuando la versión de MySQL los soporta.
SET @check_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = @db_name
    AND CONSTRAINT_NAME = 'ck_peluqueros_servicios_monto_senia_no_negativo'
);
SET @sql := IF(
  @check_exists = 0,
  'ALTER TABLE peluqueros_servicios ADD CONSTRAINT ck_peluqueros_servicios_monto_senia_no_negativo CHECK (monto_senia IS NULL OR monto_senia >= 0)',
  'SELECT ''ck_peluqueros_servicios_monto_senia_no_negativo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @check_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = @db_name
    AND CONSTRAINT_NAME = 'ck_peluqueros_servicios_porcentaje_senia_valido'
);
SET @sql := IF(
  @check_exists = 0,
  'ALTER TABLE peluqueros_servicios ADD CONSTRAINT ck_peluqueros_servicios_porcentaje_senia_valido CHECK (porcentaje_senia IS NULL OR (porcentaje_senia > 0 AND porcentaje_senia <= 100))',
  'SELECT ''ck_peluqueros_servicios_porcentaje_senia_valido ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @check_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = @db_name
    AND CONSTRAINT_NAME = 'ck_peluqueros_servicios_senia_coherente'
);
SET @sql := IF(
  @check_exists = 0,
  'ALTER TABLE peluqueros_servicios ADD CONSTRAINT ck_peluqueros_servicios_senia_coherente CHECK (requiere_senia = FALSE OR (tipo_senia = ''fijo'' AND monto_senia IS NOT NULL AND monto_senia > 0) OR (tipo_senia = ''porcentaje'' AND porcentaje_senia IS NOT NULL AND porcentaje_senia > 0 AND porcentaje_senia <= 100))',
  'SELECT ''ck_peluqueros_servicios_senia_coherente ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @check_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = @db_name
    AND CONSTRAINT_NAME = 'ck_turnos_monto_senia_no_negativo'
);
SET @sql := IF(
  @check_exists = 0,
  'ALTER TABLE turnos ADD CONSTRAINT ck_turnos_monto_senia_no_negativo CHECK (monto_senia IS NULL OR monto_senia >= 0)',
  'SELECT ''ck_turnos_monto_senia_no_negativo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @check_exists := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = @db_name
    AND CONSTRAINT_NAME = 'ck_turnos_saldo_pendiente_no_negativo'
);
SET @sql := IF(
  @check_exists = 0,
  'ALTER TABLE turnos ADD CONSTRAINT ck_turnos_saldo_pendiente_no_negativo CHECK (saldo_pendiente IS NULL OR saldo_pendiente >= 0)',
  'SELECT ''ck_turnos_saldo_pendiente_no_negativo ya existe'' AS info'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Verificaciones.
SELECT estado, COUNT(*)
FROM turnos
GROUP BY estado;

SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = @db_name
  AND (
    (TABLE_NAME = 'peluqueros_servicios' AND COLUMN_NAME IN ('requiere_senia', 'tipo_senia', 'monto_senia', 'porcentaje_senia'))
    OR (TABLE_NAME = 'turnos' AND COLUMN_NAME IN ('monto_senia', 'saldo_pendiente', 'payment_expires_at', 'payment_status_token_hash', 'no_show'))
    OR (TABLE_NAME = 'pagos' AND COLUMN_NAME IN ('external_payment_id', 'external_preference_id', 'checkout_url'))
  )
ORDER BY TABLE_NAME, ORDINAL_POSITION;

SELECT COUNT(*) AS servicios_con_senia_inicial
FROM peluqueros_servicios
WHERE requiere_senia = TRUE;

SELECT COUNT(*) AS pagos_creados
FROM pagos;
