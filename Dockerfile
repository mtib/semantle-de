FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
# Install deps, then drop pip/wheel and .pyc caches we won't need at runtime.
# setuptools stays — gunicorn imports pkg_resources from it.
RUN pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y pip wheel \
 && find /usr/local/lib/python3.10 -type d -name '__pycache__' -prune -exec rm -rf {} + \
 && find /usr/local/lib/python3.10 -type f -name '*.pyc' -delete

COPY . .

EXPOSE 8000

# --preload loads the app (including the memmap metadata) once in the master
# process so the 1 worker fork inherits it via copy-on-write, avoiding a
# duplicated ~150MB Python/flask/apscheduler footprint. Sync worker is plenty
# for this low-traffic endpoint.
CMD ["sh", "-c", "python prepare_data.py && exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --worker-class gthread --preload --worker-tmp-dir /dev/shm --timeout 120 semantle:app"]
