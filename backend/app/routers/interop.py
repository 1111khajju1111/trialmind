"""
Priority 7 -- FHIR + CDISC Demonstrator (routes).

GET /interop/fhir/{resource}   FHIR R4 Bundle for one resource type, built
                                from live data (optionally ?study_id=).
GET /interop/mapping            Human-readable internal-field -> FHIR/SDTM
                                mapping documentation (plan requirement).
GET /export/sdtm/{domain}       SDTM-style CSV export for one domain
                                (DM, AE), optionally ?study_id=.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import interop as interop_svc

router = APIRouter(tags=["interoperability"])


@router.get("/interop/fhir/{resource}")
def get_fhir_bundle(resource: str, study_id: int | None = None, db: Session = Depends(get_db)):
    if resource not in interop_svc.FHIR_RESOURCE_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown FHIR resource '{resource}'. Supported: {', '.join(interop_svc.FHIR_RESOURCE_TYPES)}.",
        )
    return interop_svc.build_fhir_bundle(db, resource, study_id)


@router.get("/interop/fhir")
def list_fhir_resources():
    """Lets the frontend Interoperability page render buttons without
    hard-coding the resource list twice."""
    return {"resource_types": interop_svc.FHIR_RESOURCE_TYPES}


@router.get("/interop/mapping", response_class=PlainTextResponse)
def get_mapping_doc():
    return interop_svc.FIELD_MAPPING_DOC


@router.get("/export/sdtm/{domain}")
def export_sdtm(domain: str, study_id: int | None = None, db: Session = Depends(get_db)):
    domain = domain.upper()
    if domain not in interop_svc.SDTM_DOMAINS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown SDTM domain '{domain}'. Supported: {', '.join(interop_svc.SDTM_DOMAINS)}.",
        )
    if domain == "DM":
        csv_text = interop_svc.sdtm_dm_csv(db, study_id)
    else:
        csv_text = interop_svc.sdtm_ae_csv(db, study_id)

    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{domain}.csv"'},
    )


@router.get("/export/sdtm")
def list_sdtm_domains():
    return {"domains": interop_svc.SDTM_DOMAINS}
