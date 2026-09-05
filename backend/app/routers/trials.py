import json
import re
import io
from fastapi import APIRouter, Depends, File, UploadFile, Form
from sqlalchemy.orm import Session
from pypdf import PdfReader
from app.database import get_db
from app import models
from app.services.groq_client import ask_llm
from app.services.rag_service import chunk_text
from app.rbac import require_role

router = APIRouter(prefix="/trials", tags=["trials"], dependencies=[Depends(require_role())])

EXTRACTION_SYSTEM_PROMPT = (
    "You are a precise clinical trial criteria extractor.\n\n"
    "Your ONLY job is to extract eligibility criteria from the given protocol text "
    "and return a valid JSON array. Do NOT include any explanation, markdown, or extra text.\n\n"
    "Return ONLY a JSON array in this exact shape:\n"
    '[{"criterion_id": "<short slug>", '
    '"type": "inclusion" or "exclusion", '
    '"field": "age or biomarker name", '
    '"label": "<human readable label>", '
    '"operator": "between" | "gte" | "lte" | "equals" | null, '
    '"value": number or [min, max] or string or null, '
    '"unit": "<unit or empty string>", '
    '"source_text": "<exact sentence from protocol>", '
    '"verification_required": true or false}]\n\n'
    "Rules:\n"
    "- Output ONLY the JSON array. No ```json, no comments, no intro text.\n"
    "- If a criterion is clearly numeric/categorical, set verification_required: false.\n"
    "- If it is qualitative or ambiguous, set operator/value to null and verification_required: true.\n"
    "- Always include source_text.\n"
    "- You MUST return at least one criterion.\n"
)

REQUIRED_FIELDS = {
    "criterion_id", "type", "field", "label", "operator", "value",
    "unit", "source_text", "verification_required"
}


def _validate_criteria(raw_text: str) -> tuple[list, str | None]:
    if not raw_text or not raw_text.strip():
        return [], "The model returned an empty response."

    # Remove markdown fences
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()

    # Extract the JSON array even if there is text before/after
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return [], f"The model did not return valid JSON ({str(e)})."

    if not isinstance(parsed, list) or len(parsed) == 0:
        return [], "No criteria could be extracted from this protocol text."

    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            return [], f"Criterion #{i+1} is not a valid object."
        
        # Fill missing optional keys with safe defaults
        item.setdefault("unit", "")
        item.setdefault("source_text", "")
        item.setdefault("verification_required", True)
        
        missing_keys = REQUIRED_FIELDS - set(item.keys())
        if missing_keys:
            return [], f"Criterion #{i+1} is missing required fields: {', '.join(missing_keys)}."
        
        if not item.get("field") or not item.get("label"):
            return [], f"Criterion #{i+1} has an empty field or label."
        
        if not item.get("verification_required") and not item.get("operator"):
            return [], f"Criterion #{i+1} claims to be machine-checkable but has no operator."

    return parsed, None

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB -- generous for a protocol PDF, small enough to bound memory use
MAX_NAME_LEN = 200
MAX_CONDITION_LEN = 200
MAX_TEXT_LEN = 200_000  # ~40k words of pasted protocol text is already a lot


@router.post("/upload")
async def upload_protocol(
    name: str = Form(...),
    condition: str = Form(...),
    protocol_text: str = Form(None),
    file: UploadFile = File(None),
    study_id: int = Form(None),
    db: Session = Depends(get_db),
):
    """Accepts either plain text or a PDF file.
    Extracts structured criteria via the LLM and only creates the trial
    if extraction succeeds (same validation as before).

    Priority 2: an optional study_id links the new protocol straight to an
    existing CTMS study at upload time, so it's immediately eligible for
    study/site-scoped patient matching. Omit it to keep the legacy
    standalone-trial flow (linkable to a study later)."""

    name = (name or "").strip()
    condition = (condition or "").strip()
    if not name or len(name) > MAX_NAME_LEN:
        return {"error": f"Trial name must be 1-{MAX_NAME_LEN} characters."}
    if not condition or len(condition) > MAX_CONDITION_LEN:
        return {"error": f"Condition must be 1-{MAX_CONDITION_LEN} characters."}

    study = None
    if study_id is not None:
        study = db.query(models.Study).filter(models.Study.id == study_id).first()
        if not study:
            return {"error": "study_id does not reference an existing study."}
        if db.query(models.Trial).filter(models.Trial.study_id == study_id).first():
            return {"error": "That study already has a linked protocol/trial."}

    text = (protocol_text or "").strip()

    # ---------- PDF handling ----------
    if file is not None and file.filename:
        # Extension check first (cheap, catches the obvious case with a clear
        # message), then a magic-byte check on the actual bytes -- a
        # filename is just client-supplied metadata and easy to spoof, so
        # the content itself is what's actually trusted here.
        if not file.filename.lower().endswith(".pdf"):
            return {"error": "Only .pdf files are accepted for protocol upload."}

        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            return {"error": f"PDF exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."}
        if not content.startswith(b"%PDF-"):
            return {"error": "File does not appear to be a valid PDF (failed content check)."}

        try:
            reader = PdfReader(io.BytesIO(content))
            pages = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pages.append(extracted)
            text = "\n".join(pages).strip()
        except Exception as e:
            return {"error": f"Failed to read PDF: {e}"}

    if not text:
        return {"error": "No protocol text found (empty paste or unreadable PDF)."}
    if len(text) > MAX_TEXT_LEN:
        return {"error": f"Protocol text exceeds the {MAX_TEXT_LEN:,} character limit."}

       # ---------- Existing extraction + validation ----------
    structured, err = None, None

    for attempt in range(2):
        prompt = text if attempt == 0 else (
            text +
            "\n\n(Previous attempt was invalid or incomplete -- ensure the "
            "response is a valid JSON list with every required field present "
            "on every item, and at least one criterion.)"
        )
        try:
            raw = ask_llm(EXTRACTION_SYSTEM_PROMPT, prompt, max_tokens=3000)
        except Exception as e:
            return {"error": f"Criteria extraction failed: {e}"}

        structured, err = _validate_criteria(raw)
        if err is None:
            break

    if err is not None:
        return {
            "error": f"Could not extract usable eligibility criteria after 2 attempts: {err} "
                     f"Please review the protocol text and try again."
        }

    trial = models.Trial(
        name=name,
        condition=condition,
        criteria=text,
        structured_criteria=json.dumps(structured),
        study_id=study.id if study else None,
    )
    db.add(trial)
    db.commit()
    db.refresh(trial)

    # Chunk for RAG
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        db.add(models.ProtocolChunk(
            trial_id=trial.id,
            chunk_index=i,
            content=chunk,
        ))
    db.commit()

    machine_checkable = sum(1 for c in structured if not c.get("verification_required"))
    verification_required = len(structured) - machine_checkable

    return {
        "trial_id": trial.id,
        "name": trial.name,
        "condition": trial.condition,
        "study_id": trial.study_id,
        "extracted_criteria": structured,
        "criteria_count": len(structured),
        "machine_checkable_count": machine_checkable,
        "verification_required_count": verification_required,
        "chunk_count": len(chunks),
    }


@router.get("/")
def list_trials(db: Session = Depends(get_db)):
    trials = db.query(models.Trial).all()
    result = []
    for t in trials:
        criteria = json.loads(t.structured_criteria) if t.structured_criteria else []
        machine_checkable = sum(1 for c in criteria if not c.get("verification_required"))
        study = db.query(models.Study).filter(models.Study.id == t.study_id).first() if t.study_id else None
        result.append({
            "id": t.id,
            "name": t.name,
            "condition": t.condition,
            "study_id": t.study_id,
            "study_code": study.study_code if study else None,
            "structured_criteria": criteria,
            "criteria_count": len(criteria),
            "machine_checkable_count": machine_checkable,
        })
    return result


@router.patch("/{trial_id}/link-study")
def link_trial_to_study(trial_id: int, study_id: int, db: Session = Depends(get_db)):
    """Links an already-uploaded (legacy) trial to a study after the fact --
    covers protocols that were ingested before the study existed. A study
    can only have one linked protocol at a time, same rule as at upload."""
    trial = db.query(models.Trial).filter(models.Trial.id == trial_id).first()
    if not trial:
        return {"error": "Trial not found."}
    if trial.study_id is not None:
        return {"error": "This trial is already linked to a study."}
    study = db.query(models.Study).filter(models.Study.id == study_id).first()
    if not study:
        return {"error": "study_id does not reference an existing study."}
    if db.query(models.Trial).filter(models.Trial.study_id == study_id).first():
        return {"error": "That study already has a linked protocol/trial."}

    trial.study_id = study_id
    db.add(models.AgentAction(
        run_id=f"study:{study_id}", trial_id=trial.id, step_name="trial_linked",
        detail=f"Protocol '{trial.name}' linked to study.",
    ))
    db.commit()
    return {"trial_id": trial.id, "study_id": study_id}


@router.get("/{trial_id}/criteria")
def get_criteria(trial_id: int, db: Session = Depends(get_db)):
    trial = db.query(models.Trial).filter(models.Trial.id == trial_id).first()
    if not trial:
        return {"error": "Trial not found."}
    return {
        "trial_id": trial.id,
        "raw_protocol": trial.criteria,
        "structured_criteria": json.loads(trial.structured_criteria) if trial.structured_criteria else [],
    }