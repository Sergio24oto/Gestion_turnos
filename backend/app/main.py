from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, SessionLocal, engine
from .routes import appointments, auth, availability, blocks, services
from .seed import seed_initial_data

app = FastAPI(title="API Turnos Peluqueria", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(services.router, prefix="/api")
app.include_router(availability.router, prefix="/api")
app.include_router(appointments.router, prefix="/api")
app.include_router(blocks.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
