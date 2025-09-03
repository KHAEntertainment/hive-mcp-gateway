from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/mcp/servers")
def get_servers():
    return [
        {"name": "test_server", "status": "connected", "tool_count": 5}
    ]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
