FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app/shared
COPY shared/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY shared ./shared
COPY services/ai-orchestrator/app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
