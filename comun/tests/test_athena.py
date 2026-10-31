"""Tests de los ayudantes de Athena, con el cliente simulado por Stubber."""

import boto3
import pytest
from botocore.stub import Stubber

from comun import athena


def test_sustituir_respeta_los_marcadores_de_athena():
    sql = "LOCATION 's3://${bucket}/x/anio=${anio}/'"
    assert athena.sustituir(sql, {"bucket": "lago"}) == "LOCATION 's3://lago/x/anio=${anio}/'"


def test_separar_sentencias():
    texto = """
    -- comentario con ; punto y coma
    SELECT ';' AS a;
    SELECT 2 -- final; de línea
    ;
    -- solo comentario
    """
    assert athena.separar_sentencias(texto) == ["SELECT ';' AS a", "SELECT 2"]


def test_separar_sentencias_con_cuerpo_de_procedimiento():
    texto = "CREATE PROCEDURE p() AS $$ BEGIN SELECT 1; SELECT ';'; END; $$ LANGUAGE plpgsql; SELECT 2;"
    assert athena.separar_sentencias(texto) == [
        "CREATE PROCEDURE p() AS $$ BEGIN SELECT 1; SELECT ';'; END; $$ LANGUAGE plpgsql",
        "SELECT 2",
    ]


@pytest.fixture
def cliente():
    return boto3.client("athena", region_name="eu-west-1", aws_access_key_id="t", aws_secret_access_key="t")


def test_ejecutar_devuelve_filas_y_bytes(cliente):
    with Stubber(cliente) as stub:
        stub.add_response(
            "start_query_execution", {"QueryExecutionId": "q1"}, {"QueryString": "SELECT 1 AS n", "WorkGroup": "curso"}
        )
        stub.add_response(
            "get_query_execution",
            {
                "QueryExecution": {
                    "StatementType": "DML",
                    "Status": {"State": "SUCCEEDED"},
                    "Statistics": {"DataScannedInBytes": 2048},
                }
            },
        )
        stub.add_response(
            "get_query_results",
            {
                "ResultSet": {
                    "ResultSetMetadata": {"ColumnInfo": [{"Name": "n", "Type": "integer"}]},
                    "Rows": [{"Data": [{"VarCharValue": "n"}]}, {"Data": [{"VarCharValue": "1"}]}],
                }
            },
        )
        resultado = athena.ejecutar(cliente, "SELECT 1 AS n")
    assert resultado.primera == {"n": "1"}
    assert resultado.bytes_escaneados == 2048
    assert athena.formato_bytes(resultado.bytes_escaneados) == "2.00 KB"


def test_ejecutar_lanza_error_si_falla(cliente):
    with Stubber(cliente) as stub:
        stub.add_response("start_query_execution", {"QueryExecutionId": "q1"})
        stub.add_response(
            "get_query_execution",
            {"QueryExecution": {"Status": {"State": "FAILED", "StateChangeReason": "SYNTAX_ERROR"}}},
        )
        with pytest.raises(athena.ErrorAthena, match="SYNTAX_ERROR"):
            athena.ejecutar(cliente, "SELECT")
