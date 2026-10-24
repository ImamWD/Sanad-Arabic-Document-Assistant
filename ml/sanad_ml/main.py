"""ml service.

M0 exposes only /health. B3 adds /embed and /rerank, with weights baked in at build time.
"""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Sanad ML", version="0.1.0", docs_url=None, redoc_url=None)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
async def health() -> Health:
    return Health(status="ok")
