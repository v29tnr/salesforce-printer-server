"""
Printer driver implementations.

Drivers are instantiated per-job from the event fields (host, port, type).
No static config required — the server is stateless with respect to printers.

Types:
  zpl  — Zebra / raw TCP socket (port 9100 default)
  raw  — Generic raw TCP socket
  cups — CUPS queue via lp, no PDF conversions needed
  ipp  — IPP printer via CUPS using constructed ipp:// URI
"""

import re
import socket
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SOCKET_TIMEOUT = 10
SGD_QUERY_TIMEOUT = 3.0

# ---------------------------------------------------------------------------
# Printer info cache — keyed by "host:port"
# Populated by SGD auto-discovery on first ZPL job to each printer.
# ---------------------------------------------------------------------------

_printer_info_cache: dict = {}


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
        _printer_info_cache.pop(f"{host}:{port}", None)
    else:
        _printer_info_cache.clear()


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
            logger.error(f"Timeout connecting to {self.host}:{self.port}")
            return False
        except socket.error as e:
            logger.error(f"Socket error → {self.host}:{self.port}: {e}")
            return False

    def print_pdf(self, content: bytes, options: dict) -> bool:
        # Raw TCP printers don't understand PDF — caller should not send PDF here
        logger.error(f"print_pdf called on RawTCPDriver ({self.host}:{self.port}) — not supported")
        return False

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
                logger.error(f"CUPS error: {result.stderr.strip()}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"CUPS lp timed out for {self.ipp_uri}")
            return False
        except Exception as e:
            logger.error(f"CUPS print error: {e}", exc_info=True)
            return False
        finally:
            if tmp:
                Path(tmp).unlink(missing_ok=True)


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
    elif t in ('cups', 'ipp'):
        return CUPSDriver(host, port)
    else:
        logger.warning(f"Unknown printer_type '{t}' — falling back to RawTCPDriver")
        return RawTCPDriver(host, port)
