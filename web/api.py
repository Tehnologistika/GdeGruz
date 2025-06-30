from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import get_last_point, init

app = FastAPI()


@app.on_event("startup")
async def startup() -> None:
    await init()

templates = Jinja2Templates(directory="templates")


@app.get("/healthz")
async def healthz():
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.get("/api/last/{user_id}")
async def api_last(user_id: int):
    """Return the last saved location for the given user."""
    point = await get_last_point(user_id)
    if not point:
        raise HTTPException(status_code=404, detail="Point not found")
    return {
        "lat": point["lat"],
        "lon": point["lon"],
        "ts": point["ts"].isoformat(),
    }


@app.get("/map/{user_id}", response_class=HTMLResponse)
async def map_view(request: Request, user_id: int):
    """Render the map template which auto refreshes the marker."""
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "user_id": user_id,
        },
    )
