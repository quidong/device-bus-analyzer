FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DBA_DB=/data/bus.sqlite
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install . && useradd -r -u 10001 dba && mkdir /data && chown dba /data
USER dba
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD dba healthcheck
CMD ["dba", "serve", "--port", "8080"]
