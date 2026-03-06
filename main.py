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
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# --- 2. KONEKCIJA (SA ZASTITOM PROTIV PUCANJA) ---
DATABASE_URL = "postgresql://postgres:MAiunMNahFMLqEjTXHLpcojyqyAjBjAx@ballast.proxy.rlwy.net:24562/railway"
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

# --- 4. MODELI ---
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

# --- AUTENTIFIKACIJA RUTA ---
@app.post("/api/login")
def login(req: LoginRequest):
    if req.password == ADMIN_PASSWORD:
        expiration = datetime.utcnow() + timedelta(hours=24) # Token vazi 24 sata
        token = jwt.encode({"sub": "admin", "exp": expiration}, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token}
    raise HTTPException(status_code=401, detail="Access Denied")

# --- RUTE ZA PROIZVODE ---
# OTVORENO ZA SVE (Prikaz na sajtu)
@app.get("/api/products", response_model=List[Product])
def read_products(db: Session = Depends(get_db)):
    return db.query(DBProduct).all()

# ZAKLJUČANO (Mora imati token)
@app.post("/api/products")
def create_product(product: ProductCreate, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    db_product = DBProduct(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

# ZAKLJUČANO
@app.put("/api/products/{product_id}")
def update_product(product_id: str, product: ProductBase, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    db_product = db.query(DBProduct).filter(DBProduct.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)
        
    db.commit()
    db.refresh(db_product)
    return db_product

# ZAKLJUČANO
@app.delete("/api/products/{product_id}")
def delete_product(product_id: str, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    db_product = db.query(DBProduct).filter(DBProduct.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(db_product)
    db.commit()
    return {"status": "deleted"}

# ZAKLJUČANO
@app.post("/api/hidden-videos/{video_id}")
def hide_video(video_id: str, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    db_hidden = DBHiddenVideo(video_id=video_id)
    db.add(db_hidden)
    db.commit()
    return {"status": f"Video {video_id} is now hidden"}

# ZAKLJUČANO
@app.delete("/api/hidden-videos/{video_id}")
def unhide_video(video_id: str, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    db_video = db.query(DBHiddenVideo).filter(DBHiddenVideo.video_id == video_id).first()
    if db_video:
        db.delete(db_video)
        db.commit()
    return {"status": "unhidden"}

# OTVORENO ZA SVE
@app.get("/api/videos")
def get_youtube_videos(db: Session = Depends(get_db)):
    MY_CHANNEL_ID = "UC6ilBUks_oFMSD8CE9qD6lQ"
    url = f"https://www.youtube.com/channel/{MY_CHANNEL_ID}/videos"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    try:
        blacklisted = [v.video_id for v in db.query(DBHiddenVideo).all()]
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        videos = []
        seen_ids = set()
        matches = re.findall(r'"videoId":"([^"]+)".*?"title":\{"runs":\[\{"text":"([^"]+)"\}\]', response.text)

        for vid_id, title in matches:
            if vid_id in blacklisted: continue
            if vid_id not in seen_ids and len(vid_id) == 11:
                clean_title = title.encode('utf-8').decode('unicode-escape').replace('\\"', '"')
                videos.append({"title": clean_title, "url": f"https://www.youtube.com/watch?v={vid_id}"})
                seen_ids.add(vid_id)
            if len(videos) >= 8: break
                
        return videos
    except Exception as e:

        return []
