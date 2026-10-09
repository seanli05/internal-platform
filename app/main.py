"""FastAPI app + routes.

YOUR TURN. Two endpoints. Run it with:
    uvicorn app.main:app --reload
then open http://127.0.0.1:8000/docs
"""
import io
from PIL import Image, UnidentifiedImageError

from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models
from app.db import Base, engine, get_db
from app.schemas import PhotoOut

UPLOAD_DIR = Path("uploads")
MAX_BYTES = 10 * 1000 * 1000

# CREATE TABLE IF NOT EXISTS — safe to re-run, but it will NOT alter
# an existing table when you change a column. That limitation is exactly why
# Alembic exists. You get to feel the pain first.
Base.metadata.create_all(bind=engine)

# Create the uploads folder if it isn't there yet. parents=True also creates
# any missing parent folders; exist_ok=True means "fine if it already exists"
# instead of raising FileExistsError on every restart.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="DSS")

# CORS (Cross-Origin Resource Sharing).
# The browser treats scheme + host + port as an "origin". The frontend is
# served from http://localhost:5500 and the API lives on :8000 — different
# ports, so different origins. By default the browser will SEND a cross-origin
# fetch() but refuse to let the page's JavaScript READ the response unless the
# API answers with an Access-Control-Allow-Origin header naming that origin.
# This middleware adds those headers (and answers OPTIONS preflights).
#
# Note: CORS is enforced by the browser, not here. It doesn't stop curl or a
# script from calling the API — it stops *other websites* from using a
# visitor's browser to read your API's responses.
#
# Dev origins only, never "*". localhost and 127.0.0.1 are different origins
# to the browser, so both are listed. In production this list should come from
# per-environment config (e.g. the Next.js app's real domain), not be hardcoded.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["GET", "POST"],
)


@app.post("/photos", response_model=PhotoOut)
def upload_photo(file: UploadFile, db: Session = Depends(get_db)):
    # gates
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="File must be an image")
    
    if (file.size or 0) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB)")

    contents = file.file.read(MAX_BYTES + 1)
    if len(contents) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB)")

    try:
        Image.open(io.BytesIO(contents)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="File is not a valid image")
    
    # Take ONLY the extension off the filename and
    # generate the rest ourselves, so the client cannot influence where
    # the bytes land or clobber an existing file.
    ext = Path(file.filename).suffix.lower()
    safe_name = f"{uuid4().hex}{ext}"

    # Bytes to disk FIRST. If this fails we raise and no row is created,
    # so the database never learns about a photo that does not exist.
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(contents)

    # Then the row. If the insert fails, delete the file we just wrote —
    # a compensating action, since the filesystem cannot join the DB's
    # transaction and be rolled back with it.
    photo = models.Photo(filename=file.filename, path=str(dest))
    try:
        db.add(photo)
        db.commit()
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    # Return the ORM object. response_model=PhotoOut turns it into JSON
    # and drops everything not declared there (including `path`).
    return photo



@app.get("/photos", response_model=list[PhotoOut])
def list_photos(db: Session = Depends(get_db)):
    # Plain `def`, not `async def`: there is no `await` here, and a sync
    # endpoint runs in a worker thread — so the sync SQLAlchemy query cannot
    # block the event loop.
    #
    # No ORDER BY, so the database may return these rows in any order it
    # likes. Fine for now; newest-first + pagination comes later.
    return db.query(models.Photo).all()


# Content-Type is chosen from this allowlist, never guessed from the extension.
# Upload still keeps the client's extension, so a valid image saved as .html
# must not be served as text/html (the browser would render it as a page).
# Anything not listed goes out as a generic download instead.
IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


@app.get("/photos/{photo_id}/file")
def get_photo_file(photo_id: int, db: Session = Depends(get_db)):
    # An endpoint rather than mounting uploads/ as static files: only photos
    # with a DB row are reachable (orphans and deleted photos 404), and when
    # auth arrives the ownership check has one obvious place to live.
    photo = db.get(models.Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    path = Path(photo.path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Photo file missing")

    media_type = IMAGE_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    # nosniff: tells the browser to trust our Content-Type rather than
    # inspecting the bytes and deciding for itself.
    return FileResponse(path, media_type=media_type, headers={"X-Content-Type-Options": "nosniff"})


@app.delete("/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    # `photo_id: int` in the signature + `{photo_id}` in the path is all
    # FastAPI needs: it pulls the segment out of the URL, converts it to int,
    # and answers 422 on its own for something like /photos/abc.
    #
    # db.get() looks up by primary key and returns None when there's no row.
    photo = db.get(models.Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Row FIRST, file second — the mirror image of upload. If the commit
    # fails we raise before touching the disk, so nothing changes. If the
    # unlink fails after the commit, we're left with an orphaned file that
    # nothing points at: harmless, and a cleanup script can sweep it later.
    # The reverse order could leave a row pointing at a missing file, which
    # GET /photos would happily list.
    path = Path(photo.path)
    db.delete(photo)
    db.commit()
    path.unlink(missing_ok=True)

    # 204 No Content: success, and there's nothing left to send back.
    # Returning None means FastAPI sends an empty body.
