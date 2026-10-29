"""Datos maestros del retail de moda: tiendas, clientes y productos.

Es la única fuente de maestros del curso. La usan el generador de ventas
(demo 1) y la carga de la base de datos que replica DMS (demo 2), de modo que
cualquier `cliente_id` o `producto_id` de una venta existe en los maestros.

La generación es determinista: cada tabla usa su propia semilla fija, así que
dos ejecuciones producen exactamente los mismos datos y añadir campos a una
tabla no altera las demás. Solo usa la biblioteca estándar.

Uso:
    from comun import maestros
    maestros.tiendas()      # 21 físicas + 5 online
    maestros.clientes()     # 4.000
    maestros.productos()    # 1.200
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from functools import cache

SEMILLA = 2026

# --- Países, monedas y tipos de cambio -------------------------------------

# Tipos de cambio ILUSTRATIVOS y FIJOS (1 EUR = x moneda local). No son
# cotizaciones reales: se fijan para que los importes sean reproducibles.
TIPOS_CAMBIO: dict[str, float] = {
    "EUR": 1.0,
    "USD": 1.08,
    "JPY": 160.0,
    "CNY": 7.8,
}

# Monedas sin decimales
MONEDAS_SIN_DECIMALES = {"JPY"}

PAISES: dict[str, str] = {  # país -> moneda
    "ES": "EUR",
    "FR": "EUR",
    "US": "USD",
    "JP": "JPY",
    "CN": "CNY",
}

PREFIJOS_TELEFONO = {"ES": "+34", "FR": "+33", "US": "+1", "JP": "+81", "CN": "+86"}


def decimales(moneda: str) -> int:
    return 0 if moneda in MONEDAS_SIN_DECIMALES else 2


def a_moneda_local(importe_eur: float, moneda: str) -> float:
    """Convierte un importe en EUR a la moneda indicada con los tipos fijos."""
    return round(importe_eur * TIPOS_CAMBIO[moneda], decimales(moneda))


# --- Tiendas ----------------------------------------------------------------

# Ciudades con su código de 3 letras
CIUDADES: dict[str, tuple[str, str]] = {
    "MAD": ("Madrid", "ES"),
    "BCN": ("Barcelona", "ES"),
    "VLC": ("Valencia", "ES"),
    "PAR": ("Paris", "FR"),
    "LYS": ("Lyon", "FR"),
    "MRS": ("Marseille", "FR"),
    "NYC": ("New York", "US"),
    "LAX": ("Los Angeles", "US"),
    "CHI": ("Chicago", "US"),
    "TYO": ("Tokyo", "JP"),
    "OSA": ("Osaka", "JP"),
    "KYO": ("Kyoto", "JP"),
    "SHA": ("Shanghai", "CN"),
    "PEK": ("Beijing", "CN"),
    "SZX": ("Shenzhen", "CN"),
}

# 21 tiendas físicas: (tienda_id, formato, superficie_m2)
_TIENDAS_FISICAS = [
    ("ES-MAD-001", "calle", 850),
    ("ES-MAD-002", "centro comercial", 620),
    ("ES-BCN-001", "calle", 780),
    ("ES-VLC-001", "calle", 540),
    ("ES-VLC-002", "outlet", 1100),
    ("ES-VLC-003", "centro comercial", 480),
    ("FR-PAR-001", "calle", 900),
    ("FR-PAR-002", "centro comercial", 560),
    ("FR-LYS-001", "calle", 510),
    ("FR-MRS-001", "outlet", 950),
    ("US-NYC-001", "calle", 1200),
    ("US-NYC-002", "centro comercial", 700),
    ("US-LAX-001", "centro comercial", 820),
    ("US-CHI-001", "outlet", 1300),
    ("JP-TYO-001", "calle", 650),
    ("JP-TYO-002", "centro comercial", 430),
    ("JP-OSA-001", "calle", 520),
    ("JP-KYO-001", "calle", 380),
    ("CN-SHA-001", "centro comercial", 760),
    ("CN-PEK-001", "calle", 690),
    ("CN-SZX-001", "centro comercial", 580),
]

NOMBRES_PAIS = {"ES": "España", "FR": "Francia", "US": "Estados Unidos", "JP": "Japón", "CN": "China"}


@dataclass(frozen=True)
class Tienda:
    tienda_id: str
    nombre: str
    pais: str
    ciudad: str
    formato: str  # calle | centro comercial | outlet | online
    superficie_m2: int | None  # None en el canal online

    @property
    def es_online(self) -> bool:
        return self.formato == "online"

    @property
    def moneda(self) -> str:
        return PAISES[self.pais]

    @property
    def numero(self) -> str:
        """Número de tienda de 3 dígitos para el `ticket_id` ("000" online)."""
        return "000" if self.es_online else self.tienda_id[-3:]


@cache
def tiendas() -> tuple[Tienda, ...]:
    """Las 21 tiendas físicas seguidas de los 5 canales online (ONL-<PAÍS>)."""
    resultado = []
    for tienda_id, formato, superficie in _TIENDAS_FISICAS:
        pais, codigo, _ = tienda_id.split("-")
        ciudad = CIUDADES[codigo][0]
        nombre = f"{ciudad} {tienda_id[-3:]}"
        resultado.append(Tienda(tienda_id, nombre, pais, ciudad, formato, superficie))
    for pais in PAISES:
        resultado.append(
            Tienda(f"ONL-{pais}", f"Online {NOMBRES_PAIS[pais]}", pais, "online", "online", None)
        )
    return tuple(resultado)


def tiendas_fisicas() -> tuple[Tienda, ...]:
    return tuple(t for t in tiendas() if not t.es_online)


# --- Clientes ---------------------------------------------------------------

NUM_CLIENTES = 4000

# Reparto de clientes por país (pesos) y provincias o regiones de cada país
_PESO_PAIS = {"ES": 40, "FR": 20, "US": 15, "JP": 15, "CN": 10}
_PROVINCIAS = {
    "ES": ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bizkaia", "Málaga", "Alicante", "Zaragoza"],
    "FR": ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux", "Lille"],
    "US": ["New York", "California", "Illinois", "Texas", "Florida"],
    "JP": ["Tokyo", "Osaka", "Kyoto", "Kanagawa", "Aichi"],
    "CN": ["Shanghai", "Beijing", "Guangdong", "Zhejiang"],
}
_NOMBRES = {
    "ES": ["Lucía", "Hugo", "Martina", "Pablo", "Sofía", "Daniel", "Carmen", "Javier", "Elena", "Álvaro"],
    "FR": ["Camille", "Louis", "Léa", "Gabriel", "Manon", "Arthur", "Chloé", "Jules"],
    "US": ["Emma", "Liam", "Olivia", "Noah", "Ava", "James", "Mia", "Ethan"],
    "JP": ["Yui", "Haruto", "Aoi", "Sota", "Hina", "Ren", "Sakura", "Yuto"],
    "CN": ["Wei", "Li Na", "Jun", "Mei", "Hao", "Xin", "Lei", "Yan"],
}
_APELLIDOS = {
    "ES": ["García", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Ferrer", "Navarro", "Ruiz", "Soler"],
    "FR": ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Petit", "Durand", "Moreau"],
    "US": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson"],
    "JP": ["Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Ito", "Yamamoto", "Nakamura"],
    "CN": ["Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Huang", "Zhao"],
}
_ALTA_DESDE = date(2018, 1, 1)
_ALTA_HASTA = date(2026, 9, 30)

# Casos fijos que aparecen en las diapositivas
_CLIENTES_FIJOS = {
    17: {"segmento": "Standard", "provincia": "Valencia", "pais": "ES", "fecha_alta": date(2025, 1, 10)},
    981: {"segmento": "Standard", "provincia": "Madrid", "pais": "ES"},
}


@dataclass(frozen=True)
class Cliente:
    cliente_id: str
    nombre: str
    email: str
    telefono: str
    segmento: str  # Standard | Premium
    provincia: str
    pais: str
    fecha_alta: date


def telefono_ficticio(numero: int, pais: str) -> str:
    """Teléfono evidentemente ficticio: C-17 en ES -> '+34 600 000 017'."""
    cifras = f"{numero:06d}"
    return f"{PREFIJOS_TELEFONO[pais]} 600 {cifras[:3]} {cifras[3:]}"


def nuevo_cliente(numero: int, nombre: str, segmento: str, provincia: str, pais: str, fecha_alta: date) -> Cliente:
    return Cliente(
        cliente_id=f"C-{numero}",
        nombre=nombre,
        email=f"cliente{numero}@ejemplo.com",
        telefono=telefono_ficticio(numero, pais),
        segmento=segmento,
        provincia=provincia,
        pais=pais,
        fecha_alta=fecha_alta,
    )


@cache
def clientes() -> tuple[Cliente, ...]:
    """C-1 … C-4000 (sin ceros a la izquierda). C-4001 no existe en la semilla."""
    rng = random.Random(f"{SEMILLA}-clientes")
    paises = list(_PESO_PAIS)
    pesos = list(_PESO_PAIS.values())
    dias_alta = (_ALTA_HASTA - _ALTA_DESDE).days
    resultado = []
    for n in range(1, NUM_CLIENTES + 1):
        pais = rng.choices(paises, pesos)[0]
        datos = {
            "nombre": f"{rng.choice(_NOMBRES[pais])} {rng.choice(_APELLIDOS[pais])}",
            "segmento": "Premium" if rng.random() < 0.20 else "Standard",
            "provincia": rng.choice(_PROVINCIAS[pais]),
            "pais": pais,
            "fecha_alta": _ALTA_DESDE + timedelta(days=rng.randrange(dias_alta)),
        }
        datos.update(_CLIENTES_FIJOS.get(n, {}))
        if datos["pais"] != pais:  # el nombre debe corresponder al país fijado
            datos["nombre"] = f"{_NOMBRES[datos['pais']][0]} {_APELLIDOS[datos['pais']][0]}"
        resultado.append(nuevo_cliente(n, **datos))
    return tuple(resultado)


# --- Productos --------------------------------------------------------------

NUM_MODELOS = 100

COLORES: dict[str, str] = {
    "NEG": "Negro",
    "BLA": "Blanco",
    "AZU": "Azul",
    "ROJ": "Rojo",
    "BEI": "Beige",
    "VER": "Verde",
    "GRI": "Gris",
}
TALLAS = ("S", "M", "L", "XL")

# familia -> (precio mínimo, precio máximo en EUR, temporadas posibles)
FAMILIAS: dict[str, tuple[int, int, tuple[str, ...]]] = {
    "vestidos": (29, 89, ("PV26", "PV26", "OI26")),
    "camisas": (19, 59, ("PV26", "OI26")),
    "pantalones": (25, 69, ("PV26", "OI26")),
    "abrigos": (79, 199, ("OI26",)),
    "punto": (29, 79, ("OI26",)),
    "baño": (15, 49, ("PV26",)),
    "calzado": (39, 119, ("PV26", "OI26")),
    "accesorios": (9, 39, ("PV26", "OI26")),
}

# Modelo fijo de las diapositivas: P-0412-ROJ-M, un vestido de 39,95 EUR
_MODELO_FIJO = 412


@dataclass(frozen=True)
class Producto:
    producto_id: str
    modelo: str  # 4 dígitos, p. ej. "0412"
    color: str  # nombre del color, p. ej. "Rojo"
    talla: str
    familia: str
    temporada: str  # PV26 | OI26
    precio_catalogo: float  # EUR
    coste_unitario: float  # EUR, entre el 30 % y el 45 % del precio

    @property
    def codigo_color(self) -> str:
        return self.producto_id.split("-")[2]

    def precio_en(self, moneda: str) -> float:
        return a_moneda_local(self.precio_catalogo, moneda)


@cache
def productos() -> tuple[Producto, ...]:
    """100 modelos × 3 colores × 4 tallas = 1.200 referencias."""
    rng = random.Random(f"{SEMILLA}-productos")
    otros = [m for m in range(100, 1000) if m != _MODELO_FIJO]
    modelos = sorted(rng.sample(otros, NUM_MODELOS - 1) + [_MODELO_FIJO])
    familias = list(FAMILIAS)
    resultado = []
    for modelo in modelos:
        familia = rng.choice(familias)
        minimo, maximo, _ = FAMILIAS[familia]
        precio = rng.randint(minimo, maximo) + 0.95
        colores = rng.sample(list(COLORES), 3)
        if modelo == _MODELO_FIJO:
            familia, precio = "vestidos", 39.95
            if "ROJ" not in colores:
                colores[0] = "ROJ"
        temporada = rng.choice(FAMILIAS[familia][2])
        coste = round(precio * rng.uniform(0.30, 0.45), 2)
        for codigo in colores:
            for talla in TALLAS:
                resultado.append(
                    Producto(
                        producto_id=f"P-{modelo:04d}-{codigo}-{talla}",
                        modelo=f"{modelo:04d}",
                        color=COLORES[codigo],
                        talla=talla,
                        familia=familia,
                        temporada=temporada,
                        precio_catalogo=precio,
                        coste_unitario=coste,
                    )
                )
    return tuple(resultado)


# --- Utilidades -------------------------------------------------------------


@cache
def indice_clientes() -> dict[str, Cliente]:
    return {c.cliente_id: c for c in clientes()}


@cache
def indice_productos() -> dict[str, Producto]:
    return {p.producto_id: p for p in productos()}


@cache
def clientes_por_pais() -> dict[str, tuple[Cliente, ...]]:
    return {pais: tuple(c for c in clientes() if c.pais == pais) for pais in PAISES}


def como_dict(registro: Tienda | Cliente | Producto) -> dict:
    """Registro como diccionario (para cargar en la base de datos o en pandas)."""
    return asdict(registro)
