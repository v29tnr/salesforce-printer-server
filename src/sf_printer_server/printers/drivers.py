"""
Printer driver implementations for various printer types.
Supports ZPL (Zebra), IPP/CUPS, and raw TCP/IP printing.
"""

import socket
import subprocess
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)


class PrinterDriver:
    """Base class for printer drivers."""
    
    def __init__(self, printer_config: Dict[str, Any]):
        """
        Initialize printer driver with configuration.
        
        Args:
            printer_config: Dictionary containing printer configuration
                - name: Printer name
                - type: Printer type (zpl, cups, raw)
                - host: IP address or hostname
                - port: Port number
                - queue: CUPS queue name (for CUPS printers)
        """
        self.name = printer_config.get('name', 'Unknown')
        self.printer_type = printer_config.get('type', 'raw')
        self.host = printer_config.get('host')
        self.port = printer_config.get('port', 9100)
        self.queue = printer_config.get('queue')
        
    def print(self, content: bytes) -> bool:
        """
        Send content to printer.
        
        Args:
            content: Raw bytes to print
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("This method should be overridden by subclasses.")
    
    def test_connection(self) -> bool:
        """Test if printer is reachable."""
        raise NotImplementedError("This method should be overridden by subclasses.")


class RawTCPPrinterDriver(PrinterDriver):
    """Driver for printers that accept raw TCP/IP connections (e.g., ZPL printers)."""
    
    def __init__(self, printer_config: Dict[str, Any]):
        super().__init__(printer_config)
        self.timeout = printer_config.get('timeout', 10)
        
    def print(self, content: bytes) -> bool:
        """
        Send raw data to printer via TCP/IP.
        
        Args:
            content: Raw bytes to print
            
        Returns:
            True if successful, False otherwise
        """
        if not self.host:
            logger.error(f"No host configured for printer {self.name}")
            return False
            
        try:
            logger.info(f"Connecting to printer {self.name} at {self.host}:{self.port}")
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                
                # Send data
                if isinstance(content, str):
                    content = content.encode('utf-8')
                    
                sock.sendall(content)
                logger.info(f"Successfully sent {len(content)} bytes to {self.name}")
                
            return True
            
        except socket.timeout:
            logger.error(f"Timeout connecting to printer {self.name} at {self.host}:{self.port}")
            return False
        except socket.error as e:
            logger.error(f"Socket error printing to {self.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error printing to {self.name}: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test TCP connection to printer."""
        if not self.host:
            return False
            
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((self.host, self.port))
            return True
        except Exception as e:
            logger.debug(f"Connection test failed for {self.name}: {e}")
            return False


class ZPLPrinterDriver(RawTCPPrinterDriver):
    """Driver for Zebra ZPL printers."""
    
    def print(self, content: bytes) -> bool:
        """
        Print ZPL content.
        
        Args:
            content: ZPL commands as bytes or string
            
        Returns:
            True if successful, False otherwise
        """
        # Validate ZPL content
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='ignore')
        else:
            content_str = content
            
        if not self._validate_zpl(content_str):
            logger.warning(f"Content may not be valid ZPL for printer {self.name}")
        
        return super().print(content)
    
    def _validate_zpl(self, content: str) -> bool:
        """Basic ZPL validation."""
        # Check for ZPL start command
        return '^XA' in content or '^xa' in content.lower()
    
    def get_printer_status(self) -> Optional[str]:
        """
        Query printer status using ZPL commands.
        
        Returns:
            Status string or None if query failed
        """
        if not self.host:
            return None
            
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((self.host, self.port))
                
                # Send host status command
                sock.sendall(b'~HS\r\n')
                
                # Receive response
                response = sock.recv(1024)
                return response.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.error(f"Error querying status for {self.name}: {e}")
            return None


class CUPSPrinterDriver(PrinterDriver):
    """Driver for CUPS-managed printers on Linux/Unix systems."""
    
    def print(self, content: bytes) -> bool:
        """
        Print using CUPS (lp command).
        
        Args:
            content: Content to print
            
        Returns:
            True if successful, False otherwise
        """
        if not self.queue:
            logger.error(f"No CUPS queue configured for printer {self.name}")
            return False
        
        try:
            # Write content to temporary file
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
                temp_path = f.name
                if isinstance(content, str):
                    content = content.encode('utf-8')
                f.write(content)
            
            # Use lp command to print
            cmd = ['lp', '-d', self.queue, temp_path]
            logger.info(f"Printing to CUPS queue {self.queue}: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully printed to {self.name}: {result.stdout.strip()}")
                return True
            else:
                logger.error(f"CUPS print failed for {self.name}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout printing to CUPS queue {self.queue}")
            return False
        except Exception as e:
            logger.error(f"Error printing to CUPS queue {self.queue}: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test if CUPS queue exists."""
        try:
            result = subprocess.run(
                ['lpstat', '-p', self.queue],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"CUPS queue test failed for {self.name}: {e}")
            return False


def get_printer_driver(printer_config: Dict[str, Any]) -> PrinterDriver:
    """
    Factory function to get appropriate printer driver.
    
    Args:
        printer_config: Printer configuration dictionary
        
    Returns:
        Appropriate PrinterDriver instance
    """
    printer_type = printer_config.get('type', 'raw').lower()
    
    if printer_type == 'zpl':
        return ZPLPrinterDriver(printer_config)
    elif printer_type == 'cups':
        return CUPSPrinterDriver(printer_config)
    elif printer_type == 'raw':
        return RawTCPPrinterDriver(printer_config)
    else:
        logger.warning(f"Unknown printer type '{printer_type}', using raw TCP driver")
        return RawTCPPrinterDriver(printer_config)