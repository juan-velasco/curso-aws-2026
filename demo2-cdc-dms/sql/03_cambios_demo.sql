-- Cambios de la diapositiva «Qué deja DMS en bronze».
-- Se ejecutan en una transacción: los tres llegan juntos al mismo fichero CDC.

BEGIN;

-- U: C-17 pasa a Premium
UPDATE clientes
   SET segmento = 'Premium', actualizado_en = now()
 WHERE cliente_id = 'C-17';

-- I: alta de C-4001 (no existe en la semilla)
INSERT INTO clientes (cliente_id, nombre, email, telefono, segmento, provincia, pais, fecha_alta)
VALUES ('C-4001', 'Camille Martin', 'cliente4001@ejemplo.com', '+33 600 004 001',
        'Standard', 'Lyon', 'FR', current_date)
ON CONFLICT (cliente_id) DO NOTHING;

-- D: baja de C-981
DELETE FROM clientes WHERE cliente_id = 'C-981';

COMMIT;
