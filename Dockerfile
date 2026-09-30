FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY data ./data
COPY main.py ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8088
CMD ["python", "main.py"]
