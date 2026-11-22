FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 RISKMINER_ENV=production RISKMINER_DB=/data/riskminer.sqlite3
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends antiword tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
COPY riskminer riskminer
COPY fixtures fixtures
COPY static static
RUN useradd --system --uid 10001 --create-home riskminer && mkdir /data && chown riskminer /data
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["python","-m","uvicorn","riskminer.service:app","--host","0.0.0.0","--port","8080","--no-proxy-headers","--limit-concurrency","64"]
