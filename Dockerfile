FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc && apt-get autoremove -y

COPY app/ ./

CMD ["python", "main.py"]
