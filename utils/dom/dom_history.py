"""DOM History Tracking and Change Detection"""

import json
import hashlib
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from storage.logs_manager import LogsManager
from .dom_models import DOMElementNode, DOMBaseNode, DOMTextNode

@dataclass
class DOMSnapshot:
    timestamp: str
    hash_value: str
    tree: DOMElementNode

class DomHistory:
    def __init__(self, max_snapshots: int = 5, logs_manager: Optional[LogsManager] = None):
        self.snapshots: List[DOMSnapshot] = []
        self.max_snapshots = max_snapshots
        self.logs_manager = logs_manager
        
    async def initialize(self, logs_manager: LogsManager):
        """Initialize with a logs manager if not provided in constructor."""
        self.logs_manager = logs_manager
        await self.logs_manager.info("DOM History tracking initialized")

    async def add_snapshot(self, tree: DOMElementNode):
        """Add new DOM snapshot with timestamp."""
        if self.logs_manager:
            await self.logs_manager.debug("Creating new DOM snapshot...")
            
        snapshot_hash = await self._calculate_hash(tree)
        snapshot = DOMSnapshot(
            timestamp=datetime.now().isoformat(),
            hash_value=snapshot_hash,
            tree=tree
        )
        self.snapshots.append(snapshot)
        
        if len(self.snapshots) > self.max_snapshots:
            if self.logs_manager:
                await self.logs_manager.debug("Removing oldest snapshot to maintain max size")
            self.snapshots.pop(0)  # Remove oldest
            
        if self.logs_manager:
            await self.logs_manager.info(f"Added new DOM snapshot with hash: {snapshot_hash[:8]}...")

    async def _calculate_hash(self, tree: DOMElementNode) -> str:
        """Calculate hash of the entire DOM tree for change detection."""
        try:
            # Convert tree to a stable JSON
            tree_dict = await self._serialize_tree(tree)
            tree_json = json.dumps(tree_dict, sort_keys=True)
            hash_value = hashlib.sha256(tree_json.encode()).hexdigest()
            
            if self.logs_manager:
                await self.logs_manager.debug(f"Calculated DOM tree hash: {hash_value[:8]}...")
            return hash_value
            
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to calculate DOM tree hash: {str(e)}")
            raise

    async def _serialize_tree(self, node: DOMBaseNode) -> Dict[str, Any]:
        """Turn the DOM node into a Python dict for hashing."""
        try:
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
                    'children': [await self._serialize_tree(child) for child in node.children]
                }
            
            if self.logs_manager:
                await self.logs_manager.warning(f"Unknown node type encountered: {type(node)}")
            return {}
            
        except Exception as e:
            if self.logs_manager:
                await self.logs_manager.error(f"Failed to serialize DOM tree node: {str(e)}")
            raise

    async def compare_latest_two(self) -> bool:
        """Return True if the latest two snapshots differ."""
        if len(self.snapshots) < 2:
            if self.logs_manager:
                await self.logs_manager.debug("Not enough snapshots for comparison")
            return False
            
        are_different = self.snapshots[-1].hash_value != self.snapshots[-2].hash_value
        
        if self.logs_manager:
            if are_different:
                await self.logs_manager.info("DOM change detected between latest snapshots")
            else:
                await self.logs_manager.debug("No changes detected between latest snapshots")
                
        return are_different
