FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock /app/
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md /app/
COPY src /app/src
RUN pip install --no-deps . && useradd --uid 10001 --create-home jev && mkdir /data && chown jev:jev /data
USER 10001:10001
CMD ["jev-decision-mcp", "--transport", "http"]
