"""
Fast and simple parser for Android UI XML
"""
import xml.etree.ElementTree as ET
from typing import Dict, List, Any
import re


def parse_fast(xml_path: str) -> Dict[str, Any]:
    """
    Fast parser that creates a simple, flat structure optimized for LLM consumption.
    No complex tree traversal, just extract what's needed.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    elements = []
    elem_id = 0
    
    # Single pass - extract all meaningful elements
    for node in root.iter('node'):
        # Skip disabled elements
        if node.get('enabled', 'true') != 'true':
            continue
            
        # Get basic attributes
        text = node.get('text', '').strip()
        desc = node.get('content-desc', '').strip()
        res_id = node.get('resource-id', '')
        clickable = node.get('clickable') == 'true'
        class_name = node.get('class', '')
        bounds = node.get('bounds', '')
        
        # Skip empty elements
        visible_text = text or desc
        if not visible_text and not clickable:
            continue
            
        # Simple type detection
        elem_type = 'element'
        if 'EditText' in class_name:
            elem_type = 'input'
        elif 'Button' in class_name or (clickable and visible_text):
            elem_type = 'button'
        elif 'TextView' in class_name and not clickable:
            elem_type = 'text'
            
        # Create element
        elem = {
            'id': elem_id,
            'type': elem_type,
            'text': visible_text
        }
        
        # Only add extra fields if needed
        if clickable:
            elem['clickable'] = True
        if res_id:
            elem['resourceId'] = res_id
            
        elements.append(elem)
        elem_id += 1
    
    # Simple grouping - pair labels with following inputs
    grouped = []
    i = 0
    while i < len(elements):
        elem = elements[i]
        
        # Check if this is a label followed by an input
        if (elem['type'] == 'text' and 
            i + 1 < len(elements) and 
            elements[i + 1]['type'] == 'input'):
            # Create form group
            grouped.append({
                'type': 'form',
                'label': elem['text'],
                'inputId': elements[i + 1]['id']
            })
            i += 2  # Skip both elements
        else:
            # Add as-is
            grouped.append(elem)
            i += 1
    
    return {
        'elements': grouped,
        'total': len(grouped)
    }


def parse_ultra_fast(xml_content: str) -> List[Dict[str, Any]]:
    """
    Ultra-fast parser using regex - no XML parsing overhead.
    Returns a simple list of actionable elements.
    """
    elements = []
    elem_id = 0
    
    # Find all nodes with a simple regex
    node_pattern = r'<node[^>]+>'
    nodes = re.findall(node_pattern, xml_content)
    
    for node_str in nodes:
        # Quick attribute extraction
        if 'enabled="false"' in node_str:
            continue
            
        # Extract text
        text_match = re.search(r'text="([^"]*)"', node_str)
        text = text_match.group(1) if text_match else ''
        
        # Extract other attributes only if we have text or it's clickable
        if 'clickable="true"' not in node_str and not text:
            continue
            
        # Build element
        elem = {'id': elem_id, 'text': text}
        
        # Add resource ID if present
        res_match = re.search(r'resource-id="([^"]*)"', node_str)
        if res_match:
            elem['resourceId'] = res_match.group(1)
            
        # Determine if clickable
        if 'clickable="true"' in node_str:
            elem['action'] = 'tap'
            
        # Quick type detection
        if 'EditText' in node_str:
            elem['action'] = 'type'
        
        elements.append(elem)
        elem_id += 1
    
    return elements