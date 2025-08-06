"""
Complete parser - Captures ALL visible text and maintains relationships
"""
from lxml import etree
from typing import Dict, List, Any, Optional, Tuple
import re


def parse_complete_ui(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI capturing ALL visible elements including non-clickable text.
    This ensures LLM sees everything the user sees.
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Collect all visible elements
    all_elements = []
    element_id = 0
    
    # First pass: collect everything visible
    for node in root.xpath("//node"):
        elem_data = _extract_all_visible(node, element_id)
        if elem_data:
            all_elements.append(elem_data)
            element_id += 1
    
    # Second pass: establish relationships
    groups = _group_by_proximity(all_elements)
    
    # Third pass: link text labels to their clickable elements
    _link_labels_to_clickables(groups)
    
    return {
        "screen_content": groups,
        "all_elements": all_elements,
        "stats": {
            "total_visible": len(all_elements),
            "clickable": len([e for e in all_elements if e.get("clickable")]),
            "text_only": len([e for e in all_elements if e["type"] == "text"])
        }
    }


def _extract_all_visible(node, elem_id: int) -> Optional[Dict]:
    """Extract ALL visible elements, not just clickable ones"""
    # Get all attributes
    text = node.get("text", "").strip()
    desc = node.get("content-desc", "").strip()
    res_id = node.get("resource-id", "")
    clickable = node.get("clickable", "false") == "true"
    enabled = node.get("enabled", "false") == "true"
    visible = node.get("visibility", "visible") == "visible"
    class_name = node.get("class", "")
    bounds = node.get("bounds", "")
    
    # Skip if not visible or enabled
    if not enabled or not visible:
        return None
    
    # Get ANY visible text
    visible_text = text or desc
    if not visible_text and res_id and "/" in res_id:
        # Only use resource ID if really needed
        id_part = res_id.split("/")[-1]
        # Check if it's a meaningful ID
        if not any(x in id_part.lower() for x in ["layout", "container", "view", "group"]):
            visible_text = id_part.replace("_", " ").replace("-", " ").title()
    
    # Skip if no visible content at all
    if not visible_text:
        return None
    
    # Parse bounds to check size
    if bounds:
        try:
            x1, y1, x2, y2 = _parse_bounds(bounds)
            # Skip tiny elements (likely invisible)
            if (x2 - x1) < 5 or (y2 - y1) < 5:
                return None
        except:
            pass
    
    # Determine element type
    elem_type = _determine_element_type(class_name, clickable)
    
    # Build element data
    element = {
        "id": elem_id,
        "text": visible_text,
        "type": elem_type,
        "clickable": clickable,
        "bounds": bounds
    }
    
    # Add action for interactive elements
    if clickable or elem_type in ["input", "button"]:
        if elem_type == "input":
            element["action"] = "type"
        else:
            element["action"] = "tap"
    
    # Add semantic hints
    text_lower = visible_text.lower()
    if any(x in text_lower for x in ["sign up", "signup", "register", "create account"]):
        element["semantic"] = "signup"
    elif any(x in text_lower for x in ["login", "sign in", "log in"]):
        element["semantic"] = "login"
    elif any(x in text_lower for x in ["mobile", "phone", "number"]):
        element["semantic"] = "phone"
    elif any(x in text_lower for x in ["₹", "$", "€", "free", "bonus", "get"]):
        element["semantic"] = "offer"
    
    return element


def _determine_element_type(class_name: str, clickable: bool) -> str:
    """Determine element type"""
    class_lower = class_name.lower()
    
    if "edittext" in class_lower:
        return "input"
    elif "button" in class_lower:
        return "button"
    elif "imageview" in class_lower and clickable:
        return "image_button"
    elif "imageview" in class_lower:
        return "image"
    elif "textview" in class_lower and clickable:
        return "clickable_text"
    elif "textview" in class_lower:
        return "text"
    elif clickable:
        return "clickable"
    else:
        return "element"


def _parse_bounds(bounds_str: str) -> Tuple[int, int, int, int]:
    """Parse bounds string"""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not match:
        raise ValueError("Invalid bounds")
    return tuple(map(int, match.groups()))


def _group_by_proximity(elements: List[Dict]) -> List[Dict]:
    """Group elements that are near each other"""
    if not elements:
        return []
    
    groups = []
    current_group = {
        "elements": [],
        "bounds": None,
        "purpose": None
    }
    
    # Sort by vertical position
    sorted_elements = sorted(elements, key=lambda e: _get_y_position(e.get("bounds", "")))
    
    for elem in sorted_elements:
        if not elem.get("bounds"):
            current_group["elements"].append(elem)
            continue
            
        elem_y = _get_y_position(elem["bounds"])
        
        # Check if this element is close to the current group
        if current_group["elements"]:
            last_elem = current_group["elements"][-1]
            if last_elem.get("bounds"):
                last_y = _get_y_position(last_elem["bounds"])
                
                # If elements are far apart vertically, start new group
                if abs(elem_y - last_y) > 200:  # 200px threshold
                    if current_group["elements"]:
                        _finalize_group(current_group)
                        groups.append(current_group)
                    current_group = {
                        "elements": [],
                        "bounds": None,
                        "purpose": None
                    }
        
        current_group["elements"].append(elem)
    
    # Don't forget last group
    if current_group["elements"]:
        _finalize_group(current_group)
        groups.append(current_group)
    
    return groups


def _get_y_position(bounds_str: str) -> int:
    """Get Y coordinate from bounds"""
    if not bounds_str:
        return 0
    try:
        x1, y1, x2, y2 = _parse_bounds(bounds_str)
        return y1
    except:
        return 0


def _finalize_group(group: Dict):
    """Determine group purpose and clean up"""
    elements = group["elements"]
    
    # Collect all text
    all_text = " ".join(e["text"] for e in elements).lower()
    
    # Determine purpose
    if any(x in all_text for x in ["sign up", "signup", "register"]):
        group["purpose"] = "signup"
    elif any(x in all_text for x in ["login", "sign in"]):
        group["purpose"] = "login"
    elif any(e["type"] == "input" for e in elements):
        group["purpose"] = "form"
    elif any(e.get("semantic") == "offer" for e in elements):
        group["purpose"] = "offer"
    else:
        group["purpose"] = "content"
    
    # Find the main title (usually first text element)
    text_elements = [e for e in elements if e["type"] == "text"]
    if text_elements:
        group["title"] = text_elements[0]["text"]
    else:
        group["title"] = "Section"


def _link_labels_to_clickables(groups: List[Dict]):
    """Link text labels to their associated clickable elements"""
    for group in groups:
        elements = group["elements"]
        
        # Look for patterns where text precedes clickable
        for i in range(len(elements) - 1):
            current = elements[i]
            next_elem = elements[i + 1]
            
            # If current is text and next is clickable
            if (current["type"] == "text" and 
                not current.get("clickable") and 
                next_elem.get("clickable")):
                
                # Link them
                next_elem["label_text"] = current["text"]
                current["labels_element"] = next_elem["id"]
        
        # Also check for clickables without visible text
        for elem in elements:
            if elem.get("clickable") and not elem.get("text"):
                # Look for nearby text
                for other in elements:
                    if (other["type"] == "text" and 
                        not other.get("clickable") and
                        _are_nearby(elem, other)):
                        elem["nearby_text"] = other["text"]
                        break


def _are_nearby(elem1: Dict, elem2: Dict) -> bool:
    """Check if two elements are near each other"""
    if not elem1.get("bounds") or not elem2.get("bounds"):
        return False
    
    try:
        x1_1, y1_1, x2_1, y2_1 = _parse_bounds(elem1["bounds"])
        x1_2, y1_2, x2_2, y2_2 = _parse_bounds(elem2["bounds"])
        
        # Check if vertically aligned and close
        vertical_distance = abs(y1_1 - y1_2)
        horizontal_overlap = not (x2_1 < x1_2 or x2_2 < x1_1)
        
        return vertical_distance < 100 and horizontal_overlap
    except:
        return False