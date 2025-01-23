/**
 * DOM Tree Builder and Element Highlighter with In-Viewport Priority
 *
 * - Collects all clickable, visible elements from the DOM.
 * - Determines if they're currently in the viewport (partial overlap is allowed).
 * - Sorts in-viewport first, then offscreen elements, up to a maximum highlight limit.
 * - Builds a JSON tree structure, labeling highlighted elements with highlightIndex.
 *
 * NOTE: You can call this each time you want to refresh or update highlights
 *       (e.g. after scrolling).
 */

// Add at the top of the file
function clearHighlightContainer() {
  const container = document.getElementById("dom-highlight-container");
  if (container) container.remove();
}

// Basic check for clickable
function isClickableElement(el) {
    const tag = el.tagName.toLowerCase();
    if (["a", "button"].includes(tag)) return true;
    if (el.getAttribute("role") === "button") return true;
    if (el.hasAttribute("onclick")) return true;
    // Expand logic as needed
    return false;
  }
  
  // Basic check for visible
  function isVisibleElement(el) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return false;
  
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || parseFloat(style.opacity) === 0) {
      return false;
    }
    return true;
  }
  
  // Check if element is at least partially in the viewport
  function isInViewport(el) {
    const rect = el.getBoundingClientRect();
  
    // Consider partial overlap with viewport
    const vpWidth = window.innerWidth;
    const vpHeight = window.innerHeight;
  
    const inHorizView = (rect.left < vpWidth) && ((rect.left + rect.width) > 0);
    const inVertView = (rect.top < vpHeight) && ((rect.top + rect.height) > 0);
  
    return inHorizView && inVertView;
  }
  
  function highlightElement(el, highlightIndex) {
    let container = document.getElementById("dom-highlight-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "dom-highlight-container";
      container.style.position = "absolute";
      container.style.top = "0";
      container.style.left = "0";
      container.style.width = "100%";
      container.style.height = "100%";
      container.style.pointerEvents = "none";
      container.style.zIndex = "2147483647";
      document.body.appendChild(container);
    }
  
    const colors = [
      "#FF0000","#00FF00","#0000FF","#FFA500","#800080",
      "#008080","#FF69B4","#4B0082","#FF4500","#2E8B57",
      "#DC143C","#4682B4","#FF1493","#8B0000","#B8860B",
      "#9ACD32","#FF8C00","#1E90FF","#FF00FF","#ADFF2F",
      "#CD5C5C","#20B2AA","#FF6347","#9932CC","#FFB6C1"
    ];
    const baseColor = colors[highlightIndex % colors.length] || "#FF0000";
    const backgroundColor = baseColor + "33"; // ~20% alpha
  
    const rect = el.getBoundingClientRect();
    const overlay = document.createElement("div");
    overlay.style.position = "absolute";
    overlay.style.border = `2px solid ${baseColor}`;
    overlay.style.backgroundColor = backgroundColor;
    overlay.style.pointerEvents = "none";
  
    overlay.style.left = (rect.left + window.scrollX) + "px";
    overlay.style.top = (rect.top + window.scrollY) + "px";
    overlay.style.width = rect.width + "px";
    overlay.style.height = rect.height + "px";
  
    // Create label
    const label = document.createElement("div");
    label.textContent = highlightIndex;
    label.style.position = "absolute";
    label.style.background = baseColor;
    label.style.color = "#fff";
    label.style.fontSize = "12px";
    label.style.padding = "2px 4px";
    label.style.pointerEvents = "none";
  
    label.style.left = (rect.left + window.scrollX) + "px";
    label.style.top = (rect.top + window.scrollY) + "px";
    label.style.zIndex = "2147483647";
  
    container.appendChild(overlay);
    container.appendChild(label);
  }
  
  /**
   * Build the DOM tree while optionally highlighting up to `maxHighlights` clickable elements,
   * prioritizing those in the visible viewport first.
   */
  function buildDomTree(root, doHighlight, maxHighlight) {
    // Clear existing highlights
    clearHighlightContainer();
  
    let clickableElements = [];
  
    function traverse(node) {
      if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent.trim();
        if (!text) return null;
        return {
          type: "text",
          content: text
        };
      }
  
      if (node.nodeType === Node.ELEMENT_NODE) {
        const tag = node.tagName.toLowerCase();
        const visible = isVisibleElement(node);
        const clickable = isClickableElement(node);
        const inViewport = visible && isInViewport(node);
  
        const elementData = {
          type: "element",
          tag: tag,
          attributes: {},
          children: [],
          isClickable: clickable,
          isVisible: visible,
          isInViewport: inViewport // Additional property for sorting
        };
  
        // Add attributes
        for (const attr of node.attributes) {
          elementData.attributes[attr.name] = attr.value;
        }
  
        // Recurse for children
        for (const child of node.childNodes) {
          const childData = traverse(child);
          if (childData) {
            elementData.children.push(childData);
          }
        }
  
        // Collect clickable elements for later highlight
        if (clickable && visible) {
          clickableElements.push({
            node,
            elementData
          });
        }
  
        return elementData;
      }
      return null;
    }
  
    const tree = traverse(root);
  
    // Now we handle highlighting if doHighlight is true
    if (doHighlight) {
      // Sort clickableElements:
      // 1. in-viewport first
      // 2. then out-of-viewport
      clickableElements.sort((a, b) => {
        const aInView = a.elementData.isInViewport ? 1 : 0;
        const bInView = b.elementData.isInViewport ? 1 : 0;
        // Descending: in-viewport (1) before out-of-viewport (0)
        if (aInView !== bInView) return bInView - aInView;
  
        // If both are same in-viewport status, let's sort by top offset
        const rectA = a.node.getBoundingClientRect();
        const rectB = b.node.getBoundingClientRect();
        return rectA.top - rectB.top;
      });
  
      let highlightCount = 0;
      for (const { node, elementData } of clickableElements) {
        if (highlightCount >= maxHighlight) break;
        highlightElement(node, highlightCount);
        elementData.highlightIndex = highlightCount;
        highlightCount++;
      }
    }
  
    return tree;
  }
  