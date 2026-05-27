import os
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent / '.env')

from auth import create_access_token, get_current_user, require_admin
from database import (
    create_client,
    create_log,
    create_user,
    delete_client,
    delete_user,
    get_latest_draft,
    get_user_by_login,
    init_db,
    list_clients,
    list_logs,
    list_users,
    mark_log_sent,
    verify_password,
)
from pdf_parser import extract_fields
from sheets import send_to_sheets


app = FastAPI(title="Logistics PDF Processor")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    login: str
    password: str


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1)
    login: str = Field(min_length=1)
    password: str = Field(min_length=6)
    role: str = "user"


class SendToSheetsRequest(BaseModel):
    extracted_data: dict[str, Any]
    filename: str


class CreateClientRequest(BaseModel):
    name: str = Field(min_length=1)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, str]:
    user = get_user_by_login(payload.login)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid login or password")
    access_token = create_access_token({"sub": str(user["id"]), "role": user["role"]})
    return {"access_token": access_token, "role": user["role"], "name": user["name"]}


@app.post("/auth/logout")
def logout(_current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, bool]:
    return {"success": True}


@app.post("/pdf/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    suffix = Path(file.filename).suffix or ".pdf"
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            while chunk := await file.read(1024 * 1024):
                tmp.write(chunk)

        extracted = extract_fields(temp_path)
        create_log(current_user["id"], file.filename, extracted, False)
        return extracted
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/pdf/send-to-sheets")
async def post_to_sheets(
    payload: SendToSheetsRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    result = await send_to_sheets(payload.extracted_data, current_user["name"], payload.filename)
    if result["success"]:
        mark_log_sent(current_user["id"], payload.filename, payload.extracted_data)
    return result


@app.get("/pdf/latest-draft")
def latest_draft(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    draft = get_latest_draft(current_user["id"])
    if draft is None:
        return {"draft": None}
    return {"draft": draft}


@app.get("/admin/users")
def admin_users(_admin: dict[str, Any] = Depends(require_admin)) -> list[dict[str, Any]]:
    return list_users()


@app.post("/admin/users")
def admin_create_user(
    payload: CreateUserRequest,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    if payload.role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    try:
        return create_user(payload.name, payload.login, payload.password, payload.role)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="User login must be unique") from exc


@app.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, bool]:
    return {"success": delete_user(user_id)}


@app.get("/admin/logs")
def admin_logs(_admin: dict[str, Any] = Depends(require_admin)) -> list[dict[str, Any]]:
    return list_logs()


@app.get("/clients")
def clients(_current_user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    return list_clients()


@app.post("/clients")
def add_client(
    payload: CreateClientRequest,
    _current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return create_client(payload.name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Клиент уже есть в списке") from exc


@app.delete("/clients/{client_id}")
def remove_client(
    client_id: int,
    _current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, bool]:
    return {"success": delete_client(client_id)}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{page_name}.html")
def page(page_name: str) -> FileResponse:
    target = FRONTEND_DIR / f"{page_name}.html"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(target)
