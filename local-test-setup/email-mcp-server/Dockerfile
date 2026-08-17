FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY email_mcp_server ./email_mcp_server

ENV EMAIL_MCP_HOST=0.0.0.0 \
    EMAIL_MCP_PORT=8002

EXPOSE 8002

CMD ["python", "-m", "email_mcp_server.server"]
