FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir -c requirements.lock .
EXPOSE 8000
CMD ["uvicorn", "compute_market.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
