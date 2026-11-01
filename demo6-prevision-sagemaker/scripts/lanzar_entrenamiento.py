"""Ruta opcional: lanza el modelo como training job en Spot. Nunca crea endpoints.

Necesita requirements-opcional.txt y que el notebook haya escrito ml/train/ y ml/valid/
(GENERAR_RUTA_OPCIONAL = True). Se lanza desde el portátil, con el rol de Studio para el job.

Uso:
    python demo6-prevision-sagemaker/scripts/lanzar_entrenamiento.py [--perfil curso]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3
import sagemaker
from sagemaker.xgboost.estimator import XGBoost

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from comun.terraform import outputs  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    args = p.parse_args()

    tf = outputs("demo6-prevision-sagemaker/infra")
    bucket = tf["bucket_name"]
    sesion = sagemaker.Session(
        boto3.Session(profile_name=args.perfil, region_name=tf["region"]),
        default_bucket=bucket,  # sin esto, el SDK crea un bucket sagemaker-<región>-<cuenta>
        default_bucket_prefix="ml/sagemaker",
    )

    est = XGBoost(
        entry_point="entrenar.py",
        source_dir=str(RAIZ / "demo6-prevision-sagemaker" / "sagemaker"),
        framework_version="1.7-1",
        role=tf["rol_ejecucion_arn"],
        instance_type="ml.m5.large",
        instance_count=1,
        use_spot_instances=True,
        max_run=900,
        max_wait=1800,
        checkpoint_s3_uri=f"s3://{bucket}/ml/checkpoints/",
        output_path=f"s3://{bucket}/ml/modelos/",
        code_location=f"s3://{bucket}/ml/codigo",
        base_job_name="prevision-ventas",
        hyperparameters={"max_depth": 6, "eta": 0.05},
        sagemaker_session=sesion,
        tags=[{"Key": "proyecto", "Value": "curso-aws-hp"}, {"Key": "sesion", "Value": "3"}],
    )
    est.fit({"train": f"s3://{bucket}/ml/train/", "validation": f"s3://{bucket}/ml/valid/"})
    print(f"Training job: {est.latest_training_job.job_name}")


if __name__ == "__main__":
    main()
