FROM python:3.12-slim

WORKDIR /app

# Copy source first, then install (setuptools needs the package to exist)
COPY pyproject.toml .
COPY datum/ datum/
COPY alembic/ alembic/
COPY alembic.ini .

RUN pip install --no-cache-dir .

EXPOSE 8001
CMD ["uvicorn", "datum.main:app", "--host", "0.0.0.0", "--port", "8001"]
