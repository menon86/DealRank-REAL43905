from fastapi import FastAPI

app = FastAPI(title="DealRank API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Deal CRUD and /rank routes are added in the API scaffolding phase
# (see docs/build-plan.md) — not wired yet.
