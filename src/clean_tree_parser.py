"""
Clean tree parser - Shows clear parent-child relationships
"""
import xml.etree.ElementTree as etree
from typing import Dict, List, Any, Optional, Tuple
import re
from .list_detector import detect_and_group_list_items


def parse_clean_tree(xml_path: str) -> Dict[str, Any]:
    """
    Parse Android UI into a clean tree showing parent-child relationships.
    Focuses on grouping related elements logically.
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # First pass: collect all meaningful elements
    all_elements = []
    _collect_elements(root, all_elements)
    
    # Second pass: group elements by proximity and context
    grouped = _group_related_elements(all_elements)
    
    # Create final structure
    result = {
        "groups": grouped,
        "flat_list": _create_flat_list(grouped),
        "total": sum(len(g["elements"]) for g in grouped)
    }
    
    return result


def _collect_elements(node, elements: List[Dict], parent_label: str = "", depth: int = 0, parent_class: str = ""):
    """Collect all meaningful elements with context"""
    # Get node attributes
    text = node.get("text", "").strip()
    desc = node.get("content-desc", "").strip()
    res_id = node.get("resource-id", "")
    clickable = node.get("clickable", "false") == "true"
    enabled = node.get("enabled", "false") == "true"
    class_name = node.get("class", "")
    bounds = node.get("bounds", "")
    
    # Check if this is a list container
    is_list = any(x in class_name.lower() for x in ["recyclerview", "listview", "horizontalscrollview", "scrollview"])
    
    # Skip disabled
    if not enabled:
        # Still process children
        for child in node:
            _collect_elements(child, elements, parent_label, depth + 1, class_name if is_list else parent_class)
        return
    
    # Create label
    label = text or desc
    if not label and res_id and "/" in res_id:
        label = res_id.split("/")[-1].replace("_", " ").replace("-", " ").title()
    
    # For touch elements without text, use a more descriptive label
    if not label and clickable:
        label = "touch_area"
    
    # Determine type
    elem_type = _determine_type(class_name, clickable)
    
    # Check if this provides context (non-clickable text often labels the next element)
    if elem_type == "text" and not clickable and label:
        # This might be a label for following elements
        parent_label = label
    
    # Check if this is interactive or has meaningful text
    is_interactive = elem_type in ["input", "button", "checkbox", "radio"] or clickable
    has_text = label and label != ""
    
    # Collect both interactive elements AND text elements
    if (is_interactive and label) or (has_text and elem_type == "text"):
        element = {
            "label": label,
            "type": elem_type,
            "parent_context": parent_label,
            "depth": depth,
            "bounds": bounds,
            "class": class_name,
            "in_list": parent_class and any(x in parent_class.lower() for x in ["recyclerview", "listview", "scrollview"])
        }
        
        # Determine action
        if elem_type == "input":
            element["action"] = "type"
        elif clickable:
            element["action"] = "tap"
        elif elem_type == "text":
            element["action"] = None  # Text elements are not actionable
        else:
            element["action"] = "interact"
            
        elements.append(element)
        
        # Don't reset parent label if this is just text
        if is_interactive:
            parent_label = ""
    
    # Process children
    for child in node:
        _collect_elements(child, elements, parent_label, depth + 1, class_name if is_list else parent_class)


def _determine_type(class_name: str, clickable: bool) -> str:
    """Determine element type from class"""
    class_lower = class_name.lower()
    
    if "edittext" in class_lower:
        return "input"
    elif "button" in class_lower:
        return "button"
    elif "checkbox" in class_lower:
        return "checkbox"
    elif "radiobutton" in class_lower:
        return "radio"
    elif "textview" in class_lower and not clickable:
        return "text"
    elif "textview" in class_lower and clickable:
        return "button"
    elif "imageview" in class_lower and clickable:
        return "button"
    else:
        return "element"


def _group_related_elements(elements: List[Dict]) -> List[Dict]:
    """Group elements that are related by context or position"""
    # First, analyze bounds to find potential containers
    grouped_elements = _group_by_proximity(elements)
    
    groups = []
    current_group = None
    last_parent_context = ""
    
    for i, elem in enumerate(elements):
        parent_context = elem.get("parent_context", "")
        
        # Check if this element is part of a proximity group
        proximity_group = elem.get("proximity_group")
        
        # Start new group if:
        # 1. We have a parent context that's different from last
        # 2. This is a standalone button/action
        if parent_context and parent_context != last_parent_context:
            # Save previous group
            if current_group and current_group["elements"]:
                groups.append(current_group)
            
            # Start new group
            current_group = {
                "title": parent_context,
                "type": "form_group",
                "elements": []
            }
            last_parent_context = parent_context
            
        elif not parent_context and elem["type"] == "button":
            # Standalone button - might be end of a form
            if current_group:
                current_group["elements"].append(elem)
                groups.append(current_group)
                current_group = None
                last_parent_context = ""
                continue
        
        # Add element to current group or create orphan group
        if current_group:
            current_group["elements"].append(elem)
        else:
            # Check if this element might belong to previous group
            if groups and elem["type"] in ["button", "input"]:
                # Check proximity to last group
                last_group = groups[-1]
                if len(last_group["elements"]) < 5:  # Reasonable form size
                    last_group["elements"].append(elem)
                    continue
            
            # Check if there's a previous text element that might be the label
            if (i > 0 and 
                elements[i-1]["type"] == "text" and 
                elem["type"] in ["button", "input"] and
                not elements[i-1].get("grouped")):
                # Group text with button/input
                group_title = elements[i-1]["label"]
                combined_group = {
                    "title": group_title,
                    "type": "labeled_action",
                    "elements": [elements[i-1], elem]
                }
                elements[i-1]["grouped"] = True
                groups.append(combined_group)
            else:
                # Create single element group
                single_group = {
                    "title": elem["label"],
                    "type": "single",
                    "elements": [elem]
                }
                groups.append(single_group)
    
    # Don't forget last group
    if current_group and current_group["elements"]:
        groups.append(current_group)
    
    # Merge groups that are part of the same visual component
    groups = _merge_related_groups(groups)
    
    # Post-process groups
    final_groups = []
    for group in groups:
        # Check if this group contains multiple list items that should be split
        if group.get("type") == "game_card" or group.get("in_list"):
            split_groups = _split_list_items(group)
            for split_group in split_groups:
                # Assign IDs to elements
                for elem in split_group["elements"]:
                    elem["id"] = len(final_groups) * 100 + split_group["elements"].index(elem)
                
                # Identify group purpose
                _identify_group_purpose(split_group)
                
                final_groups.append(split_group)
        else:
            # Assign IDs to elements
            for elem in group["elements"]:
                elem["id"] = len(final_groups) * 100 + group["elements"].index(elem)
            
            # Identify group purpose
            _identify_group_purpose(group)
            
            final_groups.append(group)
    
    return final_groups


def _identify_group_purpose(group: Dict):
    """Identify the purpose of a group based on its elements"""
    elements = group["elements"]
    
    # If already identified as promotional card, keep it
    if group.get("purpose") == "promotional":
        return
    
    # Check for common patterns
    has_inputs = any(e["type"] == "input" for e in elements)
    has_button = any(e["type"] == "button" for e in elements)
    
    # Check keywords in title and labels
    all_text = group["title"].lower() + " ".join(e["label"].lower() for e in elements)
    
    # Check for money/reward patterns
    if any(x in all_text for x in ["₹", "$", "cash", "earn", "money", "reward", "bonus", "win"]):
        group["purpose"] = "promotional"
    elif "sign up" in all_text or "signup" in all_text or "register" in all_text:
        group["purpose"] = "signup"
    elif "login" in all_text or "sign in" in all_text:
        group["purpose"] = "login"
    elif "mobile" in all_text or "phone" in all_text:
        group["purpose"] = "phone_entry"
    elif "otp" in all_text or "verification" in all_text:
        group["purpose"] = "verification"
    elif has_inputs and has_button:
        group["purpose"] = "form"
    elif has_button and not has_inputs:
        group["purpose"] = "actions"
    else:
        group["purpose"] = "info"


def _parse_bounds(bounds_str: str) -> Tuple[int, int, int, int]:
    """Parse bounds string '[x1,y1][x2,y2]' into tuple"""
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not match:
        return (0, 0, 0, 0)
    return tuple(map(int, match.groups()))


def _bounds_overlap_horizontally(b1: str, b2: str, threshold: int = 50) -> bool:
    """Check if two bounds overlap horizontally"""
    x1_1, y1_1, x2_1, y2_1 = _parse_bounds(b1)
    x1_2, y1_2, x2_2, y2_2 = _parse_bounds(b2)
    
    # Check if they overlap or are very close horizontally
    return not (x2_1 + threshold < x1_2 or x2_2 + threshold < x1_1)


def _bounds_are_vertically_close(b1: str, b2: str, threshold: int = 100) -> bool:
    """Check if two bounds are close vertically"""
    x1_1, y1_1, x2_1, y2_1 = _parse_bounds(b1)
    x1_2, y1_2, x2_2, y2_2 = _parse_bounds(b2)
    
    # Distance between bottom of first and top of second
    vertical_gap = abs(y2_1 - y1_2)
    return vertical_gap < threshold


def _check_if_related_to_card(elem: Dict, card_elements: List[Dict]) -> bool:
    """Check if an element (like touch area) is related to a card"""
    elem_bounds = elem.get("bounds")
    if not elem_bounds:
        return False
    
    elem_x1, elem_y1, elem_x2, elem_y2 = _parse_bounds(elem_bounds)
    
    for card_elem in card_elements:
        card_bounds = card_elem.get("bounds")
        if not card_bounds:
            continue
            
        card_x1, card_y1, card_x2, card_y2 = _parse_bounds(card_bounds)
        
        # Check if they overlap or are very close
        horizontal_overlap = not (elem_x2 < card_x1 or card_x2 < elem_x1)
        vertical_overlap = not (elem_y2 < card_y1 or card_y2 < elem_y1)
        
        # Also check if touch area encompasses the card elements
        encompasses = (elem_x1 <= card_x1 and elem_x2 >= card_x2 and 
                      elem_y1 <= card_y1 and elem_y2 >= card_y2)
        
        if (horizontal_overlap and vertical_overlap) or encompasses:
            return True
    
    return False


def _group_by_proximity(elements: List[Dict]) -> List[Dict]:
    """Mark elements that are likely part of the same visual component"""
    # For now, just return elements as-is
    # This is a placeholder for more sophisticated proximity analysis
    return elements


def _merge_related_groups(groups: List[Dict]) -> List[Dict]:
    """Merge groups that appear to be part of the same visual component"""
    if len(groups) < 2:
        return groups
    
    merged = []
    i = 0
    
    while i < len(groups):
        current = groups[i]
        
        # Special handling for game cards and list items
        # First check if elements are marked as being in a list
        in_list = any(elem.get("in_list", False) for elem in current["elements"])
        
        # Check if this looks like a badge (NEW!, HOT!, etc.)
        is_badge = False
        if len(current["elements"]) == 1:
            elem = current["elements"][0]
            text = elem["label"].upper()
            if text in ["NEW!", "HOT!", "POPULAR", "TRENDING", "FEATURED", "NEW", "IPL"]:
                is_badge = True
        
        # If it's a badge or we're in a list, look for the associated game/item
        if (is_badge or in_list) and i + 1 < len(groups):
            # Merge with the next group (likely the game title)
            next_group = groups[i + 1]
            
            # Also check if there's a touch area that should be included
            # Look ahead for touch areas that overlap with these bounds
            all_related_groups = [current, next_group]
            
            # Check the next few groups for related elements
            j = i + 2
            while j < len(groups) and j < i + 4:
                candidate = groups[j]
                
                # Check if this group has a touch/tap element
                for elem in candidate["elements"]:
                    if elem.get("action") == "tap":
                        # Check if bounds overlap with our game card
                        if _check_if_related_to_card(elem, current["elements"] + next_group["elements"]):
                            all_related_groups.append(candidate)
                            break
                j += 1
            
            # Create merged game card
            merged_group = {
                "title": next_group["title"],  # Use game name as title
                "type": "game_card",
                "elements": [],
                "purpose": "game"
            }
            
            # Add all elements from related groups
            for g in all_related_groups:
                merged_group["elements"].extend(g["elements"])
            
            merged.append(merged_group)
            i = i + len(all_related_groups)  # Skip processed groups
            continue
        
        # Look for groups that should be merged with this one
        if i + 1 < len(groups):
            next_group = groups[i + 1]
            
            # Check if groups are related (e.g., Cash Club example)
            should_merge = False
            
            # Get bounds of elements in each group
            current_bounds = [elem["bounds"] for elem in current["elements"] if elem.get("bounds")]
            next_bounds = [elem["bounds"] for elem in next_group["elements"] if elem.get("bounds")]
            
            if current_bounds and next_bounds:
                # Check if they're horizontally aligned and vertically close
                for cb in current_bounds:
                    for nb in next_bounds:
                        if (_bounds_overlap_horizontally(cb, nb) and 
                            _bounds_are_vertically_close(cb, nb)):
                            should_merge = True
                            break
                    if should_merge:
                        break
            
            # Also check for specific patterns
            # Pattern 1: Title + Amount + Button (like Cash Club)
            current_text = " ".join([e["label"] for e in current["elements"]]).lower()
            next_text = " ".join([e["label"] for e in next_group["elements"]]).lower()
            
            # Check for money/reward patterns or other card-like patterns
            is_card_pattern = (
                # Money patterns
                ("₹" in current_text or "₹" in next_text) or
                ("$" in current_text or "$" in next_text) or
                # Reward/earning patterns
                any(word in current_text for word in ["video", "earn", "cash", "reward"]) or
                any(word in next_text for word in ["get", "up to", "bonus", "win"]) or
                # Common card patterns
                (len(current["elements"]) == 1 and current["elements"][0]["type"] == "text" and
                 len(next_group["elements"]) >= 1 and any(e["type"] == "text" for e in next_group["elements"]))
            )
            
            if is_card_pattern:
                
                # Check if there's a button in the next 1-2 groups
                check_groups = groups[i:min(i+3, len(groups))]
                has_related_button = False
                
                for g in check_groups:
                    for elem in g["elements"]:
                        if elem.get("action") == "tap":
                            # Check if button is in same horizontal area
                            if current_bounds and elem.get("bounds"):
                                for cb in current_bounds:
                                    if _bounds_overlap_horizontally(cb, elem["bounds"]):
                                        has_related_button = True
                                        break
                
                if has_related_button:
                    # Merge the next 2-3 groups that are related
                    merged_group = {
                        "title": current["title"],
                        "type": "card",
                        "elements": current["elements"].copy(),
                        "purpose": "promotional"
                    }
                    
                    # Add elements from related groups
                    j = i + 1
                    while j < len(groups) and j < i + 3:
                        g = groups[j]
                        # Check if this group is part of the same component
                        for elem in g["elements"]:
                            if elem.get("bounds") and current_bounds:
                                for cb in current_bounds:
                                    if _bounds_overlap_horizontally(cb, elem["bounds"]):
                                        merged_group["elements"].extend(g["elements"])
                                        break
                        j += 1
                    
                    merged.append(merged_group)
                    i = j  # Skip merged groups
                    continue
        
        # No merge, just add current group
        merged.append(current)
        i += 1
    
    return merged


def _split_list_items(group: Dict) -> List[Dict]:
    """Split a group containing multiple list items into separate groups"""
    elements = group["elements"]
    
    # Check if any elements are marked as being in a list
    has_list_elements = any(e.get("in_list", False) for e in elements)
    
    if has_list_elements:
        # Use the list detector to properly group items
        list_groups = detect_and_group_list_items(elements)
        
        # Convert to our group format
        result_groups = []
        for lg in list_groups:
            if lg["type"] == "list_item":
                # This is a detected list item
                new_group = {
                    "title": lg["title"],
                    "type": "game_card" if _is_game_item(lg["elements"]) else "list_item",
                    "elements": lg["elements"],
                    "purpose": "game" if _is_game_item(lg["elements"]) else group.get("purpose", "info")
                }
                result_groups.append(new_group)
            else:
                # Non-list elements
                if lg["elements"]:
                    result_groups.append({
                        "title": group.get("title", "Group"),
                        "type": group.get("type", "group"),
                        "elements": lg["elements"],
                        "purpose": group.get("purpose", "info")
                    })
        
        return result_groups if result_groups else [group]
    
    # Fallback to the original logic for non-list items
    # Find all game titles and touch areas
    game_titles = []
    touch_areas = []
    badges = []
    other_elements = []
    
    for elem in elements:
        if elem["type"] == "text":
            # Check if it's a badge
            if elem["label"].upper() in ["NEW!", "HOT!", "5% COINS", "IPL", "LAKDI/GHODHI"]:
                badges.append(elem)
            # Check if it looks like a game title
            elif any(word in elem["label"].lower() for word in ["poker", "rummy", "patti", "skill", "cricket", "opinio", "crash", "call break"]):
                game_titles.append(elem)
            else:
                other_elements.append(elem)
        elif elem.get("action") == "tap":
            touch_areas.append(elem)
        else:
            other_elements.append(elem)
    
    # If we don't have multiple game titles, return as is
    if len(game_titles) <= 1:
        return [group]
    
    # Sort elements by x-coordinate to group them correctly
    all_elements = elements.copy()
    all_elements.sort(key=lambda e: _get_x_center(e.get("bounds", "[0,0][0,0]")))
    
    # Better approach: Group by game titles first
    groups = []
    
    # For each game title, find its associated elements
    for game_title in game_titles:
        title_x = _get_x_center(game_title.get("bounds", "[0,0][0,0]"))
        title_bounds = _parse_bounds(game_title.get("bounds", "[0,0][0,0]"))
        
        game_group = {
            "title": game_title["label"],
            "type": "game_card",
            "elements": [game_title],
            "purpose": group.get("purpose", "game")
        }
        
        # Find the badge above this game title
        for badge in badges:
            badge_x = _get_x_center(badge.get("bounds", "[0,0][0,0]"))
            badge_bounds = _parse_bounds(badge.get("bounds", "[0,0][0,0]"))
            
            # Badge should be above and horizontally aligned
            if (abs(badge_x - title_x) < 100 and 
                badge_bounds[3] < title_bounds[1]):  # Badge bottom < title top
                game_group["elements"].append(badge)
                break
        
        # Find the touch area for this game
        for touch in touch_areas:
            touch_bounds = _parse_bounds(touch.get("bounds", "[0,0][0,0]"))
            
            # Check if touch area encompasses or overlaps with game title
            if (_bounds_overlap_horizontally(game_title.get("bounds"), touch.get("bounds")) and
                touch_bounds[1] <= title_bounds[1] and touch_bounds[3] >= title_bounds[3]):
                game_group["elements"].append(touch)
                break
        
        # Add any other elements that belong to this game
        for elem in other_elements:
            elem_x = _get_x_center(elem.get("bounds", "[0,0][0,0]"))
            if abs(elem_x - title_x) < 100:
                game_group["elements"].append(elem)
        
        groups.append(game_group)
    
    # If we couldn't split properly, return original
    if len(groups) <= 1:
        return [group]
    
    return groups


def _get_x_center(bounds_str: str) -> int:
    """Get the x-coordinate center of bounds"""
    x1, y1, x2, y2 = _parse_bounds(bounds_str)
    return (x1 + x2) // 2


def _is_game_item(elements: List[Dict]) -> bool:
    """Check if elements represent a game item"""
    for elem in elements:
        label = elem.get("label", "").lower()
        if any(game in label for game in ["poker", "rummy", "patti", "skill", "cricket", "opinio", "crash", "call break"]):
            return True
    return False


def _create_flat_list(groups: List[Dict]) -> List[Dict]:
    """Create a flat list of all actionable elements with group context"""
    flat = []
    
    for group in groups:
        for elem in group["elements"]:
            # Only include actionable elements in flat list
            if elem.get("action"):
                flat_elem = {
                    "id": elem["id"],
                    "label": elem["label"],
                    "action": elem["action"],
                    "group": group["title"],
                    "group_purpose": group.get("purpose", "unknown")
                }
                flat.append(flat_elem)
    
    return flat