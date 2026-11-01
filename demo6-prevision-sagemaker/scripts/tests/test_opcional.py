import importlib.util
from pathlib import Path

import pandas as pd

from registrar_publicar import se_aprueba


def _cargar(nombre):
    ruta = Path(__file__).resolve().parents[2] / "sagemaker" / f"{nombre}.py"
    especificacion = importlib.util.spec_from_file_location(f"sm_{nombre}", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


FEATURES = ["pais", "mes"]
CATEGORIAS = {"pais": ["CN", "ES", "JP"]}


def test_preparar_conserva_orden_y_categorias():
    entrenar = _cargar("entrenar")
    df = pd.DataFrame({"mes": [1], "extra": [0], "pais": ["JP"]})
    salida = entrenar.preparar(df, FEATURES, CATEGORIAS)
    assert list(salida.columns) == FEATURES
    assert list(salida["pais"].cat.categories) == ["CN", "ES", "JP"]
    assert salida["pais"].cat.codes.iloc[0] == 2  # el mismo código que en el entrenamiento


def test_ultimo_checkpoint(tmp_path):
    entrenar = _cargar("entrenar")
    assert entrenar.ultimo_checkpoint(str(tmp_path)) == (None, 0)
    for n in (24, 99, 49):
        (tmp_path / f"checkpoint_{n}.json").touch()
    ruta, hechas = entrenar.ultimo_checkpoint(str(tmp_path))
    assert ruta.endswith("checkpoint_99.json")
    assert hechas == 100


def test_solo_se_aprueba_si_gana_a_la_linea_base():
    assert se_aprueba(0.30, 0.35)
    assert not se_aprueba(0.35, 0.35)
    assert not se_aprueba(0.40, 0.35)
