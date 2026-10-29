FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV FITLAB_DB_PATH=/data/fitlab.db FITLAB_STORAGE_PATH=/data FITLAB_SECURE_COOKIES=true
CMD ["python", "app.py"]
