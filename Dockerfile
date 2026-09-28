FROM python:3.12-slim
WORKDIR /app
COPY failure_mode /app/failure_mode
COPY web /app/web
COPY data/raw /app/data/raw
RUN python -m failure_mode.ingest --cached && useradd --system --uid 10001 appuser && chmod -R a+rX /app
USER appuser
EXPOSE 8000
CMD ["python", "-m", "failure_mode.server", "--host", "0.0.0.0", "--port", "8000"]
