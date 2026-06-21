FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN mkdir -p paperfirst && touch paperfirst/__init__.py
RUN pip install --no-cache-dir -e .

COPY paperfirst /app/paperfirst

EXPOSE 8000

CMD ["sh", "-c", "uvicorn paperfirst.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
