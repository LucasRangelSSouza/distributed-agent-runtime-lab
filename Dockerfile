FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
