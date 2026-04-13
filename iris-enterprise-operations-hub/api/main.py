from fastapi import FastAPI
import uvicorn
db_url = 'postgresql://user:password@localhost/dbname'
app = FastAPI()

@app.get('/')
def read_root():
    return {'message': 'Hello, world!'}