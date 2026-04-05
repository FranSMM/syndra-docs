## Playbook 2: Optimized Dockerfile for Python/FastAPI

**Usage:** Building lightweight, production-ready images while avoiding temporary cache files.

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code
COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY ./app /code/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```
