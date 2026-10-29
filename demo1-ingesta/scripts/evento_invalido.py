"""Envía un evento inválido a la API y muestra el detalle del 422.

Equivale al curl de la diapositiva «Demo 1: comandos»:
    curl -s -X POST localhost:8000/ventas/lote -H 'Content-Type: application/json' \
      -d '[{"event_id": "no-es-uuid"}]' | jq '.detail[0]'

Uso:
    python demo1-ingesta/scripts/evento_invalido.py               # como la diapositiva
    python demo1-ingesta/scripts/evento_invalido.py --campo unidades
"""

import argparse
import json
import urllib.error
import urllib.request
import uuid

EVENTO = {
    "event_id": "7f3c2a9e-5b1d-4c8e-9a0f-2d6e8b1c4a77",
    "event_ts": "2026-10-24T10:15:32.481Z",
    "canal": "TPV",
    "tienda_id": "ES-VLC-003",
    "ticket_id": "T-20261024-003-000187",
    "linea": 2,
    "cliente_id": "C-17",
    "producto_id": "P-0412-ROJ-M",
    "unidades": 1,
    "precio_unitario": 39.95,
    "descuento": 8.00,
    "moneda": "EUR",
    "medio_pago": "TARJETA",
}

# Un valor que incumple el contrato para cada campo que se puede probar
INVALIDOS = {"event_id": "no-es-uuid", "unidades": 0, "precio_unitario": -5.0, "moneda": "EU", "linea": 0}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--campo", choices=INVALIDOS, help="evento completo con solo este campo inválido")
    args = p.parse_args()

    if args.campo:
        lote = [{**EVENTO, "event_id": str(uuid.uuid4()), args.campo: INVALIDOS[args.campo]}]
    else:
        lote = [{"event_id": "no-es-uuid"}]  # como en la diapositiva
    print("Petición:", json.dumps(lote, ensure_ascii=False))

    peticion = urllib.request.Request(
        f"{args.api.rstrip('/')}/ventas/lote",
        data=json.dumps(lote).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=10) as r:
            print(f"Respuesta {r.status}: {r.read().decode()}")
            raise SystemExit("KO: la API aceptó un evento inválido")
    except urllib.error.HTTPError as e:
        codigo, cuerpo = e.code, json.loads(e.read())
    except urllib.error.URLError as e:
        raise SystemExit(f"No se puede conectar con la API en {args.api}: {e.reason}") from e

    print(f"Respuesta {codigo}. detail[0]:")
    print(json.dumps(cuerpo["detail"][0], indent=2, ensure_ascii=False))
    if len(cuerpo["detail"]) > 1:
        campos = ", ".join(str(d["loc"][-1]) for d in cuerpo["detail"])
        print(f"({len(cuerpo['detail'])} errores en total, campos: {campos})")
    print("OK: 422 con el campo que falla" if codigo == 422 else f"KO: se esperaba 422 y llegó {codigo}")


if __name__ == "__main__":
    main()
