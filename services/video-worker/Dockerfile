FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app/shared
COPY shared/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN pip install --no-cache-dir imageio-ffmpeg==0.6.0 pillow==11.1.0
COPY shared ./shared
COPY services/video-worker/app ./app
CMD ["python", "-m", "app.worker_loop"]
