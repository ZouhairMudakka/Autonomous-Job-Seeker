"""DOM Element Models and Node Structures"""

import asyncio
from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from storage.logs_manager import LogsManager

@dataclass
class DOMBaseNode:
    """Base node type, can be 'element' or 'text'."""
    type: str
    logs_manager: Optional['LogsManager'] = None

@dataclass
class DOMTextNode:
    """Text node containing content."""
    content: str
    type: str = 'text'
    logs_manager: Optional['LogsManager'] = None

@dataclass
class DOMElementNode:
    """Element node with attributes and children."""
    tag: str
    type: str = 'element'
    attributes: Dict[str, str] = field(default_factory=dict)
    children: List['DOMBaseNode'] = field(default_factory=list)
    is_clickable: bool = False
    is_visible: bool = False
    highlight_index: Optional[int] = None
    logs_manager: Optional['LogsManager'] = None

    @classmethod
    async def from_dict(cls, data: Dict, logs_manager: Optional['LogsManager'] = None) -> 'DOMBaseNode':
        """Create a DOM node from a dictionary representation.
        
        Args:
            data: Dictionary containing node data
            logs_manager: Optional LogsManager instance for logging
        """
        node_type = data.get('type')
        
        if logs_manager:
            await logs_manager.debug(f"Creating DOM node of type: {node_type}")
            
        if node_type == 'text':
            if logs_manager:
                await logs_manager.debug(f"Creating text node with content length: {len(data.get('content', ''))}")
            return DOMTextNode(
                content=data.get('content', ''),
                logs_manager=logs_manager
            )
        elif node_type == 'element':
            if logs_manager:
                await logs_manager.debug(f"Creating element node with tag: {data.get('tag', '')}")
            
            children_data = data.get('children', [])
            children_nodes = []
            
            for child_data in children_data:
                child = await cls.from_dict(child_data, logs_manager)
                children_nodes.append(child)
            
            if logs_manager:
                await logs_manager.debug(f"Created element with {len(children_nodes)} children")

            return DOMElementNode(
                tag=data.get('tag', ''),
                attributes=data.get('attributes', {}),
                children=children_nodes,
                is_clickable=data.get('isClickable', False),
                is_visible=data.get('isVisible', False),
                highlight_index=data.get('highlightIndex'),
                logs_manager=logs_manager
            )
        else:
            if logs_manager:
                await logs_manager.warning(f"Unknown node type: {node_type}, falling back to text node")
            return DOMTextNode(content='', logs_manager=logs_manager)

    async def find_clickable_elements(self) -> List['DOMElementNode']:
        """Collect all clickable & visible child elements (including self)."""
        result = []
        
        if self.logs_manager:
            await self.logs_manager.debug(f"Searching for clickable elements in {self.tag if hasattr(self, 'tag') else 'text node'}")
        
        if isinstance(self, DOMElementNode):
            if self.is_clickable and self.is_visible:
                if self.logs_manager:
                    await self.logs_manager.debug(f"Found clickable element: {self.tag} with attributes {self.attributes}")
                result.append(self)

            for child in self.children:
                if isinstance(child, DOMElementNode):
                    child_elements = await child.find_clickable_elements()
                    result.extend(child_elements)

        if self.logs_manager:
            await self.logs_manager.debug(f"Found {len(result)} total clickable elements in subtree")
            
        return result
