from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================================
# KLJUČNA PROMENA ZA TRAJNO ČUVANJE: 
# Ako smo na serveru (Railway) gde postoji trajni disk '/data', čuvaj tu!
# Ako smo na tvom kompu, čuvaj lokalno. NEMA VIŠE BRISANJA!
# ======================================================================
if os.path.exists("/data"):
    DB_FILE = "/data/products.json"
else:
    DB_FILE = "products.json"

def load_db():
    if not os.path.exists(DB_FILE): return []
    try:
        with open(DB_FILE, "r") as f: 
            return json.load(f)
    except: 
        return []

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.get("/api/products")
async def get_products():
    return load_db()

@app.post("/api/products")
async def create_product(request: Request):
    product_data = await request.json()
    db_data = load_db()
    product_data['id'] = str(product_data.get('id'))
    db_data.append(product_data)
    save_db(db_data)
    return {"status": "deployed"}

@app.put("/api/products/{product_id}")
async def update_product(product_id: str, request: Request):
    updated_data = await request.json()
    db_data = load_db()
    for i, p in enumerate(db_data):
        if str(p.get('id')) == str(product_id):
            updated_data['id'] = str(product_id)
            db_data[i] = updated_data
            save_db(db_data)
            return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Not found")

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str):
    db_data = load_db()
    db_data = [p for p in db_data if str(p.get('id')) != str(product_id)]
    save_db(db_data)
    return {"status": "terminated"}

@app.get("/api/youtube")
async def get_videos(): 
    return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))