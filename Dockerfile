FROM node:24-alpine AS frontend
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY . .
COPY --from=frontend /ui/dist /app/runtime_lab/static
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "runtime_lab.web"]
