"""
Shared Salesforce session context.

Populated once at startup after OAuth Client Credentials auth.
Used by the processor to automatically inject Bearer auth when
downloading content from Salesforce URLs (ContentVersion, etc.)
without requiring Auth_Config__c on each event.
"""
import logging
import requests as _requests

logger = logging.getLogger(__name__)

_access_token: str = ''
_instance_url: str = ''
_client_id: str = ''
_client_secret: str = ''


def set_sf_credentials(access_token: str, instance_url: str,
                       client_id: str = '', client_secret: str = '') -> None:
    global _access_token, _instance_url, _client_id, _client_secret
    _access_token = access_token
    _instance_url = instance_url.rstrip('/')
    if client_id:
        _client_id = client_id
    if client_secret:
        _client_secret = client_secret


def get_access_token() -> str:
    return _access_token


def get_instance_url() -> str:
    return _instance_url


def is_salesforce_url(url: str) -> bool:
    """True if the URL belongs to the authenticated Salesforce org."""
    if not _instance_url or not url:
        return False
    return url.startswith(_instance_url) or '.salesforce.com' in url.lower()


def refresh_token() -> bool:
    """
    Re-run client credentials OAuth and update the stored token.
    Called automatically by the processor on 401 errors.
    Returns True on success.
    """
    global _access_token
    if not (_instance_url and _client_id and _client_secret):
        logger.warning('Cannot refresh SF token — client_id/secret not stored in context')
        return False
    try:
        resp = _requests.post(
            f'{_instance_url}/services/oauth2/token',
            data={
                'grant_type': 'client_credentials',
                'client_id': _client_id,
                'client_secret': _client_secret,
            },
            timeout=15,
        )
        resp.raise_for_status()
        new_token = resp.json()['access_token']
        _access_token = new_token
        logger.info('SF access token refreshed successfully')
        return True
    except Exception as e:
        logger.error(f'SF token refresh failed: {e}')
        return False
