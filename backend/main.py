from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from database import engine, Base
from routers import auth_runner, auth_admin, admin_geral, admin_condominio, tasks, cadastro, whatsapp, setup, migrate

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Postino API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_runner.router)
app.include_router(auth_admin.router)
app.include_router(admin_geral.router)
app.include_router(admin_condominio.router)
app.include_router(tasks.router)
app.include_router(cadastro.router)
app.include_router(whatsapp.router)
app.include_router(setup.router)
app.include_router(migrate.router)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/admin", StaticFiles(directory=os.path.join(BASE_DIR, "admin"), html=True), name="admin")
app.mount("/app", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="frontend")
app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "landing"), html=True), name="landing")
