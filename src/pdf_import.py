"""
PDF Import Module for Utilities Tracker
Handles PDF rendering, visual field mapping, and text extraction.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


# Field definitions for each utility type
FIELD_DEFINITIONS = {
    'electric': [
        {'name': 'bill_date', 'label': 'Bill Date', 'type': 'date', 'required': True,
         'patterns': [
             r'(\d{1,2}/\d{1,2}/\d{2,4})',  # MM/DD/YYYY or MM/DD/YY
             r'(\d{1,2}-\d{1,2}-\d{2,4})',  # MM-DD-YYYY
             r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})',  # Month DD, YYYY
             r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})',  # DD Month YYYY
             r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})',  # Month DD (short)
         ]},
        {'name': 'usage_kwh', 'label': 'Usage (kWh)', 'type': 'number', 'required': True,
         'patterns': [
             r'([\d,]+)(?:\.\d*)?\s*kWh',  # Number (ignore decimals) followed by kWh
             r'([\d,]+)(?:\.\d*)?\s*kwh',  # Number (ignore decimals) followed by kwh  
             r'([\d,]+)(?:\.\d*)?',  # Just a whole number (ignore decimals)
         ]},
        {'name': 'total_cost', 'label': 'Total Cost', 'type': 'currency', 'required': True,
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
        {'name': 'days', 'label': 'Service Days', 'type': 'integer', 'required': True,
         'patterns': [r'(\d+)\s*days?', r'(\d{2,3})(?!\d)']},  # 2-3 digit number not followed by more digits
        {'name': 'meter_reading', 'label': 'Meter Reading', 'type': 'number', 'required': False,
         'patterns': [r'([\d,]+)']},
        {'name': 'electric_cost', 'label': 'Electric Cost', 'type': 'currency', 'required': False,
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
        {'name': 'taxes', 'label': 'Taxes', 'type': 'currency', 'required': False,
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
    ],
    'gas': [
        {'name': 'bill_date', 'label': 'Bill Date', 'type': 'date', 'required': True,
         'patterns': [
             # Date range patterns - capture the SECOND (end) date
             r'\d{1,2}/\d{1,2}/\d{2,4}\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})',  # MM/DD/YY-MM/DD/YY
             r'\d{1,2}-\d{1,2}-\d{2,4}\s*[-–]\s*(\d{1,2}-\d{1,2}-\d{2,4})',  # MM-DD-YY-MM-DD-YY
             # Single date patterns
             r'(\d{1,2}/\d{1,2}/\d{2,4})',
             r'(\d{1,2}-\d{1,2}-\d{2,4})',
             r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})',
             r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})',
             r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})',  # Month DD (short)
         ]},
        {'name': 'usage_ccf', 'label': 'Usage (CCF)', 'type': 'number', 'required': True,
         'patterns': [r'([\d,]+)(?:\.\d*)?\s*(?:ccf|CCF)', r'([\d,]+)(?:\.\d*)?']},
        {'name': 'total_cost', 'label': 'Total Cost', 'type': 'currency', 'required': True,
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
        {'name': 'days', 'label': 'Service Days', 'type': 'integer', 'required': True,
         'patterns': [r'(\d+)\s*days?', r'(\d{2,3})(?!\d)']},
        {'name': 'therms', 'label': 'Therms', 'type': 'number', 'required': False,
         'patterns': [r'([\d,]+)(?:\.\d*)?']},
        {'name': 'meter_reading', 'label': 'Meter Reading', 'type': 'number', 'required': False,
         'patterns': [r'([\d,]+)']},
        {'name': 'btu_factor', 'label': 'BTU Factor', 'type': 'number', 'required': False,
         'patterns': [
             r'[Xx]\s*[\$]?\s*(\d+\.\d{4,})',  # "X $1.279167" - captures long decimals (4+ places)
             r'(\d+\.\d{4,})',  # Just the long decimal number
             r'[Xx]\s*[\$]?\s*(\d+\.\d+)',  # "X $1.27" - shorter decimals
             r'(\d+\.\d+)',  # Any decimal
         ]},
        {'name': 'service_charge', 'label': 'Service Charge', 'type': 'currency', 'required': False,
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
        {'name': 'taxes', 'label': 'Taxes', 'type': 'currency', 'required': False,
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
    ],
    'water': [
        {'name': 'bill_date', 'label': 'Bill Date', 'type': 'date', 'required': True,
         'patterns': [
             r'(\d{1,2}/\d{1,2}/\d{2,4})',
             r'(\d{1,2}-\d{1,2}-\d{2,4})',
             r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})',
             r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})',
             r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})',  # Month DD (short)
         ]},
        {'name': 'usage_gallons', 'label': 'Usage (Gallons)', 'type': 'number', 'required': True,
         'patterns': [r'([\d,]+)(?:\.\d*)?\s*(?:gal|gallons?)', r'([\d,]+)(?:\.\d*)?']},
        {'name': 'total_cost', 'label': 'Total Cost', 'type': 'currency', 'required': True,
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
        {'name': 'meter_reading', 'label': 'Meter Reading', 'type': 'number', 'required': False,
         'patterns': [r'([\d,]+)']},
        {'name': 'water_cost', 'label': 'Water Cost', 'type': 'currency', 'required': False,
         'mappable': False,  # Auto-calculated: Total - Service Charge
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
        {'name': 'service_charge', 'label': 'Service Charge', 'type': 'currency', 'required': False,
         'mappable': False,  # Uses last bill's value
         'patterns': [r'\$\s*([\d,]+\.?\d*)', r'([\d,]+\.\d{2})']},
    ],
}


@dataclass
class TextBlock:
    """Represents a text block extracted from PDF with position."""
    text: str
    x: float
    y: float
    width: float
    height: float
    page: int


class PDFExtractor:
    """Handles PDF rendering and text extraction with positions."""
    
    def __init__(self):
        self.pdf_doc = None
        self.text_blocks: List[TextBlock] = []
        self.page_images = []  # PNG bytes of pages
        self.page_sizes = []  # (width, height) of each page
        self.scale_factor = 2.0  # Render at 2x for clarity
        self.error_message = ""  # Store error for display
    
    def load_pdf(self, pdf_path: str) -> bool:
        """Load a PDF file and extract text blocks with positions."""
        self.error_message = ""
        
        # Try PyMuPDF first (for visual mapping)
        try:
            import fitz  # PyMuPDF
            
            self.pdf_doc = fitz.open(pdf_path)
            self.text_blocks = []
            self.page_images = []
            self.page_sizes = []
            
            for page_num, page in enumerate(self.pdf_doc):
                # Get page size
                rect = page.rect
                self.page_sizes.append((rect.width, rect.height))
                
                # Extract text blocks with positions
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block.get("type") == 0:  # Text block
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "").strip()
                                if text:
                                    bbox = span.get("bbox", (0, 0, 0, 0))
                                    self.text_blocks.append(TextBlock(
                                        text=text,
                                        x=bbox[0],
                                        y=bbox[1],
                                        width=bbox[2] - bbox[0],
                                        height=bbox[3] - bbox[1],
                                        page=page_num
                                    ))
                
                # Render page as image
                mat = fitz.Matrix(self.scale_factor, self.scale_factor)
                pix = page.get_pixmap(matrix=mat)
                self.page_images.append(pix.tobytes("png"))
            
            return True
            
        except ImportError:
            self.error_message = "PyMuPDF not installed. Run: pip install PyMuPDF"
            # Try fallback to pdfplumber (text only, no visual)
            return self._load_with_pdfplumber(pdf_path)
            
        except Exception as e:
            self.error_message = f"Error loading PDF: {e}"
            # Try fallback
            return self._load_with_pdfplumber(pdf_path)
    
    def _load_with_pdfplumber(self, pdf_path: str) -> bool:
        """Fallback PDF loading using pdfplumber (no visual mapping)."""
        try:
            import pdfplumber
            
            self.text_blocks = []
            self.page_images = []
            self.page_sizes = []
            
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Get page size
                    self.page_sizes.append((page.width, page.height))
                    
                    # Extract text with positions
                    if page.chars:
                        # Group characters into words/lines
                        current_line = []
                        current_y = None
                        
                        for char in sorted(page.chars, key=lambda c: (c['top'], c['x0'])):
                            if current_y is None or abs(char['top'] - current_y) > 5:
                                # New line
                                if current_line:
                                    text = ''.join(c['text'] for c in current_line)
                                    if text.strip():
                                        self.text_blocks.append(TextBlock(
                                            text=text.strip(),
                                            x=current_line[0]['x0'],
                                            y=current_line[0]['top'],
                                            width=current_line[-1]['x1'] - current_line[0]['x0'],
                                            height=current_line[0]['height'],
                                            page=page_num
                                        ))
                                current_line = [char]
                                current_y = char['top']
                            else:
                                current_line.append(char)
                        
                        # Don't forget last line
                        if current_line:
                            text = ''.join(c['text'] for c in current_line)
                            if text.strip():
                                self.text_blocks.append(TextBlock(
                                    text=text.strip(),
                                    x=current_line[0]['x0'],
                                    y=current_line[0]['top'],
                                    width=current_line[-1]['x1'] - current_line[0]['x0'],
                                    height=current_line[0]['height'],
                                    page=page_num
                                ))
                    
                    # No image rendering with pdfplumber
                    self.page_images.append(None)
            
            if self.text_blocks:
                self.error_message = "Loaded with pdfplumber (text-only mode, no visual mapping)"
                return True
            else:
                self.error_message = "No text found in PDF"
                return False
                
        except ImportError:
            self.error_message = "Neither PyMuPDF nor pdfplumber installed"
            return False
        except Exception as e:
            self.error_message = f"Error with pdfplumber: {e}"
            return False
    
    def get_page_image_data(self, page_num: int = 0) -> Optional[bytes]:
        """Get page image as PNG bytes for display."""
        if page_num < len(self.page_images):
            return self.page_images[page_num]
        return None
    
    def get_page_size(self, page_num: int = 0) -> Tuple[float, float]:
        """Get page size (width, height) in points."""
        if page_num < len(self.page_sizes):
            return self.page_sizes[page_num]
        return (612, 792)  # Default letter size
    
    def get_scaled_page_size(self, page_num: int = 0) -> Tuple[int, int]:
        """Get scaled page size for display."""
        w, h = self.get_page_size(page_num)
        return (int(w * self.scale_factor), int(h * self.scale_factor))
    
    def find_text_at_position(self, x: float, y: float, page: int = 0, 
                              radius: float = 50) -> List[TextBlock]:
        """Find text blocks near a position (in PDF coordinates)."""
        results = []
        for block in self.text_blocks:
            if block.page != page:
                continue
            # Check if position is near the block
            cx = block.x + block.width / 2
            cy = block.y + block.height / 2
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if dist < radius:
                results.append(block)
        # Sort by distance
        results.sort(key=lambda b: ((x - b.x) ** 2 + (y - b.y) ** 2) ** 0.5)
        return results
    
    def find_anchor_text(self, x: float, y: float, page: int = 0) -> Optional[str]:
        """Find the nearest label/anchor text to the left or above a position."""
        import re
        
        def is_label_text(text: str) -> bool:
            """Check if text looks like a label (not just a number/value)."""
            text = text.strip()
            # If it's purely numeric (with optional $ , . -), it's a value, not a label
            if re.match(r'^[\$\-\d,.\s]+$', text):
                return False
            # If it contains letters, it's likely a label
            if re.search(r'[a-zA-Z]', text):
                return True
            return False
        
        candidates = []
        for block in self.text_blocks:
            if block.page != page:
                continue
            
            # Skip blocks that look like values (just numbers)
            if not is_label_text(block.text):
                continue
            
            # Calculate distance from point to block
            y_dist = abs(block.y - y)
            x_dist = abs(block.x - x)
            
            # Look for text to the left or above, or very close
            if block.x < x + 50:  # Allow overlap and nearby
                # Score: prefer same line, then closest
                if y_dist < 20:  # Same line
                    score = x_dist
                elif block.y < y:  # Above
                    score = y_dist + x_dist * 0.5
                else:
                    score = y_dist * 10 + x_dist
                
                # More lenient range
                if y_dist < 100 and x_dist < 400:
                    candidates.append((score, block))
        
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1].text
        
        # Fallback: find absolutely nearest text block that looks like a label
        nearest = None
        nearest_dist = float('inf')
        for block in self.text_blocks:
            if block.page != page:
                continue
            if not is_label_text(block.text):
                continue
            dist = ((x - block.x) ** 2 + (y - block.y) ** 2) ** 0.5
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = block
        
        if nearest and nearest_dist < 300:
            return nearest.text
        
        return None
    
    def get_text_in_region(self, x: float, y: float, width: float, height: float, 
                           page: int = 0) -> str:
        """Get all text within a rectangular region."""
        texts = []
        for block in self.text_blocks:
            if block.page != page:
                continue
            # Check if block overlaps with region
            if (block.x < x + width and block.x + block.width > x and
                block.y < y + height and block.y + block.height > y):
                texts.append((block.x, block.y, block.text))
        
        # Sort by position (top to bottom, left to right)
        texts.sort(key=lambda t: (t[1], t[0]))
        return " ".join(t[2] for t in texts)
    
    def extract_value_with_pattern(self, text: str, pattern: str) -> Optional[str]:
        """Extract a value from text using a regex pattern."""
        try:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Return the first group if exists, otherwise full match
                return match.group(1) if match.groups() else match.group()
        except re.error:
            pass
        return None
    
    def get_text_near_anchor(self, anchor: str, page: int = 0, 
                             search_radius: float = 200) -> str:
        """Get all text near an anchor text, including text in the same block."""
        # Find anchor position
        anchor_block = None
        anchor_lower = anchor.lower()
        for block in self.text_blocks:
            if block.page == page and anchor_lower in block.text.lower():
                anchor_block = block
                break
        
        if not anchor_block:
            return ""
        
        # Include the anchor block itself (for "Label: Value" format)
        result_parts = [(0, anchor_block.text)]
        anchor_right = anchor_block.x + anchor_block.width
        
        for block in self.text_blocks:
            if block.page != page:
                continue
            if block == anchor_block:
                continue
                
            dx = block.x - anchor_right
            dy = block.y - anchor_block.y
            
            # Same line, to the right
            if abs(dy) < 10 and dx > -5 and dx < search_radius:
                result_parts.append((dx + 1, block.text))
            # Below anchor, roughly aligned
            elif dy > 5 and dy < 40 and abs(block.x - anchor_block.x) < 150:
                result_parts.append((dy + 1000, block.text))
        
        result_parts.sort(key=lambda x: x[0])
        return " ".join(p[1] for p in result_parts)
    
    def extract_with_template(self, template: Dict, page: int = 0) -> Dict[str, str]:
        """Extract values using a saved template."""
        import re
        results = {}
        
        for field_name, mapping in template.items():
            # Support both coordinate-based and anchor-based templates
            x = mapping.get('x')
            y = mapping.get('y')
            template_page = mapping.get('page', 0)
            
            if x is not None and y is not None:
                # Coordinate-based extraction
                nearby_blocks = self.find_text_at_position(x, y, template_page, radius=60)
                if not nearby_blocks:
                    continue
                
                # Get closest block and combined text
                closest_text = nearby_blocks[0].text
                combined_text = " ".join(b.text for b in nearby_blocks[:3])
                
                # Try to extract clean value with patterns
                field_def = next((f for f in FIELD_DEFINITIONS.get('electric', []) + 
                                 FIELD_DEFINITIONS.get('gas', []) + 
                                 FIELD_DEFINITIONS.get('water', [])
                                 if f['name'] == field_name), None)
                
                value = None
                if field_def:
                    # Try closest text first, then combined
                    for text_to_try in [closest_text, combined_text]:
                        for pattern in field_def.get('patterns', []):
                            try:
                                match = re.search(pattern, text_to_try, re.IGNORECASE)
                                if match:
                                    value = match.group(1) if match.groups() else match.group()
                                    break
                            except re.error:
                                continue
                        if value:
                            break
                
                results[field_name] = value if value else closest_text
            else:
                # Legacy anchor-based extraction
                anchor = mapping.get('anchor', '')
                pattern = mapping.get('pattern', '')
                
                if not anchor:
                    continue
                
                text = self.get_text_near_anchor(anchor, page)
                if not text:
                    continue
                
                value = None
                if pattern:
                    value = self.extract_value_with_pattern(text, pattern)
                
                if not value:
                    field_def = next((f for f in FIELD_DEFINITIONS.get('electric', []) + 
                                     FIELD_DEFINITIONS.get('gas', []) + 
                                     FIELD_DEFINITIONS.get('water', [])
                                     if f['name'] == field_name), None)
                    if field_def:
                        for default_pattern in field_def.get('patterns', []):
                            value = self.extract_value_with_pattern(text, default_pattern)
                            if value:
                                break
                
                if value:
                    results[field_name] = value
        
        return results
    
    def get_full_text(self, page: int = 0) -> str:
        """Get all text from a page."""
        texts = []
        for block in self.text_blocks:
            if block.page == page:
                texts.append((block.y, block.x, block.text))
        texts.sort(key=lambda t: (t[0], t[1]))
        return "\n".join(t[2] for t in texts)
    
    def close(self):
        """Close the PDF document."""
        if self.pdf_doc:
            self.pdf_doc.close()
            self.pdf_doc = None


def get_field_definitions(utility_type: str) -> List[Dict]:
    """Get field definitions for a utility type."""
    return FIELD_DEFINITIONS.get(utility_type, [])


def parse_value(value: str, value_type: str):
    """Parse a string value into the appropriate type."""
    if not value:
        return None
    
    try:
        if value_type == 'currency':
            clean = re.sub(r'[$,]', '', value)
            return float(clean)
        
        elif value_type == 'number':
            clean = re.sub(r'[,$]', '', value)
            return float(clean)
        
        elif value_type == 'integer':
            # Extract just digits
            match = re.search(r'\d+', value)
            if match:
                return int(match.group())
            return None
        
        elif value_type == 'date':
            # Try various date formats
            formats = [
                '%b %d, %Y',   # Nov 3, 2025
                '%B %d, %Y',   # November 3, 2025
                '%b %d %Y',    # Nov 3 2025
                '%B %d %Y',    # November 3 2025
                '%m/%d/%Y',    # 11/03/2025
                '%m-%d-%Y',    # 11-03-2025
                '%m/%d/%y',    # 11/03/25
                '%m-%d-%y',    # 11-03-25
                '%Y-%m-%d',    # 2025-11-03
                '%d %b %Y',    # 3 Nov 2025
                '%d %B %Y',    # 3 November 2025
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(value.strip(), fmt).date()
                except ValueError:
                    continue
            
            # Try dateutil as fallback
            try:
                from dateutil import parser
                return parser.parse(value).date()
            except:
                pass
            
            return None
        
        return value
        
    except (ValueError, TypeError):
        return None


def validate_extraction(extracted: Dict[str, str], utility_type: str) -> Tuple[bool, List[str]]:
    """Validate extracted fields."""
    issues = []
    fields = get_field_definitions(utility_type)
    
    for field in fields:
        name = field['name']
        required = field['required']
        value = extracted.get(name, '')
        
        if required and not value:
            issues.append(f"Missing required field: {field['label']}")
        elif value:
            parsed = parse_value(value, field['type'])
            if parsed is None:
                issues.append(f"Invalid value for {field['label']}: {value}")
    
    # Sanity checks for common mistakes
    if utility_type == 'electric':
        usage = extracted.get('usage_kwh', '')
        meter = extracted.get('meter_reading', '')
        if usage:
            usage_val = parse_value(usage, 'number')
            if usage_val and usage_val > 10000:
                issues.append(f"⚠️ Usage ({usage_val:.0f} kWh) seems too high - may be meter reading?")
        if meter:
            meter_val = parse_value(meter, 'number')
            if meter_val and meter_val < 1000:
                issues.append(f"⚠️ Meter reading ({meter_val:.0f}) seems too low - may be usage?")
    
    elif utility_type == 'gas':
        usage = extracted.get('usage_ccf', '')
        if usage:
            usage_val = parse_value(usage, 'number')
            if usage_val and usage_val > 1000:
                issues.append(f"⚠️ Usage ({usage_val:.0f} CCF) seems too high - verify value")
    
    return len(issues) == 0, issues
