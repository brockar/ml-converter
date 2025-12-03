FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY gunicorn.conf.py ./

# Create non-root user
RUN useradd -m -u 1000 appuser

RUN mkdir -p /app/tmp && \
    chown -R appuser:appuser /app

USER appuser
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "src.app:app"]
