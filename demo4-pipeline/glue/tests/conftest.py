import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    sesion = (
        SparkSession.builder.master("local[1]")
        .appName("tests-transformaciones")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")  # como en los jobs
        .getOrCreate()
    )
    sesion.sparkContext.setLogLevel("ERROR")
    yield sesion
    sesion.stop()
