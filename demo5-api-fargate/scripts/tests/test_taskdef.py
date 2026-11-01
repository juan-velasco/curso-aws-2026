from pathlib import Path

from generar_taskdef import claves_aws, generar
from ip_tarea import eni_de_tarea

PLANTILLA = (Path(__file__).resolve().parents[2] / "taskdef.json.tpl").read_text(encoding="utf-8")
VALORES = {
    "execution_role_arn": "arn:aws:iam::123456789012:role/curso-aws-hp-ecs-ejecucion",
    "task_role_arn": "arn:aws:iam::123456789012:role/api-ventas-task",
    "account_id": "123456789012",
    "region": "eu-west-1",
    "stream_name": "hp-retail-ventas",
    "log_group": "/ecs/api-ventas",
}


def _taskdef():
    return generar(PLANTILLA, VALORES)


def test_no_quedan_marcadores():
    assert "${" not in str(_taskdef())


def test_incluye_la_region_que_exige_la_api():
    entorno = {v["name"]: v["value"] for v in _taskdef()["containerDefinitions"][0]["environment"]}
    assert entorno == {"FIREHOSE_STREAM": "hp-retail-ventas", "AWS_REGION": "eu-west-1"}


def test_sin_claves_aws():
    assert claves_aws(_taskdef()) == set()


def test_detecta_claves_aws():
    taskdef = _taskdef()
    taskdef["containerDefinitions"][0]["environment"].append({"name": "AWS_SECRET_ACCESS_KEY", "value": "x"})
    assert claves_aws(taskdef) == {"AWS_SECRET_ACCESS_KEY"}


def test_valores_de_la_diapositiva():
    taskdef = _taskdef()
    assert (taskdef["cpu"], taskdef["memory"]) == ("256", "512")
    assert taskdef["runtimePlatform"]["cpuArchitecture"] == "ARM64"
    contenedor = taskdef["containerDefinitions"][0]
    assert contenedor["portMappings"] == [{"containerPort": 8000}]
    assert contenedor["logConfiguration"]["logDriver"] == "awslogs"
    assert contenedor["image"] == "123456789012.dkr.ecr.eu-west-1.amazonaws.com/api-ventas:1.0.0"


def test_roles_propios():
    taskdef = _taskdef()
    assert taskdef["executionRoleArn"].endswith("role/curso-aws-hp-ecs-ejecucion")
    assert taskdef["taskRoleArn"].endswith("role/api-ventas-task")


def test_eni_de_la_tarea():
    tarea = {
        "attachments": [
            {"type": "Otro", "details": []},
            {
                "type": "ElasticNetworkInterface",
                "details": [{"name": "subnetId", "value": "s"}, {"name": "networkInterfaceId", "value": "eni-1"}],
            },
        ]
    }
    assert eni_de_tarea(tarea) == "eni-1"
    assert eni_de_tarea({"attachments": []}) is None
