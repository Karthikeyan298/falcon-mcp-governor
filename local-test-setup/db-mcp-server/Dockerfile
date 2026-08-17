FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY db_mcp_server ./db_mcp_server

ENV DB_MCP_HOST=0.0.0.0 \
    DB_MCP_PORT=8000 \
    DB_MCP_SQLITE_PATH=/app/data/app.db

VOLUME ["/app/data"]

EXPOSE 8000

CMD ["python", "-m", "db_mcp_server.server"]
