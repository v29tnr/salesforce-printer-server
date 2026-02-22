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
from sf_printer_server.printers.drivers import get_printer_driver

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


def _resolve_content(job: PrintJob) -> bytes:
    """
    Resolve job content to raw bytes.

    *_uri    — HTTP GET the URL (with optional BasicAuth / DigestAuth)
    *_base64 — standard base64 decode
    """
    if job.content_type.endswith('_uri'):
        auth = _build_requests_auth(job.auth_config)
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
    """Convert Auth_Config__c JSON to a requests auth tuple / object."""
    if not auth_config:
        return None
    auth_type = auth_config.get('type', '')
    user = auth_config.get('user', '')
    password = auth_config.get('pass', '')
    if auth_type in ('BasicAuth', 'DigestAuth') and user:
        if auth_type == 'DigestAuth':
            from requests.auth import HTTPDigestAuth
            return HTTPDigestAuth(user, password)
        return (user, password)
    return None


