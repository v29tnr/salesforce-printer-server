"""
Salesforce callback — updates Print_Job__c status after a print attempt.

Uses the REST API upsert-by-External-ID endpoint:
  PATCH {instance_url}/services/data/v{api_version}/sobjects/Print_Job__c/Correlation_Id__c/{id}

Called once per job after success or failure.
No retry — if the callback fails the job still printed (or failed to print);
the failure is logged but does not affect the print result.
"""
import logging
import datetime
import requests as _requests

from sf_printer_server.salesforce.context import (
    get_access_token,
    get_instance_url,
    refresh_token,
)

logger = logging.getLogger(__name__)

API_VERSION = 'v65.0'

# ── Status constants (match Print_Job__c Status__c picklist) ──────────────────
STATUS_DELIVERED = 'Delivered'
STATUS_ERROR     = 'Error'


def update_print_job(correlation_id: str, success: bool, message: str = '') -> bool:
    """
    Upsert Print_Job__c Status__c and Message_From_Server__c using Correlation_Id__c
    as the External ID key.

    Args:
        correlation_id: The Correlation_Id__c value on the print job record.
        success:        True → Status = Delivered, False → Status = Error.
        message:        Optional detail written to Message_From_Server__c.

    Returns:
        True if the callback succeeded, False otherwise.
    """
    if not correlation_id:
        logger.debug('No correlation_id — skipping Salesforce callback')
        return False

    instance_url = get_instance_url()
    if not instance_url:
        logger.warning('Salesforce instance URL not set — skipping callback')
        return False

    url = (
        f'{instance_url}/services/data/{API_VERSION}'
        f'/sobjects/Print_Job__c/Correlation_Id__c/{correlation_id}'
    )

    payload = {
        'Status__c': STATUS_DELIVERED if success else STATUS_ERROR,
        'Message_From_Server__c': message or ('Printed successfully' if success else 'Print failed'),
    }

    ok = _patch(url, payload)
    if ok:
        logger.info(
            f'Callback OK — Print_Job__c [{correlation_id}] → {payload["Status__c"]}'
        )
    else:
        logger.error(
            f'Callback FAILED — Print_Job__c [{correlation_id}] not updated '
            f'(status: {payload["Status__c"]})'
        )
    return ok


def _patch(url: str, payload: dict) -> bool:
    """PATCH with Bearer auth; retries once on 401 with a refreshed token."""
    token = get_access_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    try:
        resp = _requests.patch(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 401:
            logger.warning('SF callback 401 — refreshing token and retrying')
            if refresh_token():
                headers['Authorization'] = f'Bearer {get_access_token()}'
                resp = _requests.patch(url, json=payload, headers=headers, timeout=15)
        # 200 (updated) and 201 (created / upserted new) are both success
        if resp.status_code in (200, 201, 204):
            return True
        logger.error(
            f'SF callback HTTP {resp.status_code}: {resp.text[:200]}'
        )
        return False
    except Exception as exc:
        logger.error(f'SF callback exception: {exc}')
        return False
