-- Esquema de los maestros que replica DMS hacia bronze/cdc/public/
-- Las claves primarias son imprescindibles para que DMS replique bien UPDATE y DELETE.

CREATE TABLE IF NOT EXISTS clientes (
    cliente_id     varchar(12)  PRIMARY KEY,
    nombre         varchar(100) NOT NULL,
    email          varchar(150) NOT NULL,
    telefono       varchar(30),
    segmento       varchar(10)  NOT NULL CHECK (segmento IN ('Standard', 'Premium')),
    provincia      varchar(60),
    pais           char(2)      NOT NULL,
    fecha_alta     date         NOT NULL,
    actualizado_en timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS productos (
    producto_id     varchar(20)   PRIMARY KEY,
    modelo          char(4)       NOT NULL,
    color           varchar(20)   NOT NULL,
    talla           varchar(3)    NOT NULL,
    familia         varchar(20)   NOT NULL,
    temporada       char(4)       NOT NULL CHECK (temporada IN ('PV26', 'OI26')),
    precio_catalogo numeric(8, 2) NOT NULL CHECK (precio_catalogo > 0),
    coste_unitario  numeric(8, 2) NOT NULL CHECK (coste_unitario > 0)
);

-- Con REPLICA IDENTITY FULL el WAL lleva la fila completa anterior: el DELETE
-- de C-981 llega a bronze con todas sus columnas, no solo con la clave.
ALTER TABLE clientes  REPLICA IDENTITY FULL;
ALTER TABLE productos REPLICA IDENTITY FULL;
