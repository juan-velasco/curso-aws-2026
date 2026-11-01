"""Prueba las funciones del notebook: ejecuta la celda marcada con la etiqueta «funciones»."""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

NOTEBOOK = Path(__file__).resolve().parents[2] / "notebooks" / "prevision_ventas.ipynb"
INICIO = date(2026, 7, 2)
DIAS = 120
PAISES = ["ES", "JP"]
FAMILIAS = ["abrigos", "baño"]


@pytest.fixture(scope="module")
def nb():
    celdas = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    codigo = [c for c in celdas if "funciones" in c["metadata"].get("tags", [])]
    assert len(codigo) == 1
    espacio = {}
    exec("".join(codigo[0]["source"]), espacio)
    return espacio


def _sk(dia: date) -> int:
    return int(dia.strftime("%Y%m%d"))


def _calendario() -> pd.DataFrame:
    dias = [INICIO + timedelta(days=n) for n in range(DIAS + 60)]
    return pd.DataFrame(
        {
            "fecha_sk": [_sk(d) for d in dias],
            "fecha": dias,
            "dia_semana": [d.isoweekday() for d in dias],
            "semana_iso": [d.isocalendar()[1] for d in dias],
            "mes": [d.month for d in dias],
            "temporada": ["PV" if d.month < 10 else "OI" for d in dias],
            "es_festivo": [False] * len(dias),
            "es_rebajas": [d.month == 7 for d in dias],
        }
    )


def _clima() -> pd.DataFrame:
    dias = [INICIO + timedelta(days=n) for n in range(DIAS + 60)]
    return pd.DataFrame(
        [{"fecha_sk": _sk(d), "pais": p, "temp_media": 20.0, "lluvia_mm": 0.0} for d in dias for p in PAISES]
    )


def _ventas(saltar=()) -> pd.DataFrame:
    """Las unidades son el número de día: permite comprobar los desplazamientos."""
    filas = []
    for n in range(DIAS):
        dia = INICIO + timedelta(days=n)
        for pais in PAISES:
            for familia in FAMILIAS:
                if (dia, pais, familia) not in saltar:
                    filas.append({"fecha_sk": _sk(dia), "pais": pais, "familia": familia, "unidades": n + 1})
    return pd.DataFrame(filas)


def _serie(df, pais="ES", familia="abrigos"):
    return df[(df.pais == pais) & (df.familia == familia)].reset_index(drop=True)


def test_rejilla_completa_con_ceros(nb):
    hueco = INICIO + timedelta(days=50)
    df = nb["serie_completa"](_ventas(saltar={(hueco, "ES", "abrigos")}), _calendario(), _clima())
    assert len(df) == DIAS * 2 * 2
    assert df.duplicated(["fecha_sk", "pais", "familia"]).sum() == 0
    assert _serie(df).loc[50, "unidades"] == 0
    assert df["unidades"].notna().all()


def test_dias_futuros_vacios_con_calendario_y_clima(nb):
    df = nb["serie_completa"](_ventas(), _calendario(), _clima(), dias_futuros=28)
    assert len(df) == (DIAS + 28) * 4
    futuro = df[df["unidades"].isna()]
    assert len(futuro) == 28 * 4
    assert futuro["fecha_sk"].min() == _sk(INICIO + timedelta(days=DIAS))
    assert futuro[["dia_semana", "temporada", "temp_media"]].notna().all().all()


def test_lag_28_no_usa_datos_futuros(nb):
    df = nb["anadir_features"](nb["serie_completa"](_ventas(), _calendario(), _clima(), dias_futuros=28))
    serie = _serie(df)
    assert serie.loc[:27, "lag_28"].isna().all()
    assert serie.loc[28, "lag_28"] == 1
    assert serie.loc[100, "lag_28"] == 73


def test_media_28_desplazada_28_dias(nb):
    df = nb["anadir_features"](nb["serie_completa"](_ventas(), _calendario(), _clima(), dias_futuros=28))
    serie = _serie(df)
    # Día 100 (0-based): media de los días 45 a 72, con unidades 46 a 73
    assert serie.loc[100, "media_28"] == pytest.approx(sum(range(46, 74)) / 28)


def test_retardos_de_los_dias_futuros_son_conocidos(nb):
    df = nb["anadir_features"](nb["serie_completa"](_ventas(), _calendario(), _clima(), dias_futuros=28))
    futuro = df[df["unidades"].isna()]
    assert futuro["lag_28"].notna().all()
    assert futuro["media_28"].notna().all()


def test_lag_364_vacio_con_120_dias(nb):
    df = nb["anadir_features"](nb["serie_completa"](_ventas(), _calendario(), _clima()))
    assert df["lag_364"].isna().all()


def test_retardos_no_mezclan_series(nb):
    ventas = _ventas()
    ventas.loc[ventas.pais == "JP", "unidades"] *= 1000
    df = nb["anadir_features"](nb["serie_completa"](ventas, _calendario(), _clima()))
    assert _serie(df, "ES").loc[28, "lag_28"] == 1
    assert _serie(df, "JP").loc[28, "lag_28"] == 1000


def test_tipos_para_xgboost(nb):
    df = nb["anadir_features"](nb["serie_completa"](_ventas(), _calendario(), _clima()))
    for columna in ("pais", "familia", "temporada"):
        assert df[columna].dtype == "category"
    assert df["es_rebajas"].dtype.kind == "i"
    assert df["es_festivo"].dtype.kind == "i"
    assert set(nb["FEATURES"]) <= set(df.columns)
    assert not set(nb["CLIMA"]) & set(nb["FEATURES_SIN_CLIMA"])


def test_split_temporal(nb):
    df = nb["anadir_features"](nb["serie_completa"](_ventas(), _calendario(), _clima()))
    train, valid, corte = nb["dividir"](df)
    assert corte == df.fecha.max() - pd.Timedelta(days=28)
    assert train.fecha.max() == corte
    assert valid.fecha.min() == corte + pd.Timedelta(days=1)
    assert valid.fecha.nunique() == 28
    assert len(train) + len(valid) == len(df)


def test_linea_base_por_serie_con_las_ultimas_4_semanas(nb):
    ventas = _ventas()
    ventas.loc[ventas.pais == "JP", "unidades"] *= 10
    df = nb["anadir_features"](nb["serie_completa"](ventas, _calendario(), _clima()))
    train, valid, corte = nb["dividir"](df)
    base = nb["linea_base"](train, valid, corte)
    assert base.index.equals(valid.index)
    # Entrenamiento: días 1 a 92. Últimas 4 semanas: días 65 a 92
    media = sum(range(65, 93)) / 28
    assert base[valid.pais == "ES"].unique() == pytest.approx([media])
    assert base[valid.pais == "JP"].unique() == pytest.approx([media * 10])


def test_wape(nb):
    real, prev = pd.Series([10.0, 10.0]), pd.Series([5.0, 15.0])
    assert nb["wape"](real, prev) == pytest.approx(0.5)


def test_salida_con_las_columnas_de_gold(nb):
    futuro = pd.DataFrame({"fecha_sk": [20261102], "pais": pd.Categorical(["ES"]), "familia": pd.Categorical(["baño"])})
    salida = nb["salida_prevision"](futuro, [-0.5], "2026-11-01")
    assert list(salida.columns) == ["fecha_calculo", "fecha_sk", "pais", "familia", "unidades_previstas"]
    assert salida.iloc[0].to_dict() == {
        "fecha_calculo": "2026-11-01",
        "fecha_sk": 20261102,
        "pais": "ES",
        "familia": "baño",
        "unidades_previstas": 0.0,
    }
