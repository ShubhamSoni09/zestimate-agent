# Playwright base image includes Chromium and OS deps.
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "zestimate_agent.server:app", "--host", "0.0.0.0", "--port", "8000"]
