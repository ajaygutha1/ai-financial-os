from pydantic import BaseModel, Field

from app.schemas.account import AccountPublic


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangePublicTokenRequest(BaseModel):
    public_token: str = Field(min_length=1)
    # Plaid Link's onSuccess metadata carries this client-side -- cheaper to
    # pass it through than to resolve it server-side via an extra API call.
    institution_name: str | None = None


class ExchangePublicTokenResponse(BaseModel):
    accounts: list[AccountPublic]
