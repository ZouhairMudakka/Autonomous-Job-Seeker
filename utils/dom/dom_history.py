"""DOM History Tracking and Change Detection"""

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from .dom_models import DOMElementNode, DOMBaseNode, DOMTextNode

@dataclass
class DOMSnapshot:
    timestamp: str
    hash_value: str
    tree: DOMElementNode

class DomHistory:
    def __init__(self, max_snapshots: int = 5):
        self.snapshots: List[DOMSnapshot] = []
        self.max_snapshots = max_snapshots

    def add_snapshot(self, tree: DOMElementNode):
        """Add new DOM snapshot with timestamp."""
        snapshot_hash = self._calculate_hash(tree)
        snapshot = DOMSnapshot(
            timestamp=datetime.now().isoformat(),
            hash_value=snapshot_hash,
            tree=tree
        )
        self.snapshots.append(snapshot)
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots.pop(0)  # Remove oldest

    def _calculate_hash(self, tree: DOMElementNode) -> str:
        """Calculate hash of the entire DOM tree for change detection."""
        # Convert tree to a stable JSON
        tree_dict = self._serialize_tree(tree)
        tree_json = json.dumps(tree_dict, sort_keys=True)
        return hashlib.sha256(tree_json.encode()).hexdigest()

    def _serialize_tree(self, node: DOMBaseNode) -> Dict[str, Any]:
        """Turn the DOM node into a Python dict for hashing."""
        if isinstance(node, DOMTextNode):
            return {
                'type': 'text',
                'content': node.content
            }
        elif isinstance(node, DOMElementNode):
            return {
                'type': 'element',
                'tag': node.tag,
                'attributes': node.attributes,
                'is_clickable': node.is_clickable,
                'is_visible': node.is_visible,
                'highlight_index': node.highlight_index,
                'children': [self._serialize_tree(child) for child in node.children]
            }
        return {}

    def compare_latest_two(self) -> bool:
        """Return True if the latest two snapshots differ."""
        if len(self.snapshots) < 2:
            return False
        return self.snapshots[-1].hash_value != self.snapshots[-2].hash_value
