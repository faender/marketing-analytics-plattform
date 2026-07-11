FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000

# Invoked via `bash entrypoint.sh` rather than relying on the file's own
# execute bit: the dev bind mount (docker-compose's `.:/app`) replaces the
# image's copy with the host's file at runtime, and a Windows/WSL host
# filesystem doesn't reliably preserve the executable bit across that mount.
ENTRYPOINT ["bash", "entrypoint.sh"]
