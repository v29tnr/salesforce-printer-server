"""
ZPL (Zebra Programming Language) utilities and helpers.
Provides functions for generating, validating, and manipulating ZPL content.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ZPLDocument:
    """Helper class for building and validating ZPL documents."""
    
    def __init__(self):
        self.commands = []
        
    def start(self):
        """Start a ZPL document."""
        self.commands.append("^XA")
        return self
        
    def end(self):
        """End a ZPL document."""
        self.commands.append("^XZ")
        return self
        
    def add_command(self, command: str):
        """Add a raw ZPL command."""
        self.commands.append(command)
        return self
        
    def field_origin(self, x: int, y: int):
        """Set field origin (^FO)."""
        self.commands.append(f"^FO{x},{y}")
        return self
        
    def field_data(self, data: str):
        """Add field data (^FD)."""
        self.commands.append(f"^FD{data}^FS")
        return self
        
    def barcode_code128(self, height: int = 100, print_interpretation: bool = True):
        """Add Code 128 barcode (^BY and ^BC)."""
        interpretation = "Y" if print_interpretation else "N"
        self.commands.append(f"^BY2,3,{height}")
        self.commands.append(f"^BC,{height},,,,,{interpretation}")
        return self
        
    def barcode_qr(self, magnification: int = 5):
        """Add QR code (^BQ)."""
        self.commands.append(f"^BQ,2,{magnification}")
        return self
        
    def font(self, font: str = "0", height: int = 30, width: int = 30):
        """Set font (^A)."""
        self.commands.append(f"^A{font},{height},{width}")
        return self
        
    def label_home(self, x: int = 0, y: int = 0):
        """Set label home position (^LH)."""
        self.commands.append(f"^LH{x},{y}")
        return self
        
    def print_width(self, width: int):
        """Set print width (^PW)."""
        self.commands.append(f"^PW{width}")
        return self
        
    def label_length(self, length: int):
        """Set label length (^LL)."""
        self.commands.append(f"^LL{length}")
        return self
        
    def build(self) -> str:
        """Build the ZPL document as a string."""
        return "\n".join(self.commands)
        
    @classmethod
    def from_string(cls, zpl_string: str) -> 'ZPLDocument':
        """Create ZPLDocument from existing ZPL string."""
        doc = cls()
        doc.commands = [line.strip() for line in zpl_string.split('\n') if line.strip()]
        return doc


def validate_zpl(zpl_content: str) -> bool:
    """
    Validate basic ZPL syntax.
    
    Args:
        zpl_content: ZPL content string
        
    Returns:
        True if content appears to be valid ZPL
    """
    if not zpl_content or not isinstance(zpl_content, str):
        return False
        
    # Remove whitespace and convert to uppercase for checking
    content_upper = zpl_content.strip().upper()
    
    # Check for ZPL start command
    has_start = '^XA' in content_upper
    
    # Check for ZPL end command
    has_end = '^XZ' in content_upper
    
    # ZPL should have both start and end
    if not (has_start and has_end):
        logger.warning("ZPL content missing ^XA or ^XZ commands")
        return False
        
    # Check that ^XA comes before ^XZ
    start_pos = content_upper.find('^XA')
    end_pos = content_upper.find('^XZ')
    
    if start_pos >= end_pos:
        logger.warning("ZPL ^XA command should come before ^XZ")
        return False
        
    return True


def extract_zpl_metadata(zpl_content: str) -> Dict[str, Any]:
    """
    Extract metadata from ZPL content.
    
    Args:
        zpl_content: ZPL content string
        
    Returns:
        Dictionary with metadata (width, height, etc.)
    """
    metadata = {
        'valid': validate_zpl(zpl_content),
        'has_barcode': False,
        'has_qr': False,
        'has_text': False,
        'print_width': None,
        'label_length': None
    }
    
    lines = zpl_content.upper().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Check for barcodes
        if line.startswith('^B') and not line.startswith('^BQ'):
            metadata['has_barcode'] = True
        elif line.startswith('^BQ'):
            metadata['has_qr'] = True
            
        # Check for text fields
        if line.startswith('^FD'):
            metadata['has_text'] = True
            
        # Extract print width
        if line.startswith('^PW'):
            try:
                metadata['print_width'] = int(line[3:])
            except ValueError:
                pass
                
        # Extract label length
        if line.startswith('^LL'):
            try:
                metadata['label_length'] = int(line[3:])
            except ValueError:
                pass
                
    return metadata


def create_simple_label(text: str, width: int = 400, height: int = 200) -> str:
    """
    Create a simple text label in ZPL format.
    
    Args:
        text: Text to print on label
        width: Label width in dots
        height: Label height in dots
        
    Returns:
        ZPL string
    """
    doc = ZPLDocument()
    doc.start()
    doc.print_width(width)
    doc.label_length(height)
    doc.label_home(0, 0)
    doc.field_origin(50, 50)
    doc.font("0", 40, 40)
    doc.field_data(text)
    doc.end()
    
    return doc.build()


def create_barcode_label(
    barcode_data: str,
    text: Optional[str] = None,
    barcode_type: str = "code128",
    width: int = 400,
    height: int = 300
) -> str:
    """
    Create a barcode label in ZPL format.
    
    Args:
        barcode_data: Data to encode in barcode
        text: Optional text to display
        barcode_type: Type of barcode (code128 or qr)
        width: Label width in dots
        height: Label height in dots
        
    Returns:
        ZPL string
    """
    doc = ZPLDocument()
    doc.start()
    doc.print_width(width)
    doc.label_length(height)
    doc.label_home(0, 0)
    
    # Add text if provided
    if text:
        doc.field_origin(50, 30)
        doc.font("0", 30, 30)
        doc.field_data(text)
    
    # Add barcode
    barcode_y = 80 if text else 50
    doc.field_origin(50, barcode_y)
    
    if barcode_type.lower() == "qr":
        doc.barcode_qr(5)
    else:
        doc.barcode_code128(100, True)
        
    doc.field_data(barcode_data)
    doc.end()
    
    return doc.build()