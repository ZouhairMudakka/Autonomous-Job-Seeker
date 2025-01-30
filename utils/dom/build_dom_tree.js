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

// Logging bridge function that will be injected by Python
let logToPython = (level, message) => {
    // Default implementation logs to console
    // This will be overridden by Python code
    console[level](`[DOM Tree] ${message}`);
};

// Logging helper functions
function logInfo(message) {
    logToPython('info', message);
    // Keep console.log for immediate browser feedback
    console.log(`[DOM Tree] ${message}`);
}

function logError(message, error) {
    const errorMsg = error ? `${message}: ${error.message || error}` : message;
    logToPython('error', errorMsg);
    // Keep console.error for immediate browser feedback
    console.error(`[DOM Tree] ${errorMsg}`);
}

function logDebug(message) {
    logToPython('debug', message);
    // Keep console.debug for immediate browser feedback
    console.debug(`[DOM Tree] ${message}`);
}

function logWarning(message) {
    logToPython('warning', message);
    // Keep console.warn for immediate browser feedback
    console.warn(`[DOM Tree] ${message}`);
}

// Add at the top of the file
function clearHighlightContainer() {
  const container = document.getElementById("dom-highlight-container");
  if (container) container.remove();
}

// Basic check for clickable
function isClickableElement(el) {
    try {
        const tag = el.tagName.toLowerCase();
        
        // Common clickable elements
        if (["a", "button", "input", "select", "textarea"].includes(tag)) return true;
        
        // Elements with click-related attributes
        if (el.hasAttribute("onclick") || 
            el.hasAttribute("ng-click") || 
            el.hasAttribute("@click") ||
            el.hasAttribute("v-on:click")) return true;
            
        // Elements with interactive roles
        const interactiveRoles = [
            "button", "link", "menuitem", "tab", "menuitemcheckbox",
            "menuitemradio", "radio", "switch", "option"
        ];
        const role = el.getAttribute("role");
        if (role && interactiveRoles.includes(role)) return true;
        
        // Check for event listeners (if possible)
        const style = window.getComputedStyle(el);
        if (style.cursor === "pointer") return true;
        
        // Check for specific classes that might indicate clickability
        const classNames = el.className.split(" ");
        const clickableClasses = ["btn", "button", "clickable", "link"];
        if (classNames.some(cls => clickableClasses.some(clickable => cls.toLowerCase().includes(clickable)))) {
            return true;
        }
        
        // Input types that are clickable
        if (tag === "input") {
            const inputType = el.getAttribute("type");
            const clickableTypes = ["submit", "button", "radio", "checkbox", "reset", "file"];
            if (clickableTypes.includes(inputType)) return true;
        }

        return false;
    } catch (error) {
        logError("Error in isClickableElement", error);
        return false;
    }
}
  
// Basic check for visible
function isVisibleElement(el) {
    try {
        // Get element's bounding box
        const rect = el.getBoundingClientRect();
        
        // Check for zero dimensions
        if (rect.width === 0 || rect.height === 0) return false;
        
        // Get computed style
        const style = window.getComputedStyle(el);
        
        // Check basic visibility properties
        if (style.display === "none" || 
            style.visibility === "hidden" || 
            style.visibility === "collapse" || 
            parseFloat(style.opacity) === 0) {
            return false;
        }
        
        // Check if element is detached from DOM
        if (!document.body.contains(el)) return false;
        
        // Check if any parent element makes this invisible
        let parent = el.parentElement;
        while (parent && parent !== document.body) {
            const parentStyle = window.getComputedStyle(parent);
            if (parentStyle.display === "none" || 
                parentStyle.visibility === "hidden" || 
                parseFloat(parentStyle.opacity) === 0) {
                return false;
            }
            parent = parent.parentElement;
        }
        
        // Check if element is off-screen (far outside viewport)
        const vpWidth = window.innerWidth;
        const vpHeight = window.innerHeight;
        const offset = 10000; // reasonable offset for elements that might be scrolled into view
        
        if (rect.right < -offset || 
            rect.bottom < -offset || 
            rect.left > vpWidth + offset || 
            rect.top > vpHeight + offset) {
            return false;
        }
        
        return true;
    } catch (error) {
        logError("Error in isVisibleElement", error);
        return false;
    }
}

// Cache viewport dimensions and update on resize
let vpWidth = window.innerWidth;
let vpHeight = window.innerHeight;

window.addEventListener('resize', () => {
    vpWidth = window.innerWidth;
    vpHeight = window.innerHeight;
});

function isInViewport(el) {
    try {
        const rect = el.getBoundingClientRect();
        
        // Consider partial overlap with viewport
        // Add small margin to account for elements right at the edge
        const margin = 2; // 2px margin
        
        const inHorizView = (
            (rect.left < vpWidth + margin) && 
            ((rect.left + rect.width) > -margin)
        );
        
        const inVertView = (
            (rect.top < vpHeight + margin) && 
            ((rect.top + rect.height) > -margin)
        );
        
        // Check if element has meaningful size
        const hasSize = (rect.width >= 1 && rect.height >= 1);
        
        // Check if element is reasonably positioned
        const isReasonablyPositioned = (
            Math.abs(rect.left) < 10000 && 
            Math.abs(rect.top) < 10000
        );
        
        return inHorizView && inVertView && hasSize && isReasonablyPositioned;
    } catch (error) {
        logError("Error in isInViewport", error);
        return false;
    }
}

// Predefined colors array - moved outside for better performance
const HIGHLIGHT_COLORS = [
    "#FF0000","#00FF00","#0000FF","#FFA500","#800080",
    "#008080","#FF69B4","#4B0082","#FF4500","#2E8B57",
    "#DC143C","#4682B4","#FF1493","#8B0000","#B8860B",
    "#9ACD32","#FF8C00","#1E90FF","#FF00FF","#ADFF2F",
    "#CD5C5C","#20B2AA","#FF6347","#9932CC","#FFB6C1"
];

function highlightElement(el, highlightIndex) {
    try {
        // Get or create container
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

        // Get color and calculate background
        const baseColor = HIGHLIGHT_COLORS[highlightIndex % HIGHLIGHT_COLORS.length] || "#FF0000";
        const backgroundColor = baseColor + "33"; // ~20% alpha

        // Cache scroll positions and element rect
        const rect = el.getBoundingClientRect();
        const scrollX = window.scrollX;
        const scrollY = window.scrollY;

        // Create and style overlay
        const overlay = document.createElement("div");
        overlay.style.position = "absolute";
        overlay.style.border = `2px solid ${baseColor}`;
        overlay.style.backgroundColor = backgroundColor;
        overlay.style.pointerEvents = "none";
        overlay.style.left = (rect.left + scrollX) + "px";
        overlay.style.top = (rect.top + scrollY) + "px";
        overlay.style.width = rect.width + "px";
        overlay.style.height = rect.height + "px";

        // Create and style label
        const label = document.createElement("div");
        label.textContent = highlightIndex;
        label.style.position = "absolute";
        label.style.background = baseColor;
        label.style.color = "#fff";
        label.style.fontSize = "12px";
        label.style.padding = "2px 4px";
        label.style.pointerEvents = "none";
        label.style.left = (rect.left + scrollX) + "px";
        label.style.top = (rect.top + scrollY) + "px";
        label.style.zIndex = "2147483647";

        // Batch DOM operations using fragment
        const fragment = document.createDocumentFragment();
        fragment.appendChild(overlay);
        fragment.appendChild(label);
        container.appendChild(fragment);

    } catch (error) {
        logError("Error in highlightElement", error);
    }
}

/**
 * Build the DOM tree while optionally highlighting up to `maxHighlights` clickable elements,
 * prioritizing those in the visible viewport first.
 */
function buildDomTree(root, doHighlight, maxHighlight) {
  logInfo(`Starting DOM tree build with highlight=${doHighlight}, maxHighlight=${maxHighlight}`);
  
  // Clear existing highlights
  clearHighlightContainer();
  logDebug("Cleared existing highlight container");

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
        isInViewport: inViewport
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
  logInfo(`Found ${clickableElements.length} clickable and visible elements`);

  // Now we handle highlighting if doHighlight is true
  if (doHighlight) {
    logDebug("Starting element highlighting");
    
    // Sort clickableElements
    clickableElements.sort((a, b) => {
      const aInView = a.elementData.isInViewport ? 1 : 0;
      const bInView = b.elementData.isInViewport ? 1 : 0;
      if (aInView !== bInView) return bInView - aInView;

      const rectA = a.node.getBoundingClientRect();
      const rectB = b.node.getBoundingClientRect();
      return rectA.top - rectB.top;
    });

    let highlightCount = 0;
    const inViewportCount = clickableElements.filter(el => el.elementData.isInViewport).length;
    logInfo(`Found ${inViewportCount} elements in viewport out of ${clickableElements.length} total clickable`);

    for (const { node, elementData } of clickableElements) {
      if (highlightCount >= maxHighlight) {
        logDebug(`Reached maximum highlight limit of ${maxHighlight}`);
        break;
      }
      highlightElement(node, highlightCount);
      elementData.highlightIndex = highlightCount;
      highlightCount++;
    }
    
    logInfo(`Highlighted ${highlightCount} elements`);
  }

  return tree;
}
  