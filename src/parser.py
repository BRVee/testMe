from lxml import etree
from typing import List, Dict, Any, Tuple
from pathlib import Path
import re


def parse(xml_path: str) -> List[Dict[str, Any]]:
    """
    Parse Android UI XML dump into a clean JSON list of nodes.
    
    Returns list of dicts with keys:
    - resource-id
    - text
    - content-desc
    - clickable
    - bounds
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    nodes = []
    
    # Traverse all nodes
    for node in root.xpath("//node"):
        node_info = {
            "resource-id": node.get("resource-id", ""),
            "text": node.get("text", ""),
            "content-desc": node.get("content-desc", ""),
            "clickable": node.get("clickable", "false") == "true",
            "bounds": node.get("bounds", "")
        }
        
        # Only include nodes that have some identifying information
        if node_info["resource-id"] or node_info["text"] or node_info["content-desc"]:
            nodes.append(node_info)
    
    return nodes


def parse_for_llm(xml_path: str) -> List[Dict[str, Any]]:
    """
    Parse Android UI XML dump into LLM-friendly format with descriptive information.
    
    Returns list of UI elements with:
    - index: Sequential number for easy reference
    - type: UI element type (button, text, input, etc.)
    - label: Human-readable label combining available text/descriptions
    - clickable: Whether the element can be clicked
    - location: Center coordinates for clicking
    - identifiers: Dict with resource-id, text, content-desc
    - ui_class: The Android class name
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    nodes = []
    index = 0
    
    # Traverse all nodes
    for node in root.xpath("//node"):
        # Get basic attributes
        resource_id = node.get("resource-id", "")
        text = node.get("text", "")
        content_desc = node.get("content-desc", "")
        clickable = node.get("clickable", "false") == "true"
        bounds = node.get("bounds", "")
        ui_class = node.get("class", "")
        enabled = node.get("enabled", "false") == "true"
        focusable = node.get("focusable", "false") == "true"
        scrollable = node.get("scrollable", "false") == "true"
        long_clickable = node.get("long-clickable", "false") == "true"
        password = node.get("password", "false") == "true"
        selected = node.get("selected", "false") == "true"
        
        # Skip nodes without any identifying information
        if not (resource_id or text or content_desc):
            continue
            
        # Determine element type from class name
        element_type = _get_element_type(ui_class)
        
        # Create human-readable label
        label = _create_label(text, content_desc, resource_id, element_type)
        
        # Parse bounds to get center coordinates
        if bounds:
            try:
                x1, y1, x2, y2 = _parse_bounds(bounds)
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                location = {"x": center_x, "y": center_y}
                size = {"width": x2 - x1, "height": y2 - y1}
            except:
                location = None
                size = None
        else:
            location = None
            size = None
        
        node_info = {
            "index": index,
            "type": element_type,
            "label": label,
            "clickable": clickable,
            "enabled": enabled,
            "location": location,
            "size": size,
            "identifiers": {
                "resource_id": resource_id,
                "text": text,
                "content_desc": content_desc
            },
            "properties": {
                "focusable": focusable,
                "scrollable": scrollable,
                "long_clickable": long_clickable,
                "password": password,
                "selected": selected
            },
            "ui_class": ui_class
        }
        
        nodes.append(node_info)
        index += 1
    
    return nodes


def _get_element_type(class_name: str) -> str:
    """Determine user-friendly element type from Android class name."""
    class_lower = class_name.lower()
    
    if "button" in class_lower:
        return "button"
    elif "edittext" in class_lower or "input" in class_lower:
        return "input"
    elif "textview" in class_lower:
        return "text"
    elif "imageview" in class_lower or "image" in class_lower:
        return "image"
    elif "checkbox" in class_lower:
        return "checkbox"
    elif "switch" in class_lower:
        return "switch"
    elif "radiobutton" in class_lower:
        return "radio_button"
    elif "spinner" in class_lower:
        return "dropdown"
    elif "seekbar" in class_lower:
        return "slider"
    elif "recyclerview" in class_lower or "listview" in class_lower:
        return "list"
    elif "scrollview" in class_lower:
        return "scroll_container"
    elif "webview" in class_lower:
        return "webview"
    elif "layout" in class_lower or "viewgroup" in class_lower:
        return "container"
    else:
        return "element"


def _create_label(text: str, content_desc: str, resource_id: str, element_type: str) -> str:
    """Create a human-readable label for the UI element."""
    # Prefer text, then content description, then resource ID
    if text:
        return text
    elif content_desc:
        return content_desc
    elif resource_id:
        # Extract meaningful part from resource ID (e.g., "com.app:id/login_button" -> "login button")
        if "/" in resource_id:
            id_part = resource_id.split("/")[-1]
            # Replace underscores and camelCase with spaces
            label = id_part.replace("_", " ").replace("-", " ")
            # Add spaces before capital letters in camelCase
            label = re.sub(r'(?<!^)(?=[A-Z])', ' ', label).lower()
            return f"{label} {element_type}".strip()
        else:
            return f"{resource_id} {element_type}"
    else:
        return element_type


def _parse_bounds(bounds_str: str) -> Tuple[int, int, int, int]:
    """Parse bounds string '[x1,y1][x2,y2]' into tuple of ints."""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not match:
        raise ValueError(f"Invalid bounds format: {bounds_str}")
    return tuple(map(int, match.groups()))


def parse_minimal_for_llm(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI XML into minimal JSON for fast LLM processing.
    
    Filters out:
    - Non-interactive elements (containers, layouts)
    - Invisible or disabled elements
    - Duplicate/redundant elements
    - Elements with no meaningful labels
    
    Returns:
    - Compact JSON with only actionable elements
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    elements = []
    seen_elements = set()  # Track duplicates
    index = 0
    
    for node in root.xpath("//node"):
        # Skip if not enabled
        if node.get("enabled", "false") != "true":
            continue
            
        # Get attributes
        resource_id = node.get("resource-id", "")
        text = node.get("text", "").strip()
        content_desc = node.get("content-desc", "").strip()
        clickable = node.get("clickable", "false") == "true"
        ui_class = node.get("class", "")
        bounds = node.get("bounds", "")
        
        # Skip non-interactive elements
        element_type = _get_element_type(ui_class)
        if element_type in ["container", "scroll_container"] and not clickable:
            continue
            
        # Skip elements with no meaningful identity
        if not text and not content_desc and not resource_id:
            continue
            
        # Create unique identifier to detect duplicates
        element_key = f"{text}|{content_desc}|{resource_id}|{clickable}"
        if element_key in seen_elements:
            continue
        seen_elements.add(element_key)
        
        # Skip tiny elements (likely decorative)
        if bounds:
            try:
                x1, y1, x2, y2 = _parse_bounds(bounds)
                width = x2 - x1
                height = y2 - y1
                if width < 20 or height < 20:  # Too small to interact with
                    continue
            except:
                pass
        
        # Create minimal element representation
        element = {
            "i": index,  # Short key name
            "t": element_type[0].upper(),  # B=button, T=text, I=input, etc.
            "l": _create_label(text, content_desc, resource_id, element_type),  # label
        }
        
        # Only add these if true/needed
        if clickable:
            element["c"] = 1  # clickable
        
        # Add interaction hints for LLM
        if element_type == "input":
            element["h"] = "type"  # hint: needs typing
        elif element_type == "button" or clickable:
            element["h"] = "click"  # hint: clickable
        
        elements.append(element)
        index += 1
    
    # Group similar elements (e.g., list items)
    grouped_elements = _group_similar_elements(elements)
    
    return {
        "e": grouped_elements,  # elements
        "n": len(grouped_elements),  # count
        "m": _generate_element_map(grouped_elements)  # Quick reference map
    }


def _group_similar_elements(elements: List[Dict]) -> List[Dict]:
    """
    Group similar list items to reduce JSON size.
    E.g., 10 similar items become: {type: "list", items: ["item1", "item2"...]}
    """
    if len(elements) < 5:  # Don't group small lists
        return elements
    
    grouped = []
    i = 0
    
    while i < len(elements):
        current = elements[i]
        
        # Look for patterns (same type elements in sequence)
        if i + 2 < len(elements):
            next1 = elements[i + 1]
            next2 = elements[i + 2]
            
            # Check if we have a pattern
            if (current.get("t") == next1.get("t") == next2.get("t") and
                current.get("c") == next1.get("c") == next2.get("c")):
                
                # Collect all similar items
                similar_items = [current["l"]]
                j = i + 1
                
                while j < len(elements) and elements[j].get("t") == current.get("t"):
                    similar_items.append(elements[j]["l"])
                    j += 1
                
                # Create grouped element
                grouped.append({
                    "i": current["i"],
                    "t": "L",  # List type
                    "l": f"List of {len(similar_items)} {current.get('t')} items",
                    "items": similar_items[:5],  # Show first 5 only
                    "h": "select"
                })
                
                i = j
                continue
        
        grouped.append(current)
        i += 1
    
    return grouped


def _generate_element_map(elements: List[Dict]) -> Dict[str, List[int]]:
    """
    Generate a quick lookup map for common UI patterns.
    Helps LLM quickly find elements by intent.
    """
    patterns = {
        "auth": ["login", "sign in", "password", "username", "email"],
        "nav": ["back", "home", "menu", "settings", "profile"],
        "action": ["submit", "save", "cancel", "ok", "done", "next"],
        "search": ["search", "find", "filter", "query"]
    }
    
    element_map = {}
    
    for pattern_name, keywords in patterns.items():
        matches = []
        for elem in elements:
            label_lower = elem.get("l", "").lower()
            if any(keyword in label_lower for keyword in keywords):
                matches.append(elem["i"])
        
        if matches:
            element_map[pattern_name] = matches
    
    return element_map


def parse_hierarchical_for_llm(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI XML into hierarchical structure with parent-child relationships.
    This helps LLM understand UI context and relationships between elements.
    
    Returns hierarchical JSON with:
    - Screen sections (header, content, footer, etc.)
    - Parent-child relationships
    - Semantic grouping
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Build the hierarchy
    screen_hierarchy = {
        "type": "screen",
        "sections": [],
        "actionable_elements": [],
        "navigation_map": {}
    }
    
    # Process root node to build tree
    _process_node_hierarchical(root, screen_hierarchy)
    
    # Post-process to identify sections
    screen_hierarchy["sections"] = _identify_screen_sections(screen_hierarchy)
    
    # Create a flat list of actionable elements with context
    actionable = _extract_actionable_with_context(screen_hierarchy["sections"])
    
    # Build the final structure
    result = {
        "screen": {
            "sections": screen_hierarchy["sections"],
            "quick_actions": _get_quick_actions(actionable),
            "forms": _identify_forms(screen_hierarchy["sections"]),
            "lists": _identify_lists(screen_hierarchy["sections"])
        },
        "elements": actionable,
        "count": len(actionable),
        "suggestions": _generate_suggestions(actionable)
    }
    
    return result


def _process_node_hierarchical(node, parent_dict, depth=0, index_counter=[0]):
    """Recursively process XML nodes to build hierarchy"""
    # Skip if depth is too deep (avoid UI noise)
    if depth > 10:
        return
    
    # Get node attributes
    resource_id = node.get("resource-id", "")
    text = node.get("text", "").strip()
    content_desc = node.get("content-desc", "").strip()
    clickable = node.get("clickable", "false") == "true"
    enabled = node.get("enabled", "false") == "true"
    ui_class = node.get("class", "")
    bounds = node.get("bounds", "")
    
    # Determine element type
    element_type = _get_element_type(ui_class)
    
    # Check if this is a meaningful container
    is_container = element_type in ["container", "scroll_container", "list"]
    has_identity = bool(text or content_desc or resource_id)
    
    # Process based on type
    if is_container and len(node) > 0:  # Has children
        # Create a container section
        container = {
            "type": _get_container_type(resource_id, ui_class),
            "children": [],
            "id": resource_id.split("/")[-1] if "/" in resource_id else ""
        }
        
        # Process children
        for child in node:
            _process_node_hierarchical(child, container, depth + 1, index_counter)
        
        # Only add non-empty containers
        if container["children"]:
            if "sections" not in parent_dict:
                parent_dict["sections"] = []
            parent_dict["sections"].append(container)
            
    elif (clickable or element_type in ["input", "button"]) and enabled and has_identity:
        # This is an actionable element
        element = {
            "idx": index_counter[0],
            "type": element_type,
            "label": _create_label(text, content_desc, resource_id, element_type),
            "action": _get_action_type(element_type, clickable),
            "context": _get_element_context(node, depth)
        }
        
        # Add bounds for spatial understanding
        if bounds:
            try:
                x1, y1, x2, y2 = _parse_bounds(bounds)
                element["position"] = _get_position_description(x1, y1, x2, y2)
            except:
                pass
        
        index_counter[0] += 1
        
        if "children" not in parent_dict:
            parent_dict["children"] = []
        parent_dict["children"].append(element)
    
    # Process remaining children even if current node isn't added
    for child in node:
        _process_node_hierarchical(child, parent_dict, depth + 1, index_counter)


def _get_container_type(resource_id: str, ui_class: str) -> str:
    """Identify semantic container type"""
    id_lower = resource_id.lower()
    class_lower = ui_class.lower()
    
    if any(x in id_lower for x in ["toolbar", "actionbar", "header", "appbar"]):
        return "header"
    elif any(x in id_lower for x in ["bottom", "navigation", "tab"]):
        return "navigation"
    elif any(x in id_lower for x in ["form", "input", "login", "signup"]):
        return "form"
    elif any(x in id_lower for x in ["list", "recycler", "grid"]):
        return "list"
    elif any(x in id_lower for x in ["dialog", "modal", "popup"]):
        return "dialog"
    elif "scroll" in class_lower:
        return "content"
    else:
        return "section"


def _get_action_type(element_type: str, clickable: bool) -> str:
    """Determine the primary action for an element"""
    if element_type == "input":
        return "type"
    elif element_type == "button" or clickable:
        return "click"
    elif element_type == "switch" or element_type == "checkbox":
        return "toggle"
    elif element_type == "dropdown":
        return "select"
    else:
        return "interact"


def _get_element_context(node, depth: int) -> Dict[str, Any]:
    """Get context information about element's position in hierarchy"""
    parent = node.getparent()
    if parent is not None:
        parent_class = parent.get("class", "")
        parent_type = _get_element_type(parent_class)
        
        # Count siblings of same type
        siblings = parent.findall(".//node")
        same_type_count = sum(1 for s in siblings if s.get("class") == node.get("class"))
        
        return {
            "parent_type": parent_type,
            "depth": depth,
            "siblings_count": len(siblings),
            "same_type_siblings": same_type_count
        }
    
    return {"depth": depth}


def _get_position_description(x1: int, y1: int, x2: int, y2: int) -> str:
    """Convert coordinates to human-readable position"""
    # Assume standard mobile screen dimensions
    screen_width = 1080  # Default assumption
    screen_height = 2400
    
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    
    # Determine horizontal position
    if center_x < screen_width * 0.33:
        h_pos = "left"
    elif center_x > screen_width * 0.67:
        h_pos = "right"
    else:
        h_pos = "center"
    
    # Determine vertical position
    if center_y < screen_height * 0.2:
        v_pos = "top"
    elif center_y > screen_height * 0.8:
        v_pos = "bottom"
    else:
        v_pos = "middle"
    
    if h_pos == "center" and v_pos == "middle":
        return "center"
    elif v_pos == "middle":
        return h_pos
    elif h_pos == "center":
        return v_pos
    else:
        return f"{v_pos}-{h_pos}"


def _identify_screen_sections(hierarchy: Dict) -> List[Dict]:
    """Organize the hierarchy into logical screen sections"""
    sections = hierarchy.get("sections", [])
    
    # Sort sections by type priority
    section_priority = {
        "header": 1,
        "navigation": 2,
        "form": 3,
        "content": 4,
        "list": 5,
        "dialog": 0,  # Highest priority if present
        "section": 6
    }
    
    sorted_sections = sorted(sections, 
                           key=lambda x: section_priority.get(x["type"], 99))
    
    return sorted_sections


def _extract_actionable_with_context(sections: List[Dict]) -> List[Dict]:
    """Extract all actionable elements with their section context"""
    actionable = []
    
    for section in sections:
        section_type = section["type"]
        _extract_from_section(section, actionable, section_type)
    
    return actionable


def _extract_from_section(section: Dict, actionable: List, parent_section: str):
    """Recursively extract actionable elements"""
    if "children" in section:
        for child in section["children"]:
            if isinstance(child, dict):
                if "action" in child:  # It's an actionable element
                    child["section"] = parent_section
                    actionable.append(child)
                else:  # It might be a nested section
                    _extract_from_section(child, actionable, parent_section)


def _identify_forms(sections: List[Dict]) -> List[Dict]:
    """Identify form-like structures"""
    forms = []
    
    for section in sections:
        if section["type"] == "form":
            forms.append({
                "type": "explicit_form",
                "fields": _get_form_fields(section)
            })
        else:
            # Look for implicit forms (multiple inputs together)
            inputs = _find_inputs_in_section(section)
            if len(inputs) >= 2:
                forms.append({
                    "type": "implicit_form",
                    "fields": inputs
                })
    
    return forms


def _get_form_fields(section: Dict) -> List[Dict]:
    """Extract form fields from a section"""
    fields = []
    
    def extract_fields(node):
        if "children" in node:
            for child in node["children"]:
                if child.get("type") == "input":
                    fields.append({
                        "idx": child["idx"],
                        "label": child["label"],
                        "required": "required" in child.get("label", "").lower()
                    })
                elif "children" in child:
                    extract_fields(child)
    
    extract_fields(section)
    return fields


def _find_inputs_in_section(section: Dict) -> List[Dict]:
    """Find all input elements in a section"""
    inputs = []
    
    def find_inputs(node):
        if "children" in node:
            for child in node["children"]:
                if child.get("type") == "input":
                    inputs.append({
                        "idx": child["idx"],
                        "label": child["label"]
                    })
                elif isinstance(child, dict):
                    find_inputs(child)
    
    find_inputs(section)
    return inputs


def _identify_lists(sections: List[Dict]) -> List[Dict]:
    """Identify list structures"""
    lists = []
    
    for section in sections:
        if section["type"] == "list":
            items = _get_list_items(section)
            if items:
                lists.append({
                    "type": "list",
                    "item_count": len(items),
                    "sample_items": items[:3]  # First 3 as sample
                })
    
    return lists


def _get_list_items(section: Dict) -> List[Dict]:
    """Extract list items"""
    items = []
    
    if "children" in section:
        for child in section["children"]:
            if child.get("action") == "click":
                items.append({
                    "idx": child["idx"],
                    "label": child["label"]
                })
    
    return items


def _get_quick_actions(elements: List[Dict]) -> List[Dict]:
    """Identify common quick actions"""
    quick_actions = []
    
    # Common action keywords
    action_keywords = {
        "submit": ["submit", "send", "post", "save", "confirm"],
        "cancel": ["cancel", "close", "dismiss", "back"],
        "auth": ["login", "sign in", "log in", "signin"],
        "search": ["search", "find", "filter"],
        "add": ["add", "create", "new", "plus"],
        "settings": ["settings", "preferences", "config"]
    }
    
    for element in elements:
        label_lower = element["label"].lower()
        for action_type, keywords in action_keywords.items():
            if any(keyword in label_lower for keyword in keywords):
                quick_actions.append({
                    "idx": element["idx"],
                    "type": action_type,
                    "label": element["label"]
                })
                break
    
    return quick_actions


def _generate_suggestions(elements: List[Dict]) -> Dict[str, Any]:
    """Generate smart suggestions for common tasks"""
    suggestions = {}
    
    # Check for forms
    input_elements = [e for e in elements if e["type"] == "input"]
    if input_elements:
        suggestions["form_detected"] = {
            "message": f"Found {len(input_elements)} input fields",
            "action": "Consider filling form fields sequentially"
        }
    
    # Check for authentication
    auth_elements = [e for e in elements if any(
        keyword in e["label"].lower() 
        for keyword in ["login", "sign in", "password", "username"]
    )]
    if auth_elements:
        suggestions["auth_detected"] = {
            "message": "Authentication elements detected",
            "fields": [e["idx"] for e in auth_elements]
        }
    
    return suggestions