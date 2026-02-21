from fastapi import FastAPI

app = FastAPI(title="Green API")

@app.get("/")
def root():
    return {"message": "Green API running 🚀"}
