FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir .

ENV PORT=8000
EXPOSE 8000

CMD ["product-memory-mcp-http"]
