import subprocess
import os
from pathlib import Path
import xml.etree.ElementTree as etree
from typing import Dict, Optional, Tuple
import sys


def check_adb_connection():
    """Check if ADB is connected to a device"""
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.strip().split('\n')
        # First line is "List of devices attached"
        if len(lines) > 1 and lines[1].strip():
            return True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def dump_ui() -> str:
    """
    Dumps the accessibility tree XML from Android device.
    Saves to window_dump.xml in repo root.
    Returns the path to the saved file.
    """
    # Check if ADB is available
    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True)
    except FileNotFoundError:
        raise RuntimeError("ADB not found. Please install Android SDK Platform Tools.")
    
    # Check if device is connected
    if not check_adb_connection():
        raise RuntimeError("No Android device connected. Please connect a device and ensure ADB debugging is enabled.")
    
    # Dump UI hierarchy to device
    try:
        result = subprocess.run(
            ["adb", "shell", "uiautomator", "dump"],
            capture_output=True,
            text=True,
            check=False  # Don't raise on non-zero exit
        )
        
        if result.returncode != 0:
            # Some devices output to stderr even on success
            if "dumped to" in result.stderr or "dumped to" in result.stdout:
                # Success despite non-zero exit code
                pass
            else:
                error_msg = result.stderr or result.stdout
                raise RuntimeError(f"Failed to dump UI: {error_msg}")
                
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to dump UI: {e}")
    
    # Pull the file from device
    local_path = Path.cwd() / "window_dump.xml"
    
    # Try different possible locations on the device
    pulled = False
    for device_path in ["/sdcard/window_dump.xml", "/data/local/tmp/window_dump.xml"]:
        try:
            result = subprocess.run(
                ["adb", "pull", device_path, str(local_path)],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                pulled = True
                break
        except:
            continue
    
    if not pulled:
        raise RuntimeError("Failed to pull window_dump.xml from device. The UI dump may have failed.")
    
    # Verify the file exists and is valid XML
    if not local_path.exists():
        raise RuntimeError(f"window_dump.xml not found at {local_path}")
    
    try:
        # Quick XML validation
        with open(local_path, 'r', encoding='utf-8') as f:
            etree.parse(f)
    except Exception as e:
        raise RuntimeError(f"Invalid XML in window_dump.xml: {e}")
    
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
    
    # Find matching nodes
    found_node = None
    for node in root.iter('node'):
        matches = True
        
        if selector_dict.get("resource-id"):
            if node.get("resource-id") != selector_dict["resource-id"]:
                matches = False
        
        if selector_dict.get("text"):
            if node.get("text") != selector_dict["text"]:
                matches = False
                
        if selector_dict.get("content-desc"):
            if node.get("content-desc") != selector_dict["content-desc"]:
                matches = False
        
        if matches:
            found_node = node
            break
    
    if found_node is None:
        raise ValueError(f"No node found matching selector: {selector_dict}")
    
    # Get bounds from node
    bounds = found_node.get("bounds")
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