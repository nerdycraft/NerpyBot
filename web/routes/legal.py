"""Legal contact endpoint — public, no auth required."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from web.config import WebConfig
from web.dependencies import get_config
from web.schemas import LegalContactResponse

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/contact", response_model=LegalContactResponse)
async def get_legal_contact(config: WebConfig = Depends(get_config)) -> LegalContactResponse:
    return LegalContactResponse(
        name=config.legal_name,
        street=config.legal_street,
        zip_city=config.legal_zip_city,
        country_en=config.legal_country_en,
        country_de=config.legal_country_de,
        email=config.legal_email,
    )
