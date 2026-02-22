"""
Print job model — maps directly from the SF_Printer_Event__e platform event payload.
No database, no ORM. Pure data class.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PrintJob:
    # Printer connection (from event — server is stateless)
    printer_host: str
    printer_port: int
    printer_type: str           # zpl | raw | cups | ipp

    # Content
    content_type: str           # pdf_uri | pdf_base64 | raw_uri | raw_base64
    content: str                # URI string or base64 payload

    # Optional metadata
    title: str = ''
    source: str = ''
    qty: int = 1                # repeat count for RAW/ZPL; ignored for PDF
    expire_after: int = 0
    options: dict = field(default_factory=dict)     # PDF options JSON blob
    auth_config: dict = field(default_factory=dict) # HTTP auth for *_uri downloads
    correlation_id: str = ''

    @classmethod
    def from_event(cls, event: dict) -> 'PrintJob':
        """Build a PrintJob from a decoded SF_Printer_Event__e payload."""
        def _int(val, default=0):
            try:
                return int(val) if val not in (None, '') else default
            except (TypeError, ValueError):
                return default

        def _json(val):
            if not val:
                return {}
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Could not parse JSON field: {val!r}")
                return {}

        return cls(
            printer_host=event.get('Printer_Host__c', ''),
            printer_port=_int(event.get('Printer_Port__c'), 9100),
            printer_type=(event.get('Printer_Type__c') or 'raw').lower().strip(),
            content_type=(event.get('Content_Type__c') or '').lower().strip(),
            content=event.get('Content__c') or '',
            title=event.get('Job_Title__c') or '',
            source=event.get('Source__c') or '',
            qty=max(1, _int(event.get('Qty__c'), 1)),
            expire_after=_int(event.get('Expire_After__c'), 0),
            options=_json(event.get('Options__c')),
            auth_config=_json(event.get('Auth_Config__c')),
            correlation_id=event.get('Correlation_Id__c') or '',
        )

    @property
    def is_raw(self) -> bool:
        return self.content_type in ('raw_uri', 'raw_base64') or self.printer_type in ('zpl', 'raw')

    @property
    def is_pdf(self) -> bool:
        return self.content_type in ('pdf_uri', 'pdf_base64')

    def __str__(self):
        return (
            f"PrintJob(host={self.printer_host}:{self.printer_port} "
            f"type={self.printer_type} content_type={self.content_type} "
            f"title={self.title!r} qty={self.qty} correlation={self.correlation_id})"
        )