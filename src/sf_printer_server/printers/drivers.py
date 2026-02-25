"""
Printer driver implementations.

Drivers are instantiated per-job from the event fields (host, port, type).
No static config required — the server is stateless with respect to printers.

Types:
  zpl  — Zebra / raw TCP socket (port 9100 default)
  raw  — Generic raw TCP socket
  cups — CUPS queue via lp (printer must be registered in local CUPS daemon)
  ipp  — Direct IPP over HTTP — no CUPS daemon or printer registration needed
"""

import re
import socket
import struct
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

import requests as _requests

logger = logging.getLogger(__name__)


class PrinterError(Exception):
    """Raised by driver methods when a print job fails with a known, describable cause."""
    pass


# Human-readable names for IPP status codes (RFC 8011 §6.4)
_IPP_STATUS = {
    0x0000: 'successful-ok',
    0x0001: 'successful-ok-ignored-or-substituted-attributes',
    0x0002: 'successful-ok-conflicting-attributes',
    0x0400: 'client-error-bad-request',
    0x0401: 'client-error-forbidden',
    0x0402: 'client-error-not-authenticated',
    0x0403: 'client-error-not-authorized',
    0x0404: 'client-error-not-possible',
    0x0405: 'client-error-timeout',
    0x0406: 'client-error-not-found',
    0x0407: 'client-error-gone',
    0x0408: 'client-error-request-entity-too-large',
    0x0409: 'client-error-request-value-too-long',
    0x040a: 'client-error-document-format-not-supported',
    0x040b: 'client-error-attributes-or-values-not-supported',
    0x040c: 'client-error-uri-scheme-not-supported',
    0x040d: 'client-error-charset-not-supported',
    0x040e: 'client-error-conflicting-attributes',
    0x040f: 'client-error-compression-not-supported',
    0x0410: 'client-error-compression-error',
    0x0411: 'client-error-document-format-error',
    0x0412: 'client-error-document-access-error',
    0x0500: 'server-error-internal-error',
    0x0501: 'server-error-operation-not-supported',
    0x0502: 'server-error-service-unavailable',
    0x0503: 'server-error-version-not-supported',
    0x0504: 'server-error-device-error',
    0x0505: 'server-error-temporary-error',
    0x0506: 'server-error-not-accepting-jobs',
    0x0507: 'server-error-busy',
    0x0508: 'server-error-job-canceled',
    0x0509: 'server-error-multiple-document-jobs-not-supported',
}

SOCKET_TIMEOUT = 10
SGD_QUERY_TIMEOUT = 3.0

# ---------------------------------------------------------------------------
# Printer info cache — keyed by "host:port"
# Populated by SGD auto-discovery on first ZPL job to each printer.
# ---------------------------------------------------------------------------

_printer_info_cache: dict = {}

# Cache of supported document formats per "host:port"
_ipp_format_cache: dict = {}


def query_zebra_info(host: str, port: int, timeout: float = SGD_QUERY_TIMEOUT) -> dict:
    """
    Query a Zebra printer via SGD (Set/Get/Do) over TCP.
    Sends a batch query for DPI, print width and darkness.
    Returns a dict with zero or more of: dpi, width_dots, darkness.
    Returns empty dict on any failure (printer offline, not a Zebra, etc.).
    """
    # Batch SGD query — values returned in the same order
    query = b'! U1 getvar "device.dpi" "ezpl.print_width" "print.tone"\r\n'
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(query)
            raw = b''
            while True:
                try:
                    chunk = sock.recv(256)
                    if not chunk:
                        break
                    raw += chunk
                    if len(raw) >= 64 or b'"' in raw[10:]:
                        break
                except socket.timeout:
                    break
        response = raw.decode('ascii', errors='ignore').strip()
        info = _parse_sgd_response(response)
        if info:
            logger.info(f"SGD query {host}:{port} → {info}")
        return info
    except Exception as e:
        logger.debug(f"SGD query failed for {host}:{port}: {e}")
        return {}


def _parse_sgd_response(response: str) -> dict:
    """Parse a Zebra SGD response — quoted values in order: dpi, width_dots, darkness."""
    values = re.findall(r'"([^"]*)"', response)
    result = {}
    if len(values) >= 1:
        dpi_str = values[0].lower().replace('dpi', '').strip()
        try:
            result['dpi'] = int(dpi_str)
        except ValueError:
            pass
    if len(values) >= 2:
        try:
            result['width_dots'] = int(values[1])
        except ValueError:
            pass
    if len(values) >= 3:
        try:
            result['darkness'] = int(values[2])
        except ValueError:
            pass
    return result


def get_printer_info(host: str, port: int) -> dict:
    """
    Return cached printer info for host:port, or query the printer and cache the result.
    Returns empty dict if the printer cannot be queried (non-Zebra, offline, etc.).
    """
    key = f"{host}:{port}"
    if key not in _printer_info_cache:
        info = query_zebra_info(host, port)
        if info:
            logger.info(f"Printer info cached for {key}: {info}")
            _printer_info_cache[key] = info
        else:
            return {}
    return _printer_info_cache.get(key, {})


def clear_printer_cache(host: Optional[str] = None, port: Optional[int] = None) -> None:
    """Evict one entry or the entire cache (e.g. after a printer config change)."""
    if host and port:
        key = f"{host}:{port}"
        _printer_info_cache.pop(key, None)
        _ipp_format_cache.pop(key, None)
    else:
        _printer_info_cache.clear()
        _ipp_format_cache.clear()


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class PrinterDriver:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def print_raw(self, content: bytes) -> bool:
        raise NotImplementedError

    def print_pdf(self, content: bytes, options: dict) -> bool:
        raise NotImplementedError

    def test_connection(self) -> bool:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Raw TCP (ZPL, ESC/P, plain raw)
# ---------------------------------------------------------------------------

class RawTCPDriver(PrinterDriver):
    """Sends raw bytes over a TCP socket. Used for ZPL and generic raw jobs."""

    def print_raw(self, content: bytes) -> bool:
        try:
            logger.info(f"TCP → {self.host}:{self.port} ({len(content)} bytes)")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(SOCKET_TIMEOUT)
                sock.connect((self.host, self.port))
                if isinstance(content, str):
                    content = content.encode('utf-8')
                sock.sendall(content)
            logger.info(f"✓ Sent to {self.host}:{self.port}")
            return True
        except socket.timeout:
            raise PrinterError(
                f"Connection timed out — printer {self.host}:{self.port} did not respond "
                f"within {SOCKET_TIMEOUT}s. Check that the printer is online and reachable."
            )
        except socket.error as e:
            raise PrinterError(
                f"Cannot connect to printer {self.host}:{self.port}: {e}"
            )

    def print_pdf(self, content: bytes, options: dict) -> bool:
        raise PrinterError(
            f"Printer {self.host}:{self.port} is configured as type 'raw' which does not "
            f"support PDF. Change the printer Type to 'ipp' or 'cups' for PDF printing."
        )

    def test_connection(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((self.host, self.port))
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# CUPS (PDF via lp with options)
# ---------------------------------------------------------------------------

class CUPSDriver(PrinterDriver):
    """
    Sends PDF jobs to a CUPS printer using the `lp` command.
    For `cups` type: uses ipp://host:port/ipp/print as the destination.
    For `ipp`  type: same — CUPS resolves the IPP URI directly.
    """

    def __init__(self, host: str, port: int):
        super().__init__(host, port)
        # Construct IPP URI — CUPS accepts this as a -d destination
        self.ipp_uri = f"ipp://{host}:{port}/ipp/print"

    def print_raw(self, content: bytes) -> bool:
        return self._lp(content, extra_opts=['-o', 'raw'])

    def print_pdf(self, content: bytes, options: dict) -> bool:
        return self._lp(content, extra_opts=_build_lp_options(options))

    def test_connection(self) -> bool:
        try:
            result = subprocess.run(
                ['lpstat', '-v'],
                capture_output=True, text=True, timeout=5
            )
            return self.host in result.stdout
        except Exception:
            return False

    def _lp(self, content: bytes, extra_opts: list = None) -> bool:
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
                tmp = f.name
                f.write(content)

            cmd = ['lp', '-d', self.ipp_uri] + (extra_opts or []) + [tmp]
            logger.info(f"CUPS: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info(f"✓ CUPS job accepted: {result.stdout.strip()}")
                return True
            else:
                detail = (result.stderr or result.stdout).strip()
                raise PrinterError(f"CUPS error sending to {self.ipp_uri}: {detail}")
        except subprocess.TimeoutExpired:
            raise PrinterError(f"CUPS lp timed out after 60s for {self.ipp_uri}")
        except PrinterError:
            raise
        except Exception as e:
            raise PrinterError(f"CUPS print error for {self.ipp_uri}: {e}") from e
        finally:
            if tmp:
                Path(tmp).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# IPP (direct IPP/1.1 over HTTP — no CUPS daemon or printer registration)
# ---------------------------------------------------------------------------

class IPPDriver(PrinterDriver):
    """
    Sends print jobs directly via IPP/1.1 over HTTP.
    No local CUPS daemon or printer queue registration required.
    The printer only needs to be reachable on the network at host:port.
    """

    def __init__(self, host: str, port: int):
        super().__init__(host, port)
        self.printer_uri = f"ipp://{host}:{port}/ipp/print"
        self.http_url    = f"http://{host}:{port}/ipp/print"

    def print_raw(self, content: bytes) -> bool:
        return self._ipp_send(content, document_format='application/octet-stream')

    def print_pdf(self, content: bytes, options: dict) -> bool:
        copies = 1
        if options:
            try:
                copies = max(1, int(options.get('copies', 1)))
            except (TypeError, ValueError):
                pass
        fmt = self._pick_pdf_format()
        return self._ipp_send(content, document_format=fmt, copies=copies)

    def test_connection(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((self.host, self.port))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Format discovery
    # ------------------------------------------------------------------

    def _pick_pdf_format(self) -> str:
        """
        Return the best document-format to use for PDF jobs.
        Queries the printer once and caches the result.
        Preference order: application/pdf → application/octet-stream.
        """
        key = f"{self.host}:{self.port}"
        if key not in _ipp_format_cache:
            _ipp_format_cache[key] = self._query_supported_formats()

        supported = _ipp_format_cache[key]
        if not supported:
            # Query failed — try pdf and let the printer reject if needed
            return 'application/pdf'

        for preferred in ('application/pdf', 'application/octet-stream'):
            if preferred in supported:
                logger.debug(f"IPP format selected for {key}: {preferred}")
                return preferred

        # Last resort — use whatever the printer listed first
        fallback = supported[0]
        logger.warning(
            f"IPP: neither application/pdf nor application/octet-stream supported "
            f"by {key}; using {fallback}"
        )
        return fallback

    def _query_supported_formats(self) -> list:
        """
        Send a Get-Printer-Attributes IPP request and return the list of
        values from document-format-supported.  Returns [] on any failure.
        """
        a = self._attr
        ipp  = struct.pack('>BBH', 1, 1, 0x000B)   # version 1.1, op=Get-Printer-Attributes
        ipp += struct.pack('>I', 2)                 # request-id
        ipp += b'\x01'                              # operation-attributes-tag
        ipp += a(0x47, 'attributes-charset',          'utf-8')
        ipp += a(0x48, 'attributes-natural-language', 'en')
        ipp += a(0x45, 'printer-uri',                 self.printer_uri)
        ipp += a(0x44, 'requested-attributes',        'document-format-supported')
        ipp += b'\x03'                              # end-of-attributes

        try:
            resp = _requests.post(
                self.http_url,
                data=ipp,
                headers={'Content-Type': 'application/ipp'},
                timeout=10,
            )
            if resp.status_code != 200 or len(resp.content) < 8:
                return []
            formats = self._parse_keyword_list(resp.content, 'document-format-supported')
            logger.info(f"IPP supported formats for {self.host}:{self.port}: {formats}")
            return formats
        except Exception as e:
            logger.debug(f"IPP format query failed for {self.host}:{self.port}: {e}")
            return []

    @staticmethod
    def _parse_keyword_list(data: bytes, attr_name: str) -> list:
        """
        Minimal IPP response parser — extracts all string values for a named attribute.
        Handles multi-valued attributes (subsequent values have name-length == 0).
        """
        values = []
        i = 8  # skip version(2) + status(2) + request-id(4)
        target = attr_name.encode('utf-8')
        in_target = False

        while i < len(data):
            tag = data[i]; i += 1

            # Group delimiters
            if tag in (0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06):
                in_target = False
                if tag == 0x03:   # end-of-attributes
                    break
                continue

            if i + 2 > len(data):
                break
            name_len = struct.unpack('>H', data[i:i+2])[0]; i += 2

            name = b''
            if name_len > 0:
                if i + name_len > len(data):
                    break
                name = data[i:i+name_len]; i += name_len
                in_target = (name == target)

            if i + 2 > len(data):
                break
            val_len = struct.unpack('>H', data[i:i+2])[0]; i += 2

            if i + val_len > len(data):
                break
            val = data[i:i+val_len]; i += val_len

            if in_target and val_len > 0:
                values.append(val.decode('utf-8', errors='replace'))

        return values

    # ------------------------------------------------------------------
    # IPP encoding / send
    # ------------------------------------------------------------------

    @staticmethod
    def _attr(tag: int, name: str, value) -> bytes:
        """Encode a single IPP attribute (tag + name + value)."""
        name_b = name.encode('utf-8')
        if isinstance(value, str):
            value_b = value.encode('utf-8')
        elif isinstance(value, int):
            value_b = struct.pack('>i', value)   # IPP integer = signed 4-byte BE
        else:
            value_b = bytes(value)
        return (
            struct.pack('>B', tag)
            + struct.pack('>H', len(name_b)) + name_b
            + struct.pack('>H', len(value_b)) + value_b
        )

    def _ipp_send(
        self,
        content: bytes,
        document_format: str = 'application/pdf',
        copies: int = 1,
        job_name: str = 'Print Job',
    ) -> bool:
        a = self._attr

        # ── IPP/1.1 Print-Job request ──────────────────────────────────
        ipp  = struct.pack('>BBH', 1, 1, 0x0002)   # version 1.1, op=Print-Job
        ipp += struct.pack('>I', 1)                 # request-id

        # Operation-attributes group (tag 0x01)
        ipp += b'\x01'
        ipp += a(0x47, 'attributes-charset',          'utf-8')
        ipp += a(0x48, 'attributes-natural-language', 'en')
        ipp += a(0x45, 'printer-uri',                 self.printer_uri)
        ipp += a(0x42, 'requesting-user-name',        'sf-printer-server')
        ipp += a(0x42, 'job-name',                    job_name)
        ipp += a(0x49, 'document-format',             document_format)

        # Job-attributes group (tag 0x02) — only if copies > 1
        if copies > 1:
            ipp += b'\x02'
            ipp += a(0x21, 'copies', copies)

        ipp += b'\x03'    # end-of-attributes
        ipp += content    # document data

        try:
            logger.info(
                f"IPP → {self.http_url} ({len(content)} bytes, "
                f"format={document_format}, copies={copies})"
            )
            resp = _requests.post(
                self.http_url,
                data=ipp,
                headers={'Content-Type': 'application/ipp'},
                timeout=60,
            )

            if resp.status_code != 200 or len(resp.content) < 8:
                raise PrinterError(
                    f"IPP: printer {self.host}:{self.port} returned HTTP {resp.status_code}. "
                    f"Check that the printer's IPP endpoint is enabled and accessible."
                )

            status = struct.unpack('>H', resp.content[2:4])[0]
            if status in (0x0000, 0x0001):
                extra = ' (some attributes were substituted)' if status == 0x0001 else ''
                logger.info(f"✓ IPP job accepted by {self.host}:{self.port}{extra}")
                return True

            status_name = _IPP_STATUS.get(status, f'unknown-status-0x{status:04x}')
            raise PrinterError(
                f"IPP printer {self.host}:{self.port} rejected the job: "
                f"{status_name} (0x{status:04x})"
            )

        except _requests.Timeout:
            raise PrinterError(
                f"IPP request timed out — printer {self.host}:{self.port} did not respond "
                f"within 60s. Check that the printer is online and the port is correct."
            )
        except PrinterError:
            raise
        except Exception as e:
            raise PrinterError(f"IPP send error to {self.host}:{self.port}: {e}") from e


# ---------------------------------------------------------------------------
# Options mapping — Options__c JSON → lp -o flags
# ---------------------------------------------------------------------------

def _build_lp_options(options: dict) -> list:
    """
    Convert Options__c JSON dict to `lp -o key=value` argument list.
    Ignores unknown keys silently.
    """
    opts = []
    if not options:
        return opts

    _copies = options.get('copies')
    if _copies:
        opts += ['-n', str(int(_copies))]

    _duplex = options.get('duplex', '').lower()
    _duplex_map = {
        'long-edge': 'two-sided-long-edge',
        'short-edge': 'two-sided-short-edge',
        'one-sided': 'one-sided',
    }
    if _duplex in _duplex_map:
        opts += ['-o', f'sides={_duplex_map[_duplex]}']

    if options.get('paper'):
        opts += ['-o', f'media={options["paper"]}']

    if options.get('dpi'):
        opts += ['-o', f'Resolution={options["dpi"]}']

    if options.get('bin'):
        opts += ['-o', f'InputSlot={options["bin"]}']

    if options.get('collate') is True:
        opts += ['-o', 'Collate=True']

    if options.get('color') is False:
        opts += ['-o', 'ColorModel=Gray']

    if options.get('fit_to_page') is True:
        opts += ['-o', 'fit-to-page']

    if options.get('pages'):
        opts += ['-o', f'page-ranges={options["pages"]}']

    if options.get('nup'):
        opts += ['-o', f'number-up={int(options["nup"])}']

    _rotate = options.get('rotate')
    if _rotate is not None:
        opts += ['-o', f'landscape'] if int(_rotate) in (90, 270) else []

    return opts


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_printer_driver(host: str, port: int, printer_type: str) -> PrinterDriver:
    """
    Return the correct driver for the given printer type.

    Args:
        host: IP or hostname from Printer_Host__c
        port: TCP port from Printer_Port__c
        printer_type: zpl | raw | cups | ipp
    """
    t = (printer_type or 'raw').lower().strip()
    if t in ('zpl', 'raw'):
        return RawTCPDriver(host, port)
    elif t == 'cups':
        return CUPSDriver(host, port)
    elif t == 'ipp':
        return IPPDriver(host, port)
    else:
        logger.warning(f"Unknown printer_type '{t}' — falling back to RawTCPDriver")
        return RawTCPDriver(host, port)
