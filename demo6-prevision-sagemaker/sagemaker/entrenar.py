"""Entrenamiento en script mode: el modelo del notebook como training job.

Corre en el contenedor de XGBoost 1.7-1. Guarda en model_dir el modelo, las features y las categorías:
la inferencia debe usar exactamente las mismas.
"""

import argparse
import glob
import json
import os
import re

import pandas as pd

OBJETIVO = "unidades"
CATEGORICAS = ["pais", "familia", "temporada"]
FICHERO_MODELO = "xgboost-model.json"
FICHERO_COLUMNAS = "columnas.json"
FICHERO_METRICAS = "metricas.json"
DIR_CHECKPOINTS = "/opt/ml/checkpoints"


def leer_canal(ruta):
    ficheros = sorted(glob.glob(os.path.join(ruta, "*.csv")))
    return pd.concat([pd.read_csv(f) for f in ficheros], ignore_index=True)


def preparar(df, features, categorias):
    """Columnas en el orden del entrenamiento y categóricas con las categorías del entrenamiento."""
    df = df[features].copy()
    for columna, valores in categorias.items():
        df[columna] = pd.Categorical(df[columna], categories=valores)
    return df


def wape(real, prev):
    return abs(real - prev).sum() / real.sum()


def ultimo_checkpoint(directorio):
    """El checkpoint más avanzado y sus iteraciones hechas: al reanudar tras una interrupción de Spot."""
    ficheros = glob.glob(os.path.join(directorio, "checkpoint_*.json"))
    if not ficheros:
        return None, 0
    numero = lambda f: int(re.search(r"checkpoint_(\d+)\.json$", f).group(1))  # noqa: E731
    ultimo = max(ficheros, key=numero)
    return ultimo, numero(ultimo) + 1


def main():
    import xgboost as xgb

    p = argparse.ArgumentParser()
    p.add_argument("--max_depth", type=int, default=6)
    p.add_argument("--eta", type=float, default=0.05)
    p.add_argument("--n_estimators", type=int, default=800)
    p.add_argument("--early_stopping_rounds", type=int, default=50)
    p.add_argument("--model_dir", default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    p.add_argument("--train", default=os.environ.get("SM_CHANNEL_TRAIN"))
    p.add_argument("--validation", default=os.environ.get("SM_CHANNEL_VALIDATION"))
    args, _ = p.parse_known_args()

    train, valid = leer_canal(args.train), leer_canal(args.validation)
    features = [c for c in train.columns if c != OBJETIVO]
    categorias = {c: sorted(pd.concat([train[c], valid[c]]).dropna().unique().tolist()) for c in CATEGORICAS}
    x_train, x_valid = preparar(train, features, categorias), preparar(valid, features, categorias)

    os.makedirs(DIR_CHECKPOINTS, exist_ok=True)
    previo, hechas = ultimo_checkpoint(DIR_CHECKPOINTS)
    if previo:
        print(f"Se reanuda desde {previo}: {hechas} iteraciones hechas")
    modelo = xgb.XGBRegressor(
        n_estimators=max(args.n_estimators - hechas, 1),
        max_depth=args.max_depth,
        learning_rate=args.eta,
        objective="reg:tweedie",
        tree_method="hist",
        enable_categorical=True,
        early_stopping_rounds=args.early_stopping_rounds,
        callbacks=[xgb.callback.TrainingCheckPoint(directory=DIR_CHECKPOINTS, name="checkpoint", iterations=25)],
    )
    modelo.fit(
        x_train, train[OBJETIVO], eval_set=[(x_valid, valid[OBJETIVO])], xgb_model=previo, verbose=False
    )

    wape_modelo = float(wape(valid[OBJETIVO], modelo.predict(x_valid)))
    print(f"wape={wape_modelo:.4f}")

    # El contenedor de XGBoost no admite metric_definitions propias: registrar_publicar.py lo lee de aquí
    with open(os.path.join(args.model_dir, FICHERO_METRICAS), "w", encoding="utf-8") as f:
        json.dump({"wape": wape_modelo}, f)
    modelo.save_model(os.path.join(args.model_dir, FICHERO_MODELO))
    with open(os.path.join(args.model_dir, FICHERO_COLUMNAS), "w", encoding="utf-8") as f:
        json.dump({"features": features, "categorias": categorias}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
