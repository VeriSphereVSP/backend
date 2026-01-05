import os
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI(title="VeriSphere Claim Decomposition")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("DECOMP_MODEL", "gpt-4o-mini")

class DecomposeRequest(BaseModel):
    text: str

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/v1/decompose")
def decompose(req: DecomposeRequest):
    prompt = (
        "Split the following into atomic factual claims. "
        "Return a JSON array of strings.\n\n"
        f"{req.text}"
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    return {
        "atoms": resp.choices[0].message.content
    }

