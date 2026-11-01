"""Inferencia del batch transform. Sin las categorías del entrenamiento, las columnas categóricas fallan."""

import io
import json
import os

import pandas as pd
from entrenar import FICHERO_COLUMNAS, FICHERO_MODELO, preparar


def model_fn(model_dir):
    import xgboost as xgb

    modelo = xgb.XGBRegressor()
    modelo.load_model(os.path.join(model_dir, FICHERO_MODELO))
    with open(os.path.join(model_dir, FICHERO_COLUMNAS), encoding="utf-8") as f:
        columnas = json.load(f)
    return {"modelo": modelo, "features": columnas["features"], "categorias": columnas["categorias"]}


def input_fn(cuerpo, tipo):
    if tipo != "text/csv":
        raise ValueError(f"Tipo de contenido no admitido: {tipo}")
    texto = cuerpo.decode("utf-8") if isinstance(cuerpo, bytes) else cuerpo
    return pd.read_csv(io.StringIO(texto), header=None)


def predict_fn(datos, artefactos):
    datos = datos.copy()
    datos.columns = artefactos["features"]  # el CSV de entrada va sin cabecera, en este orden
    return artefactos["modelo"].predict(preparar(datos, artefactos["features"], artefactos["categorias"]))


def output_fn(prediccion, _accept):
    return "\n".join(f"{max(float(p), 0):.2f}" for p in prediccion) + "\n", "text/csv"
