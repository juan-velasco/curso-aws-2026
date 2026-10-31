"""Datos de referencia sin sistema de origen: tipos de cambio y calendario.

Se cargan en silver (demo 4) con cargar_referencia.py. Solo usa la biblioteca estándar.

Simplificaciones del curso, comunes a todos los países:
    - rebajas: del 7 de enero al 28 de febrero y del 1 de julio al 31 de agosto;
    - festivos: 1 de enero, 1 de mayo y 25 de diciembre.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import cache

from comun import maestros

CALENDARIO_DESDE = date(2024, 1, 1)
CALENDARIO_HASTA = date(2027, 12, 31)

NOMBRES_MES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
NOMBRES_DIA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
FESTIVOS = {(1, 1), (5, 1), (12, 25)}  # (mes, día)


def tipos_cambio() -> list[dict]:
    """Una fila por moneda: euros que vale una unidad, con 8 decimales."""
    return [
        {
            "moneda": moneda,
            "eur_por_unidad": (Decimal(1) / Decimal(str(tipo))).quantize(Decimal("0.00000001"), ROUND_HALF_UP),
        }
        for moneda, tipo in maestros.TIPOS_CAMBIO.items()
    ]


def temporada(fecha: date) -> str:
    """PV de marzo a agosto, OI de septiembre a febrero."""
    return "PV" if 3 <= fecha.month <= 8 else "OI"


def es_rebajas(fecha: date) -> bool:
    return (fecha.month == 1 and fecha.day >= 7) or fecha.month in (2, 7, 8)


def es_festivo(fecha: date) -> bool:
    return (fecha.month, fecha.day) in FESTIVOS


@dataclass(frozen=True)
class Dia:
    fecha_sk: int  # AAAAMMDD
    fecha: date
    anio: int
    mes: int
    nombre_mes: str
    semana_iso: int
    dia_semana: int  # 1 = lunes
    nombre_dia: str
    es_fin_de_semana: bool
    temporada: str  # PV | OI
    es_rebajas: bool
    es_festivo: bool


def _dia(fecha: date) -> Dia:
    return Dia(
        fecha_sk=int(fecha.strftime("%Y%m%d")),
        fecha=fecha,
        anio=fecha.year,
        mes=fecha.month,
        nombre_mes=NOMBRES_MES[fecha.month - 1],
        semana_iso=fecha.isocalendar().week,
        dia_semana=fecha.isoweekday(),
        nombre_dia=NOMBRES_DIA[fecha.isoweekday() - 1],
        es_fin_de_semana=fecha.isoweekday() >= 6,
        temporada=temporada(fecha),
        es_rebajas=es_rebajas(fecha),
        es_festivo=es_festivo(fecha),
    )


@cache
def calendario() -> tuple[Dia, ...]:
    """Una fila por día, de 2024-01-01 a 2027-12-31."""
    dias = (CALENDARIO_HASTA - CALENDARIO_DESDE).days + 1
    return tuple(_dia(CALENDARIO_DESDE + timedelta(days=n)) for n in range(dias))


def como_dict(dia: Dia) -> dict:
    return asdict(dia)
