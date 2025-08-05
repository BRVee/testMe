import subprocess
import os
from pathlib import Path
from lxml import etree
from typing import Dict, Optional, Tuple


def dump_ui() -> str:
    """
    Dumps the accessibility tree XML from Android device.
    Saves to window_dump.xml in repo root.
    Returns the path to the saved file.
    """
    # Dump UI hierarchy to device
    subprocess.run(
        ["adb", "shell", "uiautomator", "dump"],
        check=True,
        capture_output=True,
        text=True
    )
    
    # Pull the file from device
    local_path = Path.cwd() / "window_dump.xml"
    subprocess.run(
        ["adb", "pull", "/sdcard/window_dump.xml", str(local_path)],
        check=True,
        capture_output=True,
        text=True
    )
    
    return str(local_path)


def tap_node(selector_dict: Dict[str, str]) -> None:
    """
    Taps a node based on selector (resource-id, text, or content-desc).
    First dumps fresh UI to resolve selector to bounds.
    """
    # Get fresh dump
    xml_path = dump_ui()
    
    # Parse XML to find node
    tree = etree.parse(xml_path)
    root = tree.getroot()
    
    # Build XPath query
    conditions = []
    if selector_dict.get("resource-id"):
        conditions.append(f'@resource-id="{selector_dict["resource-id"]}"')
    if selector_dict.get("text"):
        conditions.append(f'@text="{selector_dict["text"]}"')
    if selector_dict.get("content-desc"):
        conditions.append(f'@content-desc="{selector_dict["content-desc"]}"')
    
    if not conditions:
        raise ValueError("No selector criteria provided")
    
    xpath = f"//node[{' and '.join(conditions)}]"
    nodes = root.xpath(xpath)
    
    if not nodes:
        raise ValueError(f"No node found matching selector: {selector_dict}")
    
    # Get bounds from first matching node
    node = nodes[0]
    bounds = node.get("bounds")
    if not bounds:
        raise ValueError("Node has no bounds attribute")
    
    # Parse bounds: [x1,y1][x2,y2]
    x1, y1, x2, y2 = _parse_bounds(bounds)
    
    # Calculate center point
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    
    # Perform tap
    subprocess.run(
        ["adb", "shell", "input", "tap", str(center_x), str(center_y)],
        check=True,
        capture_output=True,
        text=True
    )
    

def _parse_bounds(bounds_str: str) -> Tuple[int, int, int, int]:
    """Parse bounds string '[x1,y1][x2,y2]' into tuple of ints."""
    import re
    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if not match:
        raise ValueError(f"Invalid bounds format: {bounds_str}")
    return tuple(map(int, match.groups()))