FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app
# El usuario 1000 no tiene /home: HOME escribible para boto3 (caché de credenciales SSO)
ENV HOME=/tmp PYTHONUNBUFFERED=1
USER 1000
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
