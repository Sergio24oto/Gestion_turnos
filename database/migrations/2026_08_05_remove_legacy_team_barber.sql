-- Limpieza del profesional heredado "Equipo Marcelo Navarro".
-- No ejecutar sin backup. Script idempotente para MySQL 8.
--
-- Criterio:
-- - Marcelo Navarro es el destino de relaciones peluquero-servicio no duplicadas.
-- - Si Marcelo ya tiene la combinación, se conserva la fila de Marcelo.
-- - Solo se completan campos NULL de Marcelo con valores no NULL de Equipo.
-- - No se pisan precios/duraciones existentes de Marcelo con 0 o NULL.
-- - Si Equipo tiene turnos, la migración se detiene y no reasigna automáticamente.

DELIMITER //

DROP PROCEDURE IF EXISTS remove_legacy_team_barber//
CREATE PROCEDURE remove_legacy_team_barber()
BEGIN
  DECLARE legacy_id INT DEFAULT NULL;
  DECLARE marcelo_id INT DEFAULT NULL;
  DECLARE legacy_appointments INT DEFAULT 0;

  SELECT id
    INTO legacy_id
  FROM peluqueros
  WHERE nombre = 'Equipo Marcelo Navarro'
  ORDER BY id
  LIMIT 1;

  IF legacy_id IS NOT NULL THEN
    SELECT id
      INTO marcelo_id
    FROM peluqueros
    WHERE nombre = 'Marcelo Navarro'
    ORDER BY id
    LIMIT 1;

    IF marcelo_id IS NULL THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'No se encontró Marcelo Navarro para consolidar relaciones de Equipo Marcelo Navarro.';
    END IF;

    SELECT COUNT(*)
      INTO legacy_appointments
    FROM turnos
    WHERE peluquero_id = legacy_id;

    IF legacy_appointments > 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Equipo Marcelo Navarro tiene turnos. Revisar y reasignar explícitamente antes de limpiar.';
    END IF;

    -- Completar configuraciones de Marcelo solo cuando falte dato y Equipo tenga dato.
    UPDATE peluqueros_servicios target
    JOIN peluqueros_servicios source
      ON source.servicio_id = target.servicio_id
     AND source.peluquero_id = legacy_id
    SET
      target.precio = CASE
        WHEN target.precio IS NULL AND source.precio IS NOT NULL THEN source.precio
        ELSE target.precio
      END,
      target.duracion_visible_minutos = CASE
        WHEN target.duracion_visible_minutos IS NULL AND source.duracion_visible_minutos IS NOT NULL
          THEN source.duracion_visible_minutos
        ELSE target.duracion_visible_minutos
      END,
      target.duracion_bloqueo_minutos = CASE
        WHEN (target.duracion_bloqueo_minutos IS NULL OR target.duracion_bloqueo_minutos <= 0)
          AND source.duracion_bloqueo_minutos IS NOT NULL
          AND source.duracion_bloqueo_minutos > 0
          THEN source.duracion_bloqueo_minutos
        ELSE target.duracion_bloqueo_minutos
      END,
      target.activo = CASE
        WHEN target.activo = FALSE AND source.activo = TRUE THEN TRUE
        ELSE target.activo
      END,
      target.actualizado_en = NOW()
    WHERE target.peluquero_id = marcelo_id;

    -- Mover relaciones que Marcelo no tenga.
    UPDATE peluqueros_servicios source
    LEFT JOIN peluqueros_servicios target
      ON target.peluquero_id = marcelo_id
     AND target.servicio_id = source.servicio_id
    SET source.peluquero_id = marcelo_id,
        source.actualizado_en = NOW()
    WHERE source.peluquero_id = legacy_id
      AND target.id IS NULL;

    -- Eliminar relaciones duplicadas restantes de Equipo.
    DELETE source
    FROM peluqueros_servicios source
    JOIN peluqueros_servicios target
      ON target.peluquero_id = marcelo_id
     AND target.servicio_id = source.servicio_id
    WHERE source.peluquero_id = legacy_id;

    -- Si no quedan referencias conocidas, eliminar físicamente el registro heredado.
    DELETE FROM peluqueros
    WHERE id = legacy_id
      AND NOT EXISTS (
        SELECT 1 FROM turnos WHERE turnos.peluquero_id = legacy_id
      )
      AND NOT EXISTS (
        SELECT 1 FROM peluqueros_servicios ps WHERE ps.peluquero_id = legacy_id
      );
  END IF;
END//

DELIMITER ;

CALL remove_legacy_team_barber();
DROP PROCEDURE remove_legacy_team_barber;

-- Verificaciones finales.
SELECT id, nombre, activo, orden
FROM peluqueros
ORDER BY orden, id;

SELECT COUNT(*) AS equipo_activo
FROM peluqueros
WHERE nombre = 'Equipo Marcelo Navarro'
  AND activo = TRUE;

SELECT COUNT(*) AS turnos_equipo
FROM turnos t
JOIN peluqueros p ON p.id = t.peluquero_id
WHERE p.nombre = 'Equipo Marcelo Navarro';

SELECT COUNT(*) AS relaciones_equipo
FROM peluqueros_servicios ps
JOIN peluqueros p ON p.id = ps.peluquero_id
WHERE p.nombre = 'Equipo Marcelo Navarro';

SELECT p.nombre AS peluquero, s.nombre AS servicio, ps.precio, ps.duracion_visible_minutos,
       ps.duracion_bloqueo_minutos, ps.activo
FROM peluqueros_servicios ps
JOIN peluqueros p ON p.id = ps.peluquero_id
JOIN servicios s ON s.id = ps.servicio_id
ORDER BY p.orden, p.id, s.id;
