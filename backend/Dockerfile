FROM python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286

WORKDIR /app

# Copy source first, then install (setuptools needs the package to exist)
COPY pyproject.toml .
COPY datum/ datum/
COPY alembic/ alembic/
COPY alembic.ini .

RUN pip install --no-cache-dir .

EXPOSE 8001
CMD ["uvicorn", "datum.main:app", "--host", "0.0.0.0", "--port", "8001"]
