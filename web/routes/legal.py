"""Legal contact endpoint — public, no auth required."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from web.config import WebConfig
from web.dependencies import get_config
from web.schemas import LegalContactResponse

router = APIRouter(prefix="/legal", tags=["legal"])


@router.get("/contact", response_model=LegalContactResponse)
async def get_legal_contact(config: WebConfig = Depends(get_config)) -> LegalContactResponse:
    name = config.legal_name.strip()
    street = config.legal_street.strip()
    zip_city = config.legal_zip_city.strip()
    country_en = config.legal_country_en.strip()
    country_de = config.legal_country_de.strip()
    email = config.legal_email.strip()
    enabled = all([name, street, zip_city, country_en, country_de, email])
    return LegalContactResponse(
        enabled=enabled,
        name=name,
        street=street,
        zip_city=zip_city,
        country_en=country_en,
        country_de=country_de,
        email=email,
    )
