"""Health endpoint."""

from fastapi import APIRouter, Depends

from web.config import WebConfig
from web.dependencies import get_config
from web.schemas import BrandingResponse

router = APIRouter(tags=["health"])


@router.get("/branding", response_model=BrandingResponse)
def get_branding(config: WebConfig = Depends(get_config)) -> BrandingResponse:
    return BrandingResponse(bot_name=config.bot_name, bot_description=config.bot_description)
