FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# SQLite file lives at ./data/control_plane.db relative to this WORKDIR
# (see DEFAULT_DB_PATH in app/database.py) -- mount a volume there to persist
# agents/servers/policy/audit data across container restarts.
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
