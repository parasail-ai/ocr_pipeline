from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import get_api_router
from app.core.config import get_settings

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


@app.get("/reference", include_in_schema=False, response_class=HTMLResponse)
async def scalar_reference() -> HTMLResponse:
    html = SCALAR_TEMPLATE.format(title=settings.app_name, spec_url=app.openapi_url)
    return HTMLResponse(html)
