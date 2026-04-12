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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/video/demo.mp4")
def video_demo():
    from fastapi.responses import FileResponse
    path = "/data/postino.mp4"
    if os.path.exists(path):
        return FileResponse(path, media_type="video/mp4")
    return {"error": "not found"}

@app.get("/video/demo2.mp4")
def video_demo2():
    from fastapi.responses import FileResponse
    path = "/data/2video.mp4"
    if os.path.exists(path):
        return FileResponse(path, media_type="video/mp4")
    return {"error": "not found"}

@app.get("/config")
def config():
    return {"whatsapp_number": os.getenv("WHATSAPP_NUMBER", "")}

@app.get("/")
def landing():
    from fastapi.responses import FileResponse
    for candidate in [
        os.path.join(BASE_DIR, "landing", "index.html"),
        "/landing/index.html",
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate)
    return {"status": "ok", "app": "Postino API"}


@app.get("/favicon.png")
def favicon():
    from fastapi.responses import FileResponse
    for candidate in [
        os.path.join(BASE_DIR, "landing", "favicon.png"),
        "/landing/favicon.png",
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="image/png")
    return {"error": "not found"}

@app.get("/termos")
def termos():
    from fastapi.responses import FileResponse
    for candidate in [
        os.path.join(BASE_DIR, "landing", "termos.html"),
        "/landing/termos.html",
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate)
    return {"error": "not found"}
