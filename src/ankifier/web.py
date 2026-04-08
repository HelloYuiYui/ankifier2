import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from ankifier.csv_parser import parse_line
from ankifier.mistral_connector import init_client as init_mistral, query_senses
from ankifier.elevenlabs_connector import (
    init_client as init_elevenlabs,
    sanitize_filename,
    generate_audio,
)
from ankifier.anki_connector import (
    check_connection,
    ensure_deck,
    store_media_file,
    add_cloze_note,
)

load_dotenv()

app = FastAPI(title="Ankifier")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", uuid.uuid4().hex))

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ---------------------------------------------------------------------------
# In-memory store keyed by session id.  Single-user tool, so this is fine.
# ---------------------------------------------------------------------------
_store: dict[str, dict] = {}


def _sid(request: Request) -> str:
    """Return (or create) a session id."""
    if "sid" not in request.session:
        request.session["sid"] = uuid.uuid4().hex
    return request.session["sid"]


def _config() -> dict:
    return {
        "deck_name": os.environ.get("ANKI_DECK", "French::Vocabulary"),
        "target_lang": os.environ.get("TARGET_LANG", "French"),
        "audio_dir": os.environ.get("AUDIO_DIR", "audio"),
        "tags": os.environ.get("ANKI_TAGS", "ankifier").split(","),
    }


# ---------------------------------------------------------------------------
# Page 1 – Word input
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def page_input(request: Request):
    return templates.TemplateResponse("input.html", {"request": request})


# ---------------------------------------------------------------------------
# POST – generate senses from AI
# ---------------------------------------------------------------------------
@app.post("/generate")
async def generate(request: Request, words: str = Form(...)):
    sid = _sid(request)
    word_lines = [w.strip() for w in words.splitlines() if w.strip()]
    if not word_lines:
        return RedirectResponse("/", status_code=303)

    config = _config()
    ai_client = init_mistral()

    # Build results: list of dicts with word + senses
    results: list[dict] = []
    for line in word_lines:
        entry = parse_line(line)
        try:
            senses = query_senses(ai_client, entry, config["target_lang"])
            for sense in senses:
                results.append({
                    "word": entry.raw,
                    "sense_number": sense.sense_number,
                    "sense_description": sense.sense_description,
                    "sentence": sense.sentence,
                    "cloze_sentence": sense.cloze_sentence,
                    "hidden_text": sense.hidden_text,
                    "hint": sense.hint,
                    "translation": sense.translation,
                })
        except Exception as e:
            results.append({
                "word": entry.raw,
                "sense_number": 0,
                "sense_description": f"Error: {e}",
                "sentence": "",
                "cloze_sentence": "",
                "hidden_text": "",
                "hint": "",
                "translation": "",
            })

    _store[sid] = {"results": results, "config": config}
    return RedirectResponse("/review", status_code=303)


# ---------------------------------------------------------------------------
# Page 2 – Review senses
# ---------------------------------------------------------------------------
@app.get("/review", response_class=HTMLResponse)
async def page_review(request: Request):
    sid = _sid(request)
    data = _store.get(sid, {})
    results = data.get("results", [])
    return templates.TemplateResponse("review.html", {"request": request, "results": results})


# ---------------------------------------------------------------------------
# POST – add selected senses to Anki
# ---------------------------------------------------------------------------
@app.post("/add-to-anki")
async def add_to_anki(request: Request):
    sid = _sid(request)
    data = _store.get(sid, {})
    results = data.get("results", [])
    config = data.get("config", _config())

    form = await request.form()
    keep_indices = {int(v) for v in form.getlist("keep")}

    kept = [r for i, r in enumerate(results) if i in keep_indices]

    if not kept:
        return RedirectResponse("/review", status_code=303)

    # Ensure audio dir exists
    audio_dir = config["audio_dir"]
    os.makedirs(audio_dir, exist_ok=True)

    # Init clients
    elevenlabs_client = init_elevenlabs()

    # Check Anki
    anki_ok = check_connection()
    if anki_ok:
        ensure_deck(config["deck_name"])

    summary: list[dict] = []

    for row in kept:
        word_safe = sanitize_filename(row["word"])
        filename = f"{word_safe}_{row['sense_number']}.mp3"
        output_path = os.path.join(audio_dir, filename)

        # Generate audio
        audio_status = "ok"
        try:
            generate_audio(elevenlabs_client, row["sentence"], output_path)
        except Exception as e:
            audio_status = f"Audio error: {e}"

        # Create Anki card
        card_status = "ok"
        if anki_ok:
            try:
                store_media_file(filename, output_path)
                add_cloze_note(
                    deck_name=config["deck_name"],
                    cloze_text=row["cloze_sentence"],
                    back_extra=row["translation"],
                    audio_filename=filename,
                    tags=config["tags"],
                )
            except RuntimeError as e:
                if "duplicate" in str(e).lower():
                    card_status = "skipped (duplicate)"
                else:
                    card_status = f"Card error: {e}"
            except Exception as e:
                card_status = f"Card error: {e}"
        else:
            card_status = "Anki not connected"

        summary.append({
            **row,
            "audio_status": audio_status,
            "card_status": card_status,
        })

    # Clean up session store
    _store.pop(sid, None)

    return templates.TemplateResponse("result.html", {"request": request, "summary": summary})


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def run():
    import uvicorn
    uvicorn.run("ankifier.web:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
