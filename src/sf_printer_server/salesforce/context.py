"""
Shared Salesforce session context.

Populated once at startup after OAuth Client Credentials auth.
Used by the processor to automatically inject Bearer auth when
downloading content from Salesforce URLs (ContentVersion, etc.)
without requiring Auth_Config__c on each event.
"""

_access_token: str = ''
_instance_url: str = ''


def set_sf_credentials(access_token: str, instance_url: str) -> None:
    global _access_token, _instance_url
    _access_token = access_token
    _instance_url = instance_url.rstrip('/')


def get_access_token() -> str:
    return _access_token


def get_instance_url() -> str:
    return _instance_url


def is_salesforce_url(url: str) -> bool:
    """True if the URL belongs to the authenticated Salesforce org."""
    if not _instance_url or not url:
        return False
    return url.startswith(_instance_url) or '.salesforce.com' in url.lower()
