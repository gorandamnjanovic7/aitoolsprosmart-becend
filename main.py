import os
import requests
import re
import json
import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, String, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional

# --- 1. SIGURNOSNA KONFIGURACIJA ---
SECRET_KEY = "matrix-super-tajni-kljuc-pro-smart-2026"
ALGORITHM = "HS256"
ADMIN_PASSWORD = "goran1972$@"
YOUTUBE_API_KEY = "AIzaSyCwy46TsBPW7LxKTjExhQbHhYhq8lyc2YM"
CHANNEL_ID = "UC6ilBUks_oFMSD8CE9qD6lQ"
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# --- 2. KONEKCIJA SA BAZOM (RAILWAY POSTGRES) ---
DATABASE_URL = "postgresql://postgres:MAiunMNahFMLqEjTXHLpcojyqyAjBjAx@postgres.railway.internal:5432/railway"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. SQLALCHEMY TABELE ---
class DBProduct(Base):
    __tablename__ = "products_v2"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, default="")
    type = Column(String, default="")
    headline = Column(String, default="")
    description = Column(Text, default="")
    price = Column(String, default="")
    priceLifetime = Column(String, default="")
    whopLink = Column(String, default="")
    media = Column(JSON, default=list)
    faq = Column(JSON, default=list)

class DBHiddenVideo(Base):
    __tablename__ = "hidden_videos"
    video_id = Column(String, primary_key=True)

Base.metadata.create_all(bind=engine)

# --- 4. MODELI ZA PODATKE (PYDANTIC) ---
class ProductBase(BaseModel):
    name: Optional[str] = ""
    type: Optional[str] = ""
    headline: Optional[str] = ""
    description: Optional[str] = ""
    price: Optional[str] = ""
    priceLifetime: Optional[str] = ""
    whopLink: Optional[str] = ""
    media: Optional[list] = []
    faq: Optional[list] = []

class ProductCreate(ProductBase):
    id: str

class Product(ProductBase):
    id: str
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    password: str

# --- 5. FASTAPI I CORS PODEŠAVANJA ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://69ab658eab97ec7022526987--aitoolsprosmart-web.netlify.app",
        "https://aitoolsprosmart-web.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 6. RUTE (API ENDPOINTS) ---

@app.post("/api/login")
async def login(req: LoginRequest):
    if req.password == ADMIN_PASSWORD:
        token = jwt.encode({"admin": True}, SECRET_KEY, algorithm=ALGORITHM)
        return {"token": token}
    raise HTTPException(status_code=401, detail="Pogrešna lozinka")

@app.get("/api/products", response_model=List[Product])
def get_products(db: Session = Depends(get_db)):
    return db.query(DBProduct).all()

@app.post("/api/products", response_model=Product)
def create_product(product: ProductCreate, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    db_product = DBProduct(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    db_product = db.query(DBProduct).filter(DBProduct.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Proizvod nije pronađen")
    db.delete(db_product)
    db.commit()
    return {"message": "Obrisano"}

# --- 7. YOUTUBE MOTOR (NOVO!) ---
@app.get("/api/youtube")
async def get_youtube_videos():
    try:
        url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={CHANNEL_ID}&part=snippet,id&order=date&maxResults=6&type=video"
        response = requests.get(url)
        data = response.json()
        
        if "items" not in data:
            return []
            
        videos = []
        for item in data["items"]:
            videos.append({
                "id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "publishedAt": item["snippet"]["publishedAt"]
            })
        return videos
    except Exception as e:
        print(f"YouTube Error: {e}")
        return []

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

