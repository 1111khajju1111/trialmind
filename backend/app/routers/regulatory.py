from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.services.groq_client import ask_llm

router = APIRouter(prefix="/regulatory", tags=["regulatory-drafting"])

SYSTEM_PROMPT = (
    "You are a regulatory affairs drafting assistant for pharmaceutical "
    "submissions. Given a summary of source data, draft a professional, "
    "well-structured section suitable for a CTD-format regulatory submission. "
    "Use clear clinical/regulatory language. This is a DRAFT for human "
    "regulatory affairs review, not a final filing — do not fabricate specific "
    "trial numbers or statistics that were not provided in the source summary."
)


@router.post("/draft", response_model=schemas.RegulatoryDraftOut)
def create_draft(req: schemas.RegulatoryDraftRequest, db: Session = Depends(get_db)):
    user_prompt = (
        f"Submission title: {req.title}\n"
        f"Section: {req.section}\n\n"
        f"Source summary:\n{req.source_summary}\n\n"
        f"Draft the '{req.section}' section based on the above."
    )
    draft_text = ask_llm(SYSTEM_PROMPT, user_prompt, max_tokens=1500)

    draft = models.RegulatoryDraft(
        title=req.title,
        section=req.section,
        source_summary=req.source_summary,
        draft_content=draft_text,
        status="pending_review",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/drafts", response_model=list[schemas.RegulatoryDraftOut])
def list_drafts(db: Session = Depends(get_db)):
    return db.query(models.RegulatoryDraft).order_by(
        models.RegulatoryDraft.id.desc()
    ).all()
