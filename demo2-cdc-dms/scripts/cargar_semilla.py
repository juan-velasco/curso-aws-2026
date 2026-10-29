"""Crea el esquema y el usuario de DMS y carga los maestros en RDS PostgreSQL.

4.000 clientes y 1.200 productos de comun/maestros.py. Idempotente: si ya hay
datos, avisa y no duplica.

Uso:
    python demo2-cdc-dms/scripts/cargar_semilla.py
"""

import json

from conexion import SQL, conectar_maestro, sesion_aws, tf
from psycopg import sql

from comun import maestros

COLUMNAS_CLIENTES = ["cliente_id", "nombre", "email", "telefono", "segmento", "provincia", "pais", "fecha_alta"]
COLUMNAS_PRODUCTOS = [
    "producto_id", "modelo", "color", "talla", "familia", "temporada", "precio_catalogo", "coste_unitario",
]


def copiar(cur, tabla: str, columnas: list[str], registros) -> None:
    consulta = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(tabla), sql.SQL(", ").join(map(sql.Identifier, columnas))
    )
    with cur.copy(consulta) as copia:
        for r in registros:
            fila = maestros.como_dict(r)
            copia.write_row([fila[c] for c in columnas])


def main() -> None:
    secreto = json.loads(
        sesion_aws().client("secretsmanager").get_secret_value(SecretId=tf()["secreto_nombre"])["SecretString"]
    )
    print(f"Conectando a {tf()['rds_endpoint']} ...")
    with conectar_maestro() as conn, conn.cursor() as cur:
        wal_level = cur.execute("SHOW wal_level").fetchone()[0]
        print(f"wal_level = {wal_level}")
        if wal_level != "logical":
            print("AVISO: wal_level no es 'logical'. Reinicia la instancia para aplicar el parameter group:\n"
                  "  aws rds reboot-db-instance --db-instance-identifier curso-aws-hp-retail --profile curso")

        cur.execute((SQL / "01_esquema.sql").read_text(encoding="utf-8"))
        print("Esquema creado (clientes, productos)")

        usuario = sql.SQL((SQL / "02_usuario_dms.sql").read_text(encoding="utf-8")).format(
            password=sql.Literal(secreto["password"])
        )
        cur.execute(usuario)
        print("Usuario dms_user creado con rds_replication y SELECT sobre public")

        for tabla, columnas, registros in (
            ("clientes", COLUMNAS_CLIENTES, maestros.clientes()),
            ("productos", COLUMNAS_PRODUCTOS, maestros.productos()),
        ):
            existentes = cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla))).fetchone()[0]
            if existentes:
                print(f"AVISO: {tabla} ya tiene {existentes} filas; no se carga de nuevo")
                continue
            copiar(cur, tabla, columnas, registros)
            print(f"{tabla}: {len(registros)} filas cargadas")

        clientes, productos = cur.execute(
            "SELECT (SELECT count(*) FROM clientes), (SELECT count(*) FROM productos)"
        ).fetchone()
        c17 = cur.execute("SELECT segmento, provincia FROM clientes WHERE cliente_id = 'C-17'").fetchone()
    print(f"\nTotal: {clientes} clientes, {productos} productos. C-17: {c17}")


if __name__ == "__main__":
    main()
