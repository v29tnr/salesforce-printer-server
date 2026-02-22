"""
Print job processor — handles all content types from SF_Printer_Event__e.

Content types:
  pdf_uri     — download URL, send to CUPS/IPP as PDF
  pdf_base64  — base64-encoded PDF, send to CUPS/IPP
  raw_uri     — download URL, send raw bytes to TCP socket (ZPL, ESC/P, etc.)
  raw_base64  — base64-encoded raw bytes, send to TCP socket
"""
import base64
import logging
import json
from typing import Optional
import requests
from sf_printer_server.jobs.models import PrintJob
from sf_printer_server.printers.drivers import get_printer_driver, get_printer_info
from sf_printer_server.salesforce.context import is_salesforce_url, get_access_token

# ---------------------------------------------------------------------------
# TODO (next session): Salesforce response events
# ---------------------------------------------------------------------------
# After each job succeeds or fails, publish a SF_Printer_Response__e back to
# Salesforce via REST POST to /services/data/v60.0/sobjects/SF_Printer_Response__e
# Fields: Correlation_Id__c, Status__c (success|failed), Error_Message__c, Printed_At__c
# The auth token is already available from the pubsub client — pass it through.
# A Salesforce Flow subscribes to SF_Printer_Response__e and upserts Print_Job__c
# on Correlation_Id__c (ExternalId) to stamp the final status on the record.
# Also: query_zebra_info / get_printer_info can be exposed via a 'discover' event
# type so Salesforce can request printer config on demand and receive it in a response.
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# Track seen correlation IDs for idempotency (in-memory, resets on restart)
_seen_correlations: set = set()

MAX_IDEMPOTENCY_CACHE = 10_000


def process_event(event: dict) -> bool:
    """
    Entry point — parse a decoded platform event dict and dispatch to the right handler.
    Routes on Type__c: 'print_job' is the only type handled here (printer mgmt is stateless).
    """
    event_type = (event.get('Type__c') or '').strip().lower()

    if event_type == 'print_job':
        return _handle_print_job(event)
    else:
        logger.warning(f"Unrecognised event type: {event_type!r} — ignoring")
        return False


def _handle_print_job(event: dict) -> bool:
    """Parse event into PrintJob and execute it."""
    try:
        job = PrintJob.from_event(event)
    except Exception as e:
        logger.error(f"Failed to parse print job event: {e}", exc_info=True)
        return False

    # Idempotency check
    if job.correlation_id:
        if job.correlation_id in _seen_correlations:
            logger.info(f"Duplicate event — correlation_id already processed: {job.correlation_id}")
            return True
        if len(_seen_correlations) >= MAX_IDEMPOTENCY_CACHE:
            _seen_correlations.clear()
        _seen_correlations.add(job.correlation_id)

    if not job.printer_host:
        logger.error(f"Print job has no Printer_Host__c — cannot route: {job}")
        return False

    if not job.content:
        logger.error(f"Print job has no content: {job}")
        return False

    logger.info(f"Processing: {job}")

    try:
        content_bytes = _resolve_content(job)
    except Exception as e:
        logger.error(f"Failed to resolve content for {job}: {e}", exc_info=True)
        return False

    driver = get_printer_driver(
        host=job.printer_host,
        port=job.printer_port,
        printer_type=job.printer_type,
    )

    try:
        if job.is_raw:
            # For ZPL printers, auto-prepend a ^PW/^LL/^MD setup block if the
            # label doesn't already contain those commands.
            if job.printer_type == 'zpl':
                content_bytes = _apply_zpl_config(job, content_bytes)

            qty = max(1, job.qty)
            for i in range(qty):
                if not driver.print_raw(content_bytes):
                    logger.error(f"Raw print failed on attempt {i + 1}/{qty} for {job}")
                    return False
            logger.info(f"Raw print job complete — {qty} copy/copies sent to {job.printer_host}:{job.printer_port}")
        elif job.is_pdf:
            if not driver.print_pdf(content_bytes, job.options):
                logger.error(f"PDF print failed for {job}")
                return False
            logger.info(f"PDF print job complete — sent to {job.printer_host}:{job.printer_port}")
        else:
            logger.error(f"Unknown content_type {job.content_type!r} for {job}")
            return False
    except Exception as e:
        logger.error(f"Print error for {job}: {e}", exc_info=True)
        return False

    return True


def _apply_zpl_config(job: PrintJob, content_bytes: bytes) -> bytes:
    """
    Optionally prepend a ZPL printer setup block (^XA ^PW ^LL ^MD ^XZ) before
    the label payload.

    Priority:
      1. ZPL_Config__c from the event (explicit, overrides everything)
      2. Cached printer info from a previous SGD query
      3. Fresh SGD query to the printer (result is cached for future jobs)

    Skips prepend if the label already contains ^PW or ^LL — those labels are
    self-contained templates and don't need the setup block.
    """
    # If the label is already self-configuring, leave it alone
    if b'^PW' in content_bytes or b'^LL' in content_bytes:
        return content_bytes

    config = job.zpl_config or get_printer_info(job.printer_host, job.printer_port)
    if not config:
        return content_bytes

    lines = ['^XA']
    if 'width_dots' in config:
        lines.append(f'^PW{int(config["width_dots"])}')
    if 'height_dots' in config:
        lines.append(f'^LL{int(config["height_dots"])}')
    elif 'width_dots' in config and 'dpi' in config:
        # Derive mm→dots from explicit zpl_config if height_dots not set but dimensions were
        pass
    if 'darkness' in config:
        lines.append(f'^MD{int(config["darkness"])}')
    if config.get('prefix'):
        lines.append(str(config['prefix']))
    lines.append('^XZ')

    prefix = ('\r\n'.join(lines) + '\r\n').encode('ascii')
    logger.debug(f"Prepending ZPL setup block ({len(prefix)} bytes) for {job.printer_host}:{job.printer_port}")
    return prefix + content_bytes


def _resolve_content(job: PrintJob) -> bytes:
    """
    Resolve job content to raw bytes.

    *_uri    — HTTP GET the URL (with optional BasicAuth / DigestAuth)
    *_base64 — standard base64 decode
    """
    if job.content_type.endswith('_uri'):
        # Auto-inject server Bearer token for Salesforce URLs unless the
        # event explicitly provides its own Auth_Config__c.
        if job.auth_config:
            auth = _build_requests_auth(job.auth_config)
        elif is_salesforce_url(job.content):
            auth = _BearerAuth(get_access_token())
            logger.debug('Auto-injecting server Bearer token for Salesforce URL')
        else:
            auth = None
        logger.info(f"Downloading content from URI: {job.content[:80]}...")
        resp = requests.get(job.content, auth=auth, timeout=60)
        resp.raise_for_status()
        return resp.content

    elif job.content_type.endswith('_base64'):
        # Strip whitespace / data-URI prefix if present
        raw = job.content.strip()
        if ',' in raw and raw.startswith('data:'):
            raw = raw.split(',', 1)[1]
        # Re-pad in case Apex/Salesforce stripped trailing '=' characters
        raw += '=' * (-len(raw) % 4)
        return base64.b64decode(raw)

    else:
        raise ValueError(f"Unsupported content_type: {job.content_type!r}")


def _build_requests_auth(auth_config: dict):
    """
    Convert Auth_Config__c JSON to a requests auth object or header dict.

    Supported types:
      BasicAuth   — {"type":"BasicAuth","user":"u","pass":"p"}
      DigestAuth  — {"type":"DigestAuth","user":"u","pass":"p"}
      BearerToken — {"type":"BearerToken","token":"<sf_session_or_access_token>"}
                    Pass UserInfo.getSessionId() from Apex for Salesforce file downloads.
    """
    if not auth_config:
        return None
    auth_type = auth_config.get('type', '')
    user = auth_config.get('user', '')
    password = auth_config.get('pass', '')

    if auth_type == 'BearerToken':
        token = auth_config.get('token', '')
        if token:
            # Return a callable that requests will use as an auth hook
            return _BearerAuth(token)
        return None

    if auth_type in ('BasicAuth', 'DigestAuth') and user:
        if auth_type == 'DigestAuth':
            from requests.auth import HTTPDigestAuth
            return HTTPDigestAuth(user, password)
        return (user, password)

    return None


class _BearerAuth(requests.auth.AuthBase):
    """Attaches a Bearer token to requests."""
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r):
        r.headers['Authorization'] = f'Bearer {self.token}'
        return r


