"""Tests de comun/maestros.py: deterministas y con los casos fijos de las diapositivas."""

import re
import subprocess
import sys
from collections import Counter
from datetime import date

from comun import maestros
from comun.terraform import RAIZ


def test_tiendas():
    fisicas = maestros.tiendas_fisicas()
    assert len(fisicas) == 21
    por_pais = Counter(t.pais for t in fisicas)
    assert por_pais == {"ES": 6, "FR": 4, "US": 4, "JP": 4, "CN": 3}
    ids = [t.tienda_id for t in maestros.tiendas()]
    assert len(ids) == len(set(ids))
    assert "ES-VLC-003" in ids
    for t in fisicas:
        assert re.fullmatch(r"[A-Z]{2}-[A-Z]{3}-\d{3}", t.tienda_id)
        assert t.formato in ("calle", "centro comercial", "outlet")
    online = [t for t in maestros.tiendas() if t.es_online]
    assert sorted(t.tienda_id for t in online) == ["ONL-CN", "ONL-ES", "ONL-FR", "ONL-JP", "ONL-US"]
    assert all(t.numero == "000" for t in online)


def test_monedas():
    assert {t.pais: t.moneda for t in maestros.tiendas()} == {
        "ES": "EUR", "FR": "EUR", "US": "USD", "JP": "JPY", "CN": "CNY",
    }
    assert maestros.a_moneda_local(39.95, "EUR") == 39.95
    assert maestros.a_moneda_local(39.95, "USD") == 43.15
    assert maestros.a_moneda_local(39.95, "JPY") == 6392
    assert maestros.a_moneda_local(39.95, "CNY") == 311.61


def test_clientes():
    clientes = maestros.clientes()
    assert len(clientes) == 4000
    assert clientes[0].cliente_id == "C-1" and clientes[-1].cliente_id == "C-4000"
    indice = maestros.indice_clientes()
    assert "C-4001" not in indice
    assert "C-0017" not in indice  # sin ceros a la izquierda
    assert set(maestros.clientes_por_pais()) == set(maestros.PAISES)
    premium = sum(c.segmento == "Premium" for c in clientes) / len(clientes)
    assert 0.17 < premium < 0.23
    assert {c.segmento for c in clientes} == {"Standard", "Premium"}


def test_clientes_fijos():
    c17 = maestros.indice_clientes()["C-17"]
    assert (c17.segmento, c17.provincia, c17.pais, c17.fecha_alta) == ("Standard", "Valencia", "ES", date(2025, 1, 10))
    assert c17.email == "cliente17@ejemplo.com"
    assert c17.telefono == "+34 600 000 017"
    c981 = maestros.indice_clientes()["C-981"]
    assert (c981.segmento, c981.provincia, c981.pais) == ("Standard", "Madrid", "ES")


def test_productos():
    productos = maestros.productos()
    assert len(productos) == 1200
    indice = maestros.indice_productos()
    assert len(indice) == 1200
    assert len({p.modelo for p in productos}) == 100
    p = indice["P-0412-ROJ-M"]
    assert (p.familia, p.color, p.talla, p.precio_catalogo) == ("vestidos", "Rojo", "M", 39.95)
    for p in productos:
        assert re.fullmatch(r"P-\d{4}-[A-Z]{3}-(S|M|L|XL)", p.producto_id)
        assert p.codigo_color in maestros.COLORES
        assert 0.30 * p.precio_catalogo - 0.01 <= p.coste_unitario <= 0.45 * p.precio_catalogo + 0.01
        if p.familia in ("abrigos", "punto"):
            assert p.temporada == "OI26"
        if p.familia == "baño":
            assert p.temporada == "PV26"
    por_modelo = Counter(p.modelo for p in productos)
    assert set(por_modelo.values()) == {12}  # 3 colores x 4 tallas


def test_determinista_entre_procesos():
    """Dos ejecuciones (procesos distintos) producen exactamente los mismos datos."""
    codigo = (
        "from comun import maestros; import hashlib;"
        "print(hashlib.sha256(repr((maestros.tiendas(), maestros.clientes(), maestros.productos()))"
        ".encode()).hexdigest())"
    )
    huellas = {
        subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, check=True).stdout
        for _ in range(2)
    }
    assert len(huellas) == 1
