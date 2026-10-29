# Se construye desde la raíz del repositorio (context: .. en docker-compose.yml)
# para poder copiar comun/, la única fuente de los datos maestros.
FROM python:3.12-slim
WORKDIR /app
COPY demo1-ingesta/generador/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY comun/ ./comun
COPY demo1-ingesta/generador/generador.py .
ENV HOME=/tmp PYTHONUNBUFFERED=1 SALIDA_DIR=/app/salida
USER 1000
CMD ["python", "generador.py"]
