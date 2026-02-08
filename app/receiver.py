# receiver.py
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.post("/commands")
async def commands(req: Request):
    body = await req.json()
    print("\n=== GOT COMMANDS ===")
    print(body)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9090)
