FROM python:3.11-slim
WORKDIR /app
COPY teams_webhook.py .
# No extra packages needed — stdlib only (http.server, urllib)
CMD ["python", "teams_webhook.py"]
