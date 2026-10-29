"""Gestiona la tarea de DMS de la demo 2.

Uso:
    python demo2-cdc-dms/scripts/tarea_dms.py probar    # test de conexión de ambos endpoints
    python demo2-cdc-dms/scripts/tarea_dms.py iniciar   # arranca (o reanuda) la tarea
    python demo2-cdc-dms/scripts/tarea_dms.py estado    # estado y estadísticas por tabla
    python demo2-cdc-dms/scripts/tarea_dms.py parar     # para la tarea y espera a 'stopped'
"""

import argparse
import sys
import time

from conexion import sesion_aws, tf


def dms():
    return sesion_aws().client("dms")


def tarea(cliente) -> dict:
    return cliente.describe_replication_tasks(
        Filters=[{"Name": "replication-task-arn", "Values": [tf()["tarea_arn"]]}]
    )["ReplicationTasks"][0]


def probar(cliente) -> bool:
    instancia = tf()["instancia_replicacion_arn"]
    endpoints = {"origen (PostgreSQL)": tf()["endpoint_origen_arn"], "destino (S3)": tf()["endpoint_destino_arn"]}
    for arn in endpoints.values():
        cliente.test_connection(ReplicationInstanceArn=instancia, EndpointArn=arn)
    print("Probando conexiones (puede tardar 1-2 minutos)...")
    pendientes = dict(endpoints)
    resultado = True
    while pendientes:
        time.sleep(10)
        for nombre, arn in list(pendientes.items()):
            con = cliente.describe_connections(
                Filters=[{"Name": "endpoint-arn", "Values": [arn]},
                         {"Name": "replication-instance-arn", "Values": [instancia]}]
            )["Connections"][0]
            if con["Status"] == "testing":
                continue
            ok = con["Status"] == "successful"
            resultado &= ok
            print(f"  [{'OK' if ok else 'KO'}] {nombre}: {con['Status']} {con.get('LastFailureMessage', '')}")
            del pendientes[nombre]
    return resultado


def iniciar(cliente) -> None:
    t = tarea(cliente)
    if t["Status"] == "running":
        print("La tarea ya está en marcha")
        return
    # La primera vez se arranca; tras parar, se reanuda el CDC desde donde se quedó
    tipo = "resume-processing" if t["Status"] == "stopped" else "start-replication"
    cliente.start_replication_task(ReplicationTaskArn=t["ReplicationTaskArn"], StartReplicationTaskType=tipo)
    print(f"Tarea arrancada ({tipo}). Esperando a 'running'...")
    esperar(cliente, {"running"})
    print("La carga completa tarda ~1 minuto. Sigue con: tarea_dms.py estado")


def estado(cliente) -> None:
    t = tarea(cliente)
    stats = t.get("ReplicationTaskStats", {})
    print(f"Tarea {t['ReplicationTaskIdentifier']}: {t['Status']}"
          + (f" ({t['StopReason']})" if t.get("StopReason") else ""))
    if t.get("LastFailureMessage"):
        print(f"  Último error: {t['LastFailureMessage']}")
    if stats:
        print(f"  Carga completa: {stats.get('FullLoadProgressPercent', 0)} %, "
              f"tablas cargadas {stats.get('TablesLoaded', 0)}, con error {stats.get('TablesErrored', 0)}")
    if t["Status"] in ("running", "stopped"):
        tablas = cliente.describe_table_statistics(ReplicationTaskArn=t["ReplicationTaskArn"])["TableStatistics"]
        print(f"  {'tabla':<18}{'estado':<26}{'carga':>7}{'ins':>6}{'upd':>6}{'del':>6}")
        for e in tablas:
            print(f"  {e['SchemaName'] + '.' + e['TableName']:<18}{e['TableState']:<26}{e['FullLoadRows']:>7}"
                  f"{e['Inserts']:>6}{e['Updates']:>6}{e['Deletes']:>6}")


def parar(cliente) -> None:
    t = tarea(cliente)
    if t["Status"] != "running":
        print(f"La tarea no está en marcha (estado: {t['Status']})")
        return
    cliente.stop_replication_task(ReplicationTaskArn=t["ReplicationTaskArn"])
    print("Parando la tarea...")
    esperar(cliente, {"stopped"})


def esperar(cliente, estados: set[str], minutos: int = 10) -> None:
    limite = time.monotonic() + minutos * 60
    while (actual := tarea(cliente)["Status"]) not in estados:
        if actual == "failed" or time.monotonic() > limite:
            estado(cliente)
            sys.exit(f"La tarea no llegó a {estados} (estado: {actual})")
        time.sleep(10)
    print(f"Estado: {actual}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("accion", choices=["probar", "iniciar", "estado", "parar"])
    args = p.parse_args()
    cliente = dms()
    if args.accion == "probar":
        sys.exit(0 if probar(cliente) else 1)
    {"iniciar": iniciar, "estado": estado, "parar": parar}[args.accion](cliente)


if __name__ == "__main__":
    main()
