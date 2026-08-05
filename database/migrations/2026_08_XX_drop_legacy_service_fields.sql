-- Future contract migration. Do not run until production is fully using
-- peluqueros_servicios and turnos historical fields as the only sources.
--
-- Preconditions:
-- 1. The application version deployed in production no longer reads servicios.precio.
-- 2. The application version deployed in production no longer reads servicios.duracion.
-- 3. Every active peluqueros_servicios row has duracion_bloqueo_minutos > 0.
-- 4. Every turnos row has duracion_bloqueo_servicio > 0.
-- 5. Backups were created and verified.

-- Verification before contract:
SELECT COUNT(*) AS servicios_total FROM servicios;
SELECT COUNT(*) AS combinaciones_total FROM peluqueros_servicios;
SELECT COUNT(*) AS turnos_total FROM turnos;
SELECT COUNT(*) AS turnos_sin_bloqueo FROM turnos WHERE duracion_bloqueo_servicio IS NULL OR duracion_bloqueo_servicio <= 0;

-- Contract steps for a future release:
ALTER TABLE servicios DROP COLUMN precio;
ALTER TABLE servicios DROP COLUMN duracion;
