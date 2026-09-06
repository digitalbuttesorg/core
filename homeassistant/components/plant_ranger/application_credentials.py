"""Application credentials platform for Plant Ranger."""

from plantranger import OAUTH2_AUTHORIZE, OAUTH2_TOKEN

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return a PKCE implementation so the built-in client needs no secret."""
    return LocalOAuth2ImplementationWithPkce(
        hass,
        auth_domain,
        credential.client_id,
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
        credential.client_secret,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "developer_dashboard_url": "https://www.plantranger.com/settings/api",
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
    }
