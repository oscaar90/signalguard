FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY signalguard /app/signalguard

RUN pip install --no-cache-dir .

ENTRYPOINT ["signalguard"]
CMD ["watch", "--no-llm", "--interval", "30"]
