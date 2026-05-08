FROM python:3.11-slim

WORKDIR /app

COPY backend/ /app/
COPY Bases/ /Bases/
COPY Flags\ LiveScore.txt /Flags LiveScore.txt
COPY Flags\ BetCity.txt /Flags BetCity.txt

RUN pip install --no-cache-dir fastapi uvicorn requests sqlalchemy apscheduler

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
