-- EXPAND: agrega precios por combinacion peluquero + servicio.
-- No ejecutar en produccion sin backup y ventana de despliegue controlada.
-- No borra tablas, no borra turnos, no elimina servicios.precio legacy.

CREATE TABLE IF NOT EXISTS peluqueros_servicios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  peluquero_id INT NOT NULL,
  servicio_id INT NOT NULL,
  precio DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en DATETIME NULL,
  CONSTRAINT uq_peluqueros_servicios_peluquero_servicio UNIQUE (peluquero_id, servicio_id),
  CONSTRAINT ck_peluqueros_servicios_precio_no_negativo CHECK (precio >= 0),
  CONSTRAINT fk_peluqueros_servicios_peluquero FOREIGN KEY (peluquero_id) REFERENCES peluqueros(id),
  CONSTRAINT fk_peluqueros_servicios_servicio FOREIGN KEY (servicio_id) REFERENCES servicios(id)
);

SET @turnos_precio_servicio_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'turnos'
    AND COLUMN_NAME = 'precio_servicio'
);

SET @add_turnos_precio_servicio := IF(
  @turnos_precio_servicio_exists = 0,
  'ALTER TABLE turnos ADD COLUMN precio_servicio DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER peluquero_id',
  'SELECT ''La columna turnos.precio_servicio ya existe'' AS info'
);

PREPARE stmt FROM @add_turnos_precio_servicio;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

INSERT INTO peluqueros_servicios (peluquero_id, servicio_id, precio, activo)
SELECT p.id, s.id, 0.00, TRUE
FROM peluqueros p
CROSS JOIN servicios s
LEFT JOIN peluqueros_servicios ps
  ON ps.peluquero_id = p.id
 AND ps.servicio_id = s.id
WHERE p.activo = TRUE
  AND s.activo = TRUE
  AND ps.id IS NULL;

SELECT
  ps.id,
  p.nombre AS peluquero,
  s.nombre AS servicio,
  ps.precio,
  ps.activo
FROM peluqueros_servicios ps
JOIN peluqueros p ON p.id = ps.peluquero_id
JOIN servicios s ON s.id = ps.servicio_id
ORDER BY p.orden, p.id, s.id;

SELECT COUNT(*) AS total_combinaciones
FROM peluqueros_servicios;

SELECT nombre, COUNT(*) AS total
FROM servicios
GROUP BY nombre
HAVING COUNT(*) > 1;

SELECT
  COLUMN_NAME,
  COLUMN_TYPE,
  IS_NULLABLE,
  COLUMN_DEFAULT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'turnos'
  AND COLUMN_NAME = 'precio_servicio';
