"""DOM Element Models and Node Structures"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class DOMBaseNode:
    """Base node type, can be 'element' or 'text'."""
    type: str

@dataclass
class DOMTextNode(DOMBaseNode):
    content: str

@dataclass
class DOMElementNode(DOMBaseNode):
    tag: str
    attributes: Dict[str, str] = field(default_factory=dict)
    children: List[DOMBaseNode] = field(default_factory=list)
    is_clickable: bool = False
    is_visible: bool = False
    highlight_index: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'DOMBaseNode':
        node_type = data.get('type')
        if node_type == 'text':
            return DOMTextNode(
                type='text',
                content=data.get('content', '')
            )
        elif node_type == 'element':
            children_data = data.get('children', [])
            children_nodes = [cls.from_dict(child) for child in children_data]

            return DOMElementNode(
                type='element',
                tag=data.get('tag', ''),
                attributes=data.get('attributes', {}),
                children=children_nodes,
                is_clickable=data.get('isClickable', False),
                is_visible=data.get('isVisible', False),
                highlight_index=data.get('highlightIndex')
            )
        else:
            # Fallback, if unknown type
            return DOMTextNode(type='text', content='')

    def find_clickable_elements(self) -> List['DOMElementNode']:
        """Collect all clickable & visible child elements (including self)."""
        result = []
        if self.is_clickable and self.is_visible:
            result.append(self)

        for child in self.children:
            if isinstance(child, DOMElementNode):
                result.extend(child.find_clickable_elements())

        return result
