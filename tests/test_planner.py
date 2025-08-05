import pytest
from src.planner import choose_node


def test_choose_node_with_text():
    """Test that planner picks first clickable node with text"""
    nodes = [
        {"resource-id": "id1", "text": "", "content-desc": "desc1", "clickable": True},
        {"resource-id": "id2", "text": "Click Me", "content-desc": "", "clickable": True},
        {"resource-id": "id3", "text": "Another", "content-desc": "", "clickable": True},
    ]
    
    chosen = choose_node(nodes)
    assert chosen is not None
    assert chosen["text"] == "Click Me"
    assert chosen["resource-id"] == "id2"


def test_choose_node_no_text_fallback():
    """Test fallback to clickable node with resource-id when no text available"""
    nodes = [
        {"resource-id": "", "text": "", "content-desc": "", "clickable": False},
        {"resource-id": "id1", "text": "", "content-desc": "", "clickable": True},
        {"resource-id": "", "text": "", "content-desc": "desc", "clickable": True},
    ]
    
    chosen = choose_node(nodes)
    assert chosen is not None
    assert chosen["resource-id"] == "id1"


def test_choose_node_no_clickable():
    """Test returns None when no clickable nodes"""
    nodes = [
        {"resource-id": "id1", "text": "text", "content-desc": "", "clickable": False},
        {"resource-id": "id2", "text": "text2", "content-desc": "", "clickable": False},
    ]
    
    chosen = choose_node(nodes)
    assert chosen is None


def test_choose_node_empty_list():
    """Test returns None for empty node list"""
    chosen = choose_node([])
    assert chosen is None