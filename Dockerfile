# One container for the hosted demo: build the React front end, then serve it and the API with FastAPI.
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# Bake the Whisper speech model into the image so voice works without downloading at runtime.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')" || echo "speech model not baked; it downloads on first use"
COPY backend/ backend/
COPY data/ data/
COPY --from=web /app/frontend/dist frontend/dist
WORKDIR /app/backend
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn aura.main:app --host 0.0.0.0 --port ${PORT}"]
