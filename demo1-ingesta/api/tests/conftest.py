import os

# Antes de importar la API: región y stream ficticios, sin credenciales reales
os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("FIREHOSE_STREAM", "hp-retail-ventas")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
