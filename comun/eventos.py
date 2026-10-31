"""Construcción de tickets y eventos de venta.

La comparten el generador (demo 1, en tiempo real) y el backfill (histórico
directo a bronze), de modo que sus eventos son idénticos en forma. Un evento es
una línea de ticket. Solo usa la biblioteca estándar.

Los patrones del histórico también están aquí, para que el dashboard y la
previsión de la sesión 3 tengan señal:
    - fin de semana x1,3 y rebajas x1,6 sobre el volumen diario;
    - abrigos y punto x2,5 en los meses de OI y baño x2,5 en los de PV.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime

from comun import maestros, referencia

MEDIOS_PAGO_TIENDA = ("TARJETA", "EFECTIVO", "MOVIL")
MEDIOS_PAGO_ONLINE = ("TARJETA", "PAYPAL")
PESO_ONLINE = 4  # cada canal online pesa como 4 tiendas físicas
LINEAS_POR_TICKET = (1, 2, 3, 4)
PESOS_LINEAS = (45, 30, 15, 10)
MEDIA_LINEAS = sum(n * p for n, p in zip(LINEAS_POR_TICKET, PESOS_LINEAS)) / sum(PESOS_LINEAS)

FACTOR_FIN_DE_SEMANA = 1.3
FACTOR_REBAJAS = 1.6
FACTOR_ESTACIONAL = 2.5
FAMILIAS_ESTACIONALES = {"abrigos": "OI", "punto": "OI", "baño": "PV"}  # familia -> temporada en la que sube


def iso_utc(momento: datetime) -> str:
    """Marca de tiempo en UTC con milisegundos y sufijo Z: 2026-10-24T10:15:32.481Z."""
    return momento.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ahora_iso() -> str:
    return iso_utc(datetime.now(UTC))


def eventos_del_dia(fecha: date, eventos_dia: int) -> int:
    """Volumen del día: la base multiplicada por los factores de fin de semana y rebajas."""
    factor = 1.0
    if fecha.isoweekday() >= 6:
        factor *= FACTOR_FIN_DE_SEMANA
    if referencia.es_rebajas(fecha):
        factor *= FACTOR_REBAJAS
    return round(eventos_dia * factor)


def pesos_productos(fecha: date) -> list[float]:
    """Peso de cada producto de maestros.productos() según la estacionalidad de su familia."""
    temporada = referencia.temporada(fecha)
    return [
        FACTOR_ESTACIONAL if FAMILIAS_ESTACIONALES.get(p.familia) == temporada else 1.0
        for p in maestros.productos()
    ]


class FabricaVentas:
    """Genera tickets coherentes con los maestros.

    `secuencia_inicial` es el primer valor de la secuencia de ticket por tienda.
    Por defecto, los segundos transcurridos del día, para no repetir ticket_id
    entre ejecuciones sucesivas del mismo día.
    """

    def __init__(
        self,
        rng: random.Random | None = None,
        secuencia_inicial: int | None = None,
        nuevo_id: Callable[[], str] | None = None,
    ):
        self.rng = rng or random.Random()
        self.nuevo_id = nuevo_id or (lambda: str(uuid.uuid4()))
        self.tiendas = maestros.tiendas()
        self.pesos = [PESO_ONLINE if t.es_online else 1 for t in self.tiendas]
        self.productos = maestros.productos()
        self.clientes = maestros.clientes_por_pais()
        if secuencia_inicial is None:
            hoy = datetime.now(UTC)
            secuencia_inicial = hoy.hour * 3600 + hoy.minute * 60 + hoy.second
        self.secuencias = {t.tienda_id: secuencia_inicial for t in self.tiendas}

    def _elegir_productos(self, num_lineas: int, pesos: Sequence[float] | None) -> list[maestros.Producto]:
        """Productos distintos para las líneas del ticket, con pesos si se indican."""
        if pesos is None:
            return self.rng.sample(self.productos, num_lineas)
        elegidos: dict[str, maestros.Producto] = {}
        while len(elegidos) < num_lineas:
            producto = self.rng.choices(self.productos, pesos)[0]
            elegidos[producto.producto_id] = producto
        return list(elegidos.values())

    def ticket(self, momento: datetime | None = None, pesos: Sequence[float] | None = None) -> list[dict]:
        """Un ticket de 1 a 4 líneas: un evento por línea. Por defecto, con la hora actual."""
        rng = self.rng
        tienda = rng.choices(self.tiendas, self.pesos)[0]
        event_ts = iso_utc(momento) if momento else ahora_iso()
        self.secuencias[tienda.tienda_id] += 1
        ticket_id = f"T-{event_ts[:10].replace('-', '')}-{tienda.numero}-{self.secuencias[tienda.tienda_id]:06d}"
        if tienda.es_online:
            canal = rng.choice(("WEB", "APP"))
            medio_pago = rng.choice(MEDIOS_PAGO_ONLINE)
        else:
            canal = "TPV"
            medio_pago = rng.choices(MEDIOS_PAGO_TIENDA, (60, 25, 15))[0]
        # ~30 % de los tickets sin cliente identificado
        cliente = None if rng.random() < 0.30 else rng.choice(self.clientes[tienda.pais]).cliente_id
        moneda = tienda.moneda
        decimales = maestros.decimales(moneda)

        lineas = []
        num_lineas = rng.choices(LINEAS_POR_TICKET, PESOS_LINEAS)[0]
        for n, producto in enumerate(self._elegir_productos(num_lineas, pesos), start=1):
            unidades = rng.choices((1, 2, 3), (88, 9, 3))[0]
            precio = producto.precio_en(moneda)
            descuento = 0.0
            if rng.random() < 0.20:  # algunas líneas con descuento del 10 % al 30 %
                descuento = round(precio * unidades * rng.uniform(0.10, 0.30), decimales)
            lineas.append(
                {
                    "event_id": self.nuevo_id(),
                    "event_ts": event_ts,
                    "canal": canal,
                    "tienda_id": tienda.tienda_id,
                    "ticket_id": ticket_id,
                    "linea": n,
                    "cliente_id": cliente,
                    "producto_id": producto.producto_id,
                    "unidades": unidades,
                    "precio_unitario": precio,
                    "descuento": descuento,
                    "moneda": moneda,
                    "medio_pago": medio_pago,
                }
            )
        return lineas

    def invalido(self, evento: dict) -> dict:
        """Copia del evento que incumple el contrato (la API debe responder 422)."""
        campo, valor = self.rng.choice(
            [("event_id", "no-es-uuid"), ("unidades", 0), ("precio_unitario", -1.0), ("moneda", "EU")]
        )
        return {**evento, campo: valor}
