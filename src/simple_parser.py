"""
Simple, effective parser for Android UI that actually works
"""
from lxml import etree
from typing import Dict, List, Any, Tuple
import re


def parse_ui_tree(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI into a simple tree structure that LLMs can understand.
    Focus on clarity and usefulness over complexity.
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Collect all interactive elements
    elements = []
    element_index = 0
    
    # Process all nodes
    for node in root.xpath("//node"):
        element_data = _extract_element_data(node, element_index)
        if element_data:
            elements.append(element_data)
            element_index += 1
    
    # Organize elements by screen position
    organized = _organize_by_position(elements)
    
    # Identify patterns
    patterns = _identify_patterns(elements)
    
    return {
        "summary": {
            "total_elements": len(elements),
            "clickable": len([e for e in elements if e.get("clickable")]),
            "inputs": len([e for e in elements if e.get("type") == "input"]),
            "buttons": len([e for e in elements if e.get("type") == "button"])
        },
        "layout": organized,
        "patterns": patterns,
        "elements": elements
    }


def _extract_element_data(node, index: int) -> Dict[str, Any]:
    """Extract useful data from a node"""
    # Get attributes
    text = node.get("text", "").strip()
    content_desc = node.get("content-desc", "").strip()
    resource_id = node.get("resource-id", "")
    clickable = node.get("clickable", "false") == "true"
    enabled = node.get("enabled", "false") == "true"
    focusable = node.get("focusable", "false") == "true"
    ui_class = node.get("class", "")
    bounds = node.get("bounds", "")
    
    # Skip if disabled or no identity
    if not enabled:
        return None
    
    # Must have some way to identify it
    if not (text or content_desc or (resource_id and "/" in resource_id)):
        return None
    
    # Determine type
    elem_type = _determine_type(ui_class, clickable, focusable)
    
    # Skip pure containers unless clickable
    if elem_type == "container" and not clickable:
        return None
    
    # Create label
    label = text or content_desc
    if not label and resource_id:
        # Extract meaningful part from resource ID
        if "/" in resource_id:
            label = resource_id.split("/")[-1].replace("_", " ").replace("-", " ")
    
    # Parse position
    position = None
    if bounds:
        try:
            x1, y1, x2, y2 = _parse_bounds(bounds)
            # Skip tiny elements
            if (x2 - x1) < 10 or (y2 - y1) < 10:
                return None
            position = {
                "x": (x1 + x2) // 2,
                "y": (y1 + y2) // 2,
                "area": _get_screen_area(x1, y1, x2, y2)
            }
        except:
            pass
    
    return {
        "id": index,
        "type": elem_type,
        "label": label,
        "clickable": clickable,
        "position": position,
        "resource_id": resource_id.split("/")[-1] if "/" in resource_id else ""
    }


def _determine_type(ui_class: str, clickable: bool, focusable: bool) -> str:
    """Determine element type from class and properties"""
    class_lower = ui_class.lower()
    
    if "edittext" in class_lower:
        return "input"
    elif "button" in class_lower:
        return "button"
    elif "textview" in class_lower and clickable:
        return "link"
    elif "imageview" in class_lower and clickable:
        return "image_button"
    elif "checkbox" in class_lower:
        return "checkbox"
    elif "switch" in class_lower:
        return "switch"
    elif "radiobutton" in class_lower:
        return "radio"
    elif clickable:
        return "clickable"
    elif focusable and "edittext" not in class_lower:
        return "selectable"
    elif any(x in class_lower for x in ["layout", "viewgroup", "relativelayout", "linearlayout"]):
        return "container"
    else:
        return "text"


def _parse_bounds(bounds_str: str) -> Tuple[int, int, int, int]:
    """Parse [x1,y1][x2,y2] format"""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not match:
        raise ValueError("Invalid bounds")
    return tuple(map(int, match.groups()))


def _get_screen_area(x1: int, y1: int, x2: int, y2: int) -> str:
    """Determine which area of screen the element is in"""
    center_y = (y1 + y2) / 2
    
    # Rough screen divisions (assuming typical mobile screen)
    if center_y < 200:
        return "header"
    elif center_y > 2000:  # Assuming ~2400px height
        return "footer"
    else:
        return "content"


def _organize_by_position(elements: List[Dict]) -> Dict[str, List[Dict]]:
    """Group elements by screen area"""
    areas = {
        "header": [],
        "content": [],
        "footer": []
    }
    
    for elem in elements:
        if elem.get("position"):
            area = elem["position"]["area"]
            areas[area].append({
                "id": elem["id"],
                "label": elem["label"],
                "type": elem["type"]
            })
    
    return areas


def _identify_patterns(elements: List[Dict]) -> Dict[str, Any]:
    """Identify common UI patterns"""
    patterns = {}
    
    # Check for login/auth pattern
    auth_keywords = ["login", "sign in", "password", "username", "email"]
    auth_elements = [e for e in elements if any(
        keyword in e["label"].lower() for keyword in auth_keywords
    )]
    if auth_elements:
        patterns["authentication"] = {
            "detected": True,
            "elements": [{"id": e["id"], "label": e["label"]} for e in auth_elements]
        }
    
    # Check for form pattern (multiple inputs)
    inputs = [e for e in elements if e["type"] == "input"]
    if len(inputs) >= 2:
        patterns["form"] = {
            "detected": True,
            "fields": [{"id": e["id"], "label": e["label"]} for e in inputs]
        }
    
    # Check for list pattern (multiple similar clickables)
    clickables = [e for e in elements if e.get("clickable") and e["type"] not in ["button", "input"]]
    if len(clickables) >= 5:
        patterns["list"] = {
            "detected": True,
            "item_count": len(clickables)
        }
    
    return patterns