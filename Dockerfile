# The web app's backend (app/server.py) wrapping the demo engine.
# Static front end deploys separately to GitHub Pages; this container
# holds the credentials and runs the pipeline.
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV APS_DB=turso PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]
