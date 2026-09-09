# app/main.py
from fastapi import FastAPI

app = FastAPI(title="FieldKit Core API")

@app.get("/healthz")
async def health():
    return {"status": "healthy", "service": "fieldkit"}