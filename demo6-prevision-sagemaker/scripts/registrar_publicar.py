"""Ruta opcional: registra el último modelo, lo aprueba si gana a la línea base y lanza un batch transform.

El batch transform sale de la versión aprobada, no del estimador. Nunca crea endpoints.

Uso:
    python demo6-prevision-sagemaker/scripts/registrar_publicar.py --wape-base 0.349 [--training-job <nombre>]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tarfile
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from comun.terraform import outputs  # noqa: E402

GRUPO = "prevision-ventas"
ETIQUETAS = [{"Key": "proyecto", "Value": "curso-aws-hp"}, {"Key": "sesion", "Value": "3"}]


def se_aprueba(wape_modelo: float, wape_base: float) -> bool:
    return wape_modelo < wape_base


def ultimo_job(sm) -> str:
    trabajos = sm.list_training_jobs(
        NameContains="prevision-ventas", StatusEquals="Completed", SortBy="CreationTime", SortOrder="Descending"
    )["TrainingJobSummaries"]
    if not trabajos:
        sys.exit("No hay ningún training job terminado: lanza antes lanzar_entrenamiento.py.")
    return trabajos[0]["TrainingJobName"]


def leer_wape(s3, uri_modelo: str) -> float:
    """El WAPE va dentro del model.tar.gz: el contenedor no admite metric_definitions propias."""
    bucket, clave = uri_modelo.removeprefix("s3://").split("/", 1)
    contenido = s3.get_object(Bucket=bucket, Key=clave)["Body"].read()
    with tarfile.open(fileobj=io.BytesIO(contenido), mode="r:gz") as tar:
        return json.load(tar.extractfile("metricas.json"))["wape"]


def registrar(sm, job: dict, wape: float) -> str:
    try:
        sm.create_model_package_group(ModelPackageGroupName=GRUPO, Tags=ETIQUETAS)
    except ClientError as e:
        if "already exists" not in str(e):
            raise
    entorno = {
        "SAGEMAKER_PROGRAM": "inferencia.py",
        "SAGEMAKER_SUBMIT_DIRECTORY": job["HyperParameters"]["sagemaker_submit_directory"].strip('"'),
        "SAGEMAKER_REGION": sm.meta.region_name,
    }
    return sm.create_model_package(
        ModelPackageGroupName=GRUPO,
        ModelPackageDescription=f"Training job {job['TrainingJobName']}. WAPE {wape:.4f}",
        ModelApprovalStatus="PendingManualApproval",
        CustomerMetadataProperties={"wape": f"{wape:.4f}", "training_job": job["TrainingJobName"]},
        InferenceSpecification={
            "Containers": [
                {
                    "Image": job["AlgorithmSpecification"]["TrainingImage"],
                    "ModelDataUrl": job["ModelArtifacts"]["S3ModelArtifacts"],
                    "Environment": entorno,
                }
            ],
            "SupportedContentTypes": ["text/csv"],
            "SupportedResponseMIMETypes": ["text/csv"],
            "SupportedTransformInstanceTypes": ["ml.m5.large"],
        },
    )["ModelPackageArn"]


def publicar(sm, paquete: str, rol: str, bucket: str) -> str:
    """Modelo temporal desde la versión aprobada, batch transform y borrado del modelo."""
    nombre = f"prevision-ventas-{int(time.time())}"
    sm.create_model(
        ModelName=nombre, ExecutionRoleArn=rol, PrimaryContainer={"ModelPackageName": paquete}, Tags=ETIQUETAS
    )
    sm.create_transform_job(
        TransformJobName=nombre,
        ModelName=nombre,
        TransformInput={
            "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": f"s3://{bucket}/ml/entrada_bt/"}},
            "ContentType": "text/csv",
            "SplitType": "Line",
        },
        TransformOutput={"S3OutputPath": f"s3://{bucket}/ml/predicciones_bt/", "AssembleWith": "Line"},
        TransformResources={"InstanceType": "ml.m5.large", "InstanceCount": 1},
        BatchStrategy="MultiRecord",
        Tags=ETIQUETAS,
    )
    while True:
        trabajo = sm.describe_transform_job(TransformJobName=nombre)
        print(f"  Batch transform: {trabajo['TransformJobStatus']}")
        if trabajo["TransformJobStatus"] in {"Completed", "Failed", "Stopped"}:
            break
        time.sleep(30)
    sm.delete_model(ModelName=nombre)
    if trabajo["TransformJobStatus"] != "Completed":
        sys.exit(f"El batch transform no ha terminado bien: {trabajo.get('FailureReason')}")
    return trabajo["TransformOutput"]["S3OutputPath"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--perfil", default=os.environ.get("AWS_PROFILE", "curso"))
    p.add_argument("--wape-base", type=float, required=True, help="WAPE de la línea base, del notebook")
    p.add_argument("--training-job", help="Por defecto, el último terminado")
    args = p.parse_args()

    tf = outputs("demo6-prevision-sagemaker/infra")
    sesion = boto3.Session(profile_name=args.perfil, region_name=tf["region"])
    sm = sesion.client("sagemaker")

    nombre = args.training_job or ultimo_job(sm)
    job = sm.describe_training_job(TrainingJobName=nombre)
    wape = leer_wape(sesion.client("s3"), job["ModelArtifacts"]["S3ModelArtifacts"])
    segundos = job.get("BillableTimeInSeconds", 0)
    print(f"Job {nombre}: WAPE {wape:.4f}, {job.get('TrainingTimeInSeconds', 0)} s, {segundos} s facturados.")

    paquete = registrar(sm, job, wape)
    print(f"Versión registrada, pendiente de aprobar: {paquete}")

    if not se_aprueba(wape, args.wape_base):
        print(f"No se aprueba ni se publica: WAPE {wape:.4f} no mejora a la línea base {args.wape_base:.4f}.")
        return
    sm.update_model_package(ModelPackageArn=paquete, ModelApprovalStatus="Approved")
    print(f"Aprobada: WAPE {wape:.4f} < línea base {args.wape_base:.4f}.")
    print(f"Salida del batch transform: {publicar(sm, paquete, tf['rol_ejecucion_arn'], tf['bucket_name'])}")


if __name__ == "__main__":
    main()
