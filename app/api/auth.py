"""Single-tenant Microsoft Entra bearer-token validation."""

from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.api.settings import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


class TokenValidator:
    """Validate single-tenant Entra access tokens against the tenant's cached JWKS."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jwks = PyJWKClient(
            f"https://login.microsoftonline.com/{settings.azure_tenant_id}/discovery/v2.0/keys",
            cache_jwk_set=True,
            lifespan=3600,
        )

    def validate(self, token: str) -> dict[str, Any]:
        """Verify signature, issuer, audience, lifetime, and tenant before returning claims."""
        try:
            signing_key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.token_audiences,
                issuer=self.settings.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "tid"]},
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        if claims.get("tid") != self.settings.azure_tenant_id:
            raise HTTPException(status_code=401, detail="Token tenant is not allowed")
        return claims


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Authorize a user token by API audience and tenant for protected endpoints.

    The current POC does not independently enforce the delegated ``scp`` claim.
    """
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenValidator(settings).validate(credentials.credentials)


def require_search_service(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Authorize only the Search service identity configured for custom-skill calls."""
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = TokenValidator(settings).validate(credentials.credentials)
    if not settings.azure_search_principal_id:
        raise HTTPException(status_code=503, detail="Search skill authentication is not configured")
    if claims.get("oid") != settings.azure_search_principal_id:
        raise HTTPException(status_code=403, detail="Caller is not the configured Search service")
    return claims
