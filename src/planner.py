from typing import List, Dict, Any, Optional
import os
import json
from pathlib import Path


def choose_node(nodes: List[Dict[str, Any]], user_goal: str = None) -> Optional[Dict[str, str]]:
    """
    Choose which node to interact with based on user goal.
    Falls back to stub logic if LLM is not configured.
    
    Args:
        nodes: List of UI nodes from parser
        user_goal: What the user wants to achieve (optional)
    
    Returns:
        Selector dict with keys matching node identifiers
        (resource-id, text, content-desc).
    """
    # Check if LLM is configured (either simple API key or Vertex AI)
    use_llm = os.getenv("GOOGLE_AI_API_KEY") is not None or os.getenv("VERTEX_AI_PROJECT_ID") is not None
    
    if use_llm and user_goal:
        try:
            return choose_node_with_llm(nodes, user_goal)
        except Exception as e:
            print(f"LLM failed, falling back to stub: {e}")
    
    # Original stub logic
    return choose_node_stub(nodes)


def choose_node_stub(nodes: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """
    Original stub: Pick the first clickable node that has non-empty text.
    """
    for node in nodes:
        # Only consider clickable nodes
        if not node.get("clickable", False):
            continue
            
        # Pick first node with non-empty text
        if node.get("text"):
            return {
                "resource-id": node.get("resource-id", ""),
                "text": node.get("text", ""),
                "content-desc": node.get("content-desc", "")
            }
    
    # Fallback: pick first clickable node with any identifier
    for node in nodes:
        if not node.get("clickable", False):
            continue
            
        if node.get("resource-id") or node.get("content-desc"):
            return {
                "resource-id": node.get("resource-id", ""),
                "text": node.get("text", ""),
                "content-desc": node.get("content-desc", "")
            }
    
    return None


def choose_node_with_llm(nodes: List[Dict[str, Any]], user_goal: str) -> Optional[Dict[str, str]]:
    """
    Use LLM to intelligently choose which node to interact with.
    """
    # Try simple API key method first
    if os.getenv("GOOGLE_AI_API_KEY"):
        from .llm_client_simple import get_simple_llm_client as get_llm_client
    else:
        from .llm_client import get_llm_client
    
    from .parser import parse_for_llm
    
    # Get the latest screen dump file
    xml_path = Path.cwd() / "window_dump.xml"
    if not xml_path.exists():
        raise FileNotFoundError("window_dump.xml not found")
    
    # Parse to LLM format
    llm_nodes = parse_for_llm(str(xml_path))
    
    # Create screen summary
    screen_dump = {
        "screen_elements": llm_nodes,
        "total_elements": len(llm_nodes),
        "clickable_elements": sum(1 for n in llm_nodes if n["clickable"]),
        "element_types": {}
    }
    
    # Count element types
    for node in llm_nodes:
        elem_type = node["type"]
        screen_dump["element_types"][elem_type] = screen_dump["element_types"].get(elem_type, 0) + 1
    
    # Get LLM decision
    llm = get_llm_client()
    result = llm.analyze_screen(screen_dump, user_goal)
    
    # Find the selected element
    element_index = result["element_index"]
    if 0 <= element_index < len(llm_nodes):
        selected_node = llm_nodes[element_index]
        identifiers = selected_node["identifiers"]
        
        # Log the decision
        print(f"\nLLM Decision:")
        print(f"- Action: {result['action']}")
        print(f"- Element: {selected_node['label']} (index {element_index})")
        print(f"- Reason: {result['reason']}")
        print(f"- Confidence: {result['confidence']}")
        
        return {
            "resource-id": identifiers["resource_id"],
            "text": identifiers["text"],
            "content-desc": identifiers["content_desc"]
        }
    else:
        raise ValueError(f"Invalid element index {element_index} from LLM")


def analyze_screen_for_goal(user_goal: str) -> Dict[str, Any]:
    """
    Analyze current screen and determine action for a specific goal.
    
    Args:
        user_goal: What the user wants to achieve
        
    Returns:
        Dict with action details and selected element
    """
    # Try simple API key method first
    if os.getenv("GOOGLE_AI_API_KEY"):
        from .llm_client_simple import get_simple_llm_client as get_llm_client
    else:
        from .llm_client import get_llm_client
    
    from .parser import parse_for_llm
    
    # Get the latest screen dump
    xml_path = Path.cwd() / "window_dump.xml"
    if not xml_path.exists():
        raise FileNotFoundError("Run 'dump' command first to capture screen")
    
    # Parse to LLM format
    nodes = parse_for_llm(str(xml_path))
    
    # Create screen summary
    screen_dump = {
        "screen_elements": nodes,
        "total_elements": len(nodes),
        "clickable_elements": sum(1 for n in nodes if n["clickable"]),
        "element_types": {}
    }
    
    # Count element types
    for node in nodes:
        elem_type = node["type"]
        screen_dump["element_types"][elem_type] = screen_dump["element_types"].get(elem_type, 0) + 1
    
    # Get LLM analysis
    llm = get_llm_client()
    result = llm.analyze_screen(screen_dump, user_goal)
    
    # Add element details to result
    if 0 <= result["element_index"] < len(nodes):
        result["element"] = nodes[result["element_index"]]
    
    return result