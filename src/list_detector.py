"""
List detector - Identifies and properly groups list items
"""
from typing import Dict, List, Any, Tuple
import re


def detect_and_group_list_items(elements: List[Dict]) -> List[Dict]:
    """
    Detect list patterns and group items correctly.
    Each list item becomes its own group.
    """
    # First, identify elements that are in lists
    list_elements = [e for e in elements if e.get("in_list", False)]
    non_list_elements = [e for e in elements if not e.get("in_list", False)]
    
    if not list_elements:
        # No list elements, return as is
        return [{"elements": elements, "type": "group"}]
    
    # Analyze list structure to find repeating patterns
    list_items = _identify_list_items(list_elements)
    
    # Create groups for list items
    groups = []
    
    # Add non-list elements as separate groups
    if non_list_elements:
        groups.append({
            "elements": non_list_elements,
            "type": "non_list_group"
        })
    
    # Add each list item as its own group
    for item in list_items:
        groups.append(item)
    
    return groups


def _identify_list_items(elements: List[Dict]) -> List[Dict]:
    """
    Identify individual list items by analyzing bounds and patterns.
    """
    # Sort elements by position (y first for vertical lists, x for horizontal)
    # Detect if it's horizontal or vertical by checking variance
    x_positions = [_get_x_center(_parse_bounds(e.get("bounds", "[0,0][0,0]"))) for e in elements]
    y_positions = [_get_y_center(_parse_bounds(e.get("bounds", "[0,0][0,0]"))) for e in elements]
    
    x_variance = max(x_positions) - min(x_positions) if x_positions else 0
    y_variance = max(y_positions) - min(y_positions) if y_positions else 0
    
    is_horizontal = x_variance > y_variance
    
    # Sort by primary axis
    if is_horizontal:
        elements.sort(key=lambda e: _get_x_center(_parse_bounds(e.get("bounds", "[0,0][0,0]"))))
    else:
        elements.sort(key=lambda e: _get_y_center(_parse_bounds(e.get("bounds", "[0,0][0,0]"))))
    
    # Find patterns - look for repeating element types
    patterns = _find_repeating_patterns(elements)
    
    # Group elements into list items
    list_items = []
    
    if patterns:
        # Use patterns to group
        list_items = _group_by_patterns(elements, patterns, is_horizontal)
    else:
        # Fallback: group by proximity
        list_items = _group_by_proximity(elements, is_horizontal)
    
    return list_items


def _find_repeating_patterns(elements: List[Dict]) -> List[List[str]]:
    """
    Find repeating patterns in element types.
    For example: [text, text, button] repeating
    """
    # Create type sequence
    type_sequence = []
    for e in elements:
        # Create a type signature
        if e.get("action") == "tap":
            type_sig = "tap_area"
        elif e["type"] == "text" and any(badge in e.get("label", "").upper() for badge in ["NEW!", "HOT!", "IPL", "5%"]):
            type_sig = "badge"
        elif e["type"] == "text":
            type_sig = "text"
        else:
            type_sig = e["type"]
        
        type_sequence.append(type_sig)
    
    # Find repeating subsequences
    patterns = []
    for pattern_len in range(2, min(8, len(type_sequence) // 2)):
        pattern = type_sequence[:pattern_len]
        
        # Check if this pattern repeats
        is_pattern = True
        for i in range(pattern_len, len(type_sequence), pattern_len):
            if type_sequence[i:i+pattern_len] != pattern:
                is_pattern = False
                break
        
        if is_pattern:
            patterns.append(pattern)
    
    return patterns


def _group_by_patterns(elements: List[Dict], patterns: List[List[str]], is_horizontal: bool) -> List[Dict]:
    """Group elements based on detected patterns."""
    if not patterns:
        return _group_by_proximity(elements, is_horizontal)
    
    # Use the longest pattern
    pattern = max(patterns, key=len)
    pattern_len = len(pattern)
    
    list_items = []
    for i in range(0, len(elements), pattern_len):
        item_elements = elements[i:i+pattern_len]
        if item_elements:
            # Find the main text (title) for this item
            title = "Item"
            for e in item_elements:
                if e["type"] == "text" and not any(badge in e.get("label", "").upper() for badge in ["NEW!", "HOT!", "IPL", "5%"]):
                    # This is likely the title
                    if any(game in e.get("label", "").lower() for game in ["poker", "rummy", "patti", "skill", "cricket", "opinio", "crash", "call break"]):
                        title = e["label"]
                        break
            
            list_items.append({
                "title": title,
                "type": "list_item",
                "elements": item_elements
            })
    
    return list_items


def _group_by_proximity(elements: List[Dict], is_horizontal: bool) -> List[Dict]:
    """Group elements by spatial proximity."""
    list_items = []
    current_item = None
    last_pos = -1000
    
    for elem in elements:
        bounds = _parse_bounds(elem.get("bounds", "[0,0][0,0]"))
        pos = _get_x_center(bounds) if is_horizontal else _get_y_center(bounds)
        
        # Check if this is a new item
        threshold = 200 if is_horizontal else 150
        if pos - last_pos > threshold:
            # Save current item
            if current_item:
                list_items.append(current_item)
            
            # Start new item
            current_item = {
                "title": elem.get("label", "Item"),
                "type": "list_item",
                "elements": [elem]
            }
        else:
            # Add to current item
            if current_item:
                current_item["elements"].append(elem)
                # Update title if we find a better one
                if elem["type"] == "text" and len(elem.get("label", "")) > len(current_item["title"]):
                    current_item["title"] = elem["label"]
    
        last_pos = pos
    
    # Don't forget last item
    if current_item:
        list_items.append(current_item)
    
    return list_items


def _parse_bounds(bounds_str: str) -> Tuple[int, int, int, int]:
    """Parse bounds string '[x1,y1][x2,y2]' into tuple"""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not match:
        return (0, 0, 0, 0)
    return tuple(map(int, match.groups()))


def _get_x_center(bounds: Tuple[int, int, int, int]) -> int:
    """Get x center of bounds"""
    return (bounds[0] + bounds[2]) // 2


def _get_y_center(bounds: Tuple[int, int, int, int]) -> int:
    """Get y center of bounds"""
    return (bounds[1] + bounds[3]) // 2