import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
import jinja2

from ankifier.csv_parser import parse_line
from ankifier import local_connector, mistral_connector
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
    add_basic_note,
)

load_dotenv()

app = FastAPI(title="Ankifier")
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", uuid.uuid4().hex))

# Initialize Jinja2 templates manually
TEMPLATES_DIR = (Path(__file__).parent / "templates").resolve()
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def render_template(template_name: str, **context):
    """Render a template and return the HTML string."""
    template = jinja_env.get_template(template_name)
    return template.render(**context)

# ---------------------------------------------------------------------------
# In-memory store keyed by session id.  Single-user tool, so this is fine.
# ---------------------------------------------------------------------------
_store: dict[str, dict] = {}


def _sid(request: Request) -> str:
    """Return (or create) a session id."""
    if "sid" not in request.session:
        request.session["sid"] = uuid.uuid4().hex
    return request.session["sid"]


def _init_llm():
    """Return (client, query_senses) for the backend named by LLM_BACKEND.

    "local" talks to the MLX server (see llm_server/server.py); anything else
    uses the hosted Mistral API.
    """
    # if os.environ.get("LLM_BACKEND", "mistral").lower() == "local":
    #     return local_connector.init_client(), local_connector.query_senses
    return mistral_connector.init_client(), mistral_connector.query_senses


def _config() -> dict:
    return {
        "deck_name": os.environ.get("ANKI_DECK", "French::Vocabulary"),
        # "As is" cards are hand-written grammar material, not generated
        # vocabulary, so they get their own deck.
        "as_is_deck_name": os.environ.get("ANKI_ASIS_DECK", "French::Grammar"),
        "target_lang": os.environ.get("TARGET_LANG", "French"),
        "audio_dir": os.environ.get("AUDIO_DIR", "audio"),
        "tags": os.environ.get("ANKI_TAGS", "ankifier").split(","),
    }


# ---------------------------------------------------------------------------
# Page 1 – Word input
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def page_input(request: Request):
    html = render_template("input.html", request=request)
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# POST – generate senses from AI
# ---------------------------------------------------------------------------
def _parse_rows(rows: str | None, words: str | None) -> list[tuple[str, bool]]:
    """Return [(text, as_is), ...] from the submitted form.

    The input page posts `rows` as JSON so each line can carry its own "as is"
    flag; `words` is the older newline-separated field, kept so a plain POST
    (or an older cached page) still works.
    """
    if rows:
        try:
            parsed = json.loads(rows)
        except (ValueError, TypeError):
            parsed = []
        out = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if text:
                out.append((text, bool(item.get("as_is"))))
        if out:
            return out

    if words:
        return [(w.strip(), False) for w in words.splitlines() if w.strip()]

    return []


@app.post("/generate")
async def generate(
    request: Request,
    rows: str = Form(None),
    words: str = Form(None),
):
    sid = _sid(request)
    word_lines = _parse_rows(rows, words)
    if not word_lines:
        return RedirectResponse("/", status_code=303)

    config = _config()
    ai_client, query = _init_llm()

    # Build results: list of dicts with word + senses
    results: list[dict] = []
    for line, as_is in word_lines:
        entry = parse_line(line, as_is=as_is)
        # "As is" skips sense generation entirely: the text is already the
        # card, so the model is only asked for its translation.
        run = mistral_connector.translate_as_is if as_is else query
        try:
            senses = run(ai_client, entry, config["target_lang"])
            for sense in senses:
                results.append({
                    "word": entry.raw,
                    "as_is": as_is,
                    "sense_number": sense.sense_number,
                    "sense_description": sense.sense_description,
                    "sentence": sense.sentence,
                    "cloze_sentence": sense.cloze_sentence,
                    "hidden_text": sense.hidden_text,
                    "hint": sense.hint,
                    "translation": sense.translation,
                    "level": sense.level.value if sense.level else None,
                })
        except Exception as e:
            results.append({
                "word": entry.raw,
                "as_is": as_is,
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
    html = render_template("review.html", request=request, results=results)
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# POST – add selected senses to Anki
# ---------------------------------------------------------------------------
def _deck_for(row: dict, config: dict) -> str:
    """Return the deck a result row belongs in."""
    if row.get("as_is"):
        return config.get("as_is_deck_name", _config()["as_is_deck_name"])
    return config["deck_name"]


def _tags_for(row: dict, config: dict) -> list[str]:
    """Return the tags for a result row, marking as-is cards so they can be
    found (and re-styled) separately from generated vocabulary."""
    tags = list(config["tags"])
    if row.get("as_is") and "as-is" not in tags:
        tags.append("as-is")
    return tags


@app.post("/add-to-anki")
async def add_to_anki(request: Request):
    sid = _sid(request)
    data = _store.get(sid, {})
    results = data.get("results", [])
    config = data.get("config", _config())

    form = await request.form()
    keep_indices = set()
    for v in form.getlist("keep"):
        try:
            keep_indices.add(int(v))
        except (ValueError, TypeError):
            # Skip invalid indices
            pass
        

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
        # Only create the decks this batch actually needs.
        for deck in {_deck_for(row, config) for row in kept}:
            ensure_deck(deck)

    summary: list[dict] = []

    for row in kept:
        # An as-is "word" is a whole sentence, so cap the filename stem.
        word_safe = sanitize_filename(row["word"])[:60]
        filename = f"{word_safe}_{row['sense_number']}.mp3"
        output_path = os.path.join(audio_dir, filename)

        # Generate audio
        audio_status = "ok"
        try:
            generate_audio(elevenlabs_client, row["sentence"], output_path)
        except Exception as e:
            audio_status = f"Audio error: {e}"

        # Create Anki card
        audio_ok = audio_status == "ok"
        card_status = "ok"
        if anki_ok:
            try:
                if audio_ok:
                    store_media_file(filename, output_path)
                deck_name = _deck_for(row, config)
                if "{{c" in row["cloze_sentence"]:
                    add_cloze_note(
                        deck_name=deck_name,
                        cloze_text=row["cloze_sentence"],
                        back_extra=row["translation"],
                        audio_filename=filename if audio_ok else None,
                        tags=_tags_for(row, config),
                    )
                else:
                    # No cloze deletion to make -- an as-is text with no
                    # -...- markers. Anki rejects an empty Cloze note, so
                    # this becomes a plain front/back card.
                    add_basic_note(
                        deck_name=deck_name,
                        front=row["sentence"],
                        back=row["translation"],
                        audio_filename=filename if audio_ok else None,
                        tags=_tags_for(row, config),
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

    # Store summary and config for potential retry
    _store[sid] = {"summary": summary, "config": config}

    html = render_template("result.html", request=request, summary=summary)
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def run():
    import uvicorn
    uvicorn.run("ankifier.web:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
