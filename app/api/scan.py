from fastapi import FastAPI
import univcorn

app = FastAPI()

# Testing api
@app.get("/")
def test():
    return "The API is working"

