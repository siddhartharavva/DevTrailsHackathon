from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from onboarding.routes import router as onboarding_router
from trigger_engine.routes import router as trigger_router
from claims.routes import router as claims_router
from admin.routes import router as admin_router

app = FastAPI(
    title="ShieldShift API",
    description="Parametric Income Insurance for Gig Delivery Workers",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding_router, prefix="/api/onboarding", tags=["Onboarding"])
app.include_router(trigger_router,    prefix="/api/triggers",   tags=["Triggers"])
app.include_router(claims_router,     prefix="/api/claims",     tags=["Claims"])
app.include_router(admin_router,      prefix="/api/admin",      tags=["Admin"])

@app.get("/")
def root():
    return {"service": "ShieldShift API", "status": "running", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "ok"}
