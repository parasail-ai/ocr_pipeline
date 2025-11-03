from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import get_api_router
from app.core.config import get_settings
from app.services.auth import AuthService

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Parasail OCR Pipeline built with FastAPI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(get_api_router())

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

SCALAR_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title} API Reference</title>
    <link rel="preconnect" href="https://cdn.jsdelivr.net" />
    <link rel="dns-prefetch" href="https://cdn.jsdelivr.net" />
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
    <style>
      body {{
        margin: 0;
        font-family: "Roboto", sans-serif;
        background-color: #f4f2ff;
      }}
      scalar-api-reference {{
        height: 100vh;
      }}
    </style>
  </head>
  <body>
    <scalar-api-reference
      spec-url="{spec_url}"
      layout="modern"
      hide-download-button="true"
      theme="purple"
    ></scalar-api-reference>
  </body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
        },
    )


@app.get("/staging/{document_id}", response_class=HTMLResponse)
async def staging(request: Request, document_id: str) -> HTMLResponse:
    """Staging page for document processing with real-time status updates"""
    return templates.TemplateResponse(
        "staging.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "document_id": document_id,
        },
    )


@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request) -> HTMLResponse:
    """Documents management page"""
    return templates.TemplateResponse(
        "documents.html",
        {
            "request": request,
            "app_name": settings.app_name,
        },
    )


@app.get("/schemas", response_class=HTMLResponse)
async def schemas_page(
    request: Request,
    session_token: Optional[str] = Cookie(None)
) -> HTMLResponse:
    """Schemas management page"""
    is_admin = AuthService.is_admin(session_token)
    
    return templates.TemplateResponse(
        "schemas.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "is_admin": is_admin,
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Login page"""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "app_name": settings.app_name,
        },
    )


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request) -> HTMLResponse:
    """Signup page for new users"""
    return templates.TemplateResponse(
        "signup.html",
        {
            "request": request,
            "app_name": settings.app_name,
        },
    )


@app.get("/models", response_class=HTMLResponse)
async def models_page(
    request: Request,
    session_token: Optional[str] = Cookie(None)
) -> HTMLResponse:
    """Models management page (admin only)"""
    # Check if user is admin
    if not AuthService.is_admin(session_token):
        return RedirectResponse(url="/login?return=/models", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        "models.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "is_admin": True,
        },
    )


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    session_token: Optional[str] = Cookie(None)
) -> HTMLResponse:
    """Analytics dashboard page (admin only)"""
    # Check if user is admin
    if not AuthService.is_admin(session_token):
        return RedirectResponse(url="/login?return=/analytics", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "is_admin": True,
        },
    )


@app.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    session_token: Optional[str] = Cookie(None)
) -> HTMLResponse:
    """User management page (admin only)"""
    # Check if user is admin
    if not AuthService.is_admin(session_token):
        return RedirectResponse(url="/login?return=/users", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "is_admin": True,
        },
    )


@app.get("/reference", include_in_schema=False, response_class=HTMLResponse)
async def scalar_reference(
    session_token: Optional[str] = Cookie(None)
) -> HTMLResponse:
    if not AuthService.is_admin(session_token):
        return RedirectResponse(url="/login?return=/reference", status_code=status.HTTP_303_SEE_OTHER)

    html = SCALAR_TEMPLATE.format(title=settings.app_name, spec_url=app.openapi_url)
    return HTMLResponse(html)
