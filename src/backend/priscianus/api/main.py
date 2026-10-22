from fastapi import FastAPI

app = FastAPI(title="Priscianus")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
