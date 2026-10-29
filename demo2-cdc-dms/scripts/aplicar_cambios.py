"""Ejecuta los cambios de la demo (sql/03_cambios_demo.sql): U de C-17, I de C-4001, D de C-981.

Uso:
    python demo2-cdc-dms/scripts/aplicar_cambios.py
"""

from datetime import UTC, datetime

from conexion import SQL, conectar_maestro


def main() -> None:
    with conectar_maestro() as conn:
        conn.autocommit = True  # el fichero gestiona su propia transacción (BEGIN/COMMIT)
        with conn.cursor() as cur:
            cur.execute((SQL / "03_cambios_demo.sql").read_text(encoding="utf-8"))
            filas = cur.execute(
                "SELECT cliente_id, segmento, provincia, pais FROM clientes "
                "WHERE cliente_id IN ('C-17', 'C-981', 'C-4001') ORDER BY cliente_id"
            ).fetchall()
    print(f"Cambios aplicados a las {datetime.now(UTC):%H:%M:%S} UTC. Estado actual:")
    for fila in filas:
        print("  ", *fila)
    print("  (C-981 ya no existe)" if all(f[0] != "C-981" for f in filas) else "")
    print("DMS los escribirá en bronze en ~1 minuto: python demo2-cdc-dms/scripts/comprobar_cdc.py")


if __name__ == "__main__":
    main()
