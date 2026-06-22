FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ARG SERVICE_MODULE
ENV SERVICE_MODULE=${SERVICE_MODULE}
CMD python -m ${SERVICE_MODULE}
