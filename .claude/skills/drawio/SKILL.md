---
name: drawio
description: "REQUIRED: Invoke this skill FIRST before using execute_script tool. Draw diagrams in Draw.io (flowcharts, architecture, mind maps, UML, etc). Use when user asks to draw, create diagrams, visualize flows, or design architecture."
allowed-tools:
  - mcp__drawio-controller__execute_script
---

# Draw.io Diagramming Skill

## When to Use
- User asks to "draw", "create diagram", "visualize", "架构图", "流程图"
- Flowcharts, architecture diagrams, mind maps, UML, ER diagrams
- Any visual representation of structure or process

## Critical Guidelines

### Use Native mxGraph API, NOT AI_HLP
The `AI_HLP` wrapper has layout issues. Always use native mxGraph API directly:

```javascript
const graph = ui.editor.graph;
const parent = graph.getDefaultParent();
const model = graph.getModel();

model.beginUpdate();
try {
    // Create vertices and edges here
} finally {
    model.endUpdate();
}
```

### Required Style Base
All shapes MUST include this base style for proper anchor points:
```
whiteSpace=wrap;html=1;
```

### Manual Positioning Over Auto-Layout
Position nodes manually with explicit x/y coordinates. Auto-layout often produces poor results.

## Core Patterns

### Create a Vertex
```javascript
graph.insertVertex(parent, 'unique_id', 'Label Text', x, y, width, height,
    'whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;rounded=1;');
```

### Create an Edge with Proper Port Constraints

**CRITICAL**: Always specify exitX/exitY/entryX/entryY based on node positions to avoid messy orthogonal routing.

```javascript
// Helper function to determine edge style
function getEdgeStyle(source, target) {
    const s = source.geometry;
    const t = target.geometry;
    const dx = t.x - (s.x + s.width);
    const dy = t.y - (s.y + s.height);
    
    if (Math.abs(dx) > Math.abs(dy)) {
        // Horizontal: exit right, enter left
        return 'edgeStyle=orthogonalEdgeStyle;rounded=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;';
    } else {
        // Vertical: exit bottom, enter top
        return 'edgeStyle=orthogonalEdgeStyle;rounded=1;exitX=0.5;exitY=1;entryX=0.5;entryY=0;';
    }
}

// Usage
graph.insertEdge(parent, null, 'label', sourceVertex, targetVertex, getEdgeStyle(sourceVertex, targetVertex));
```

**Edge Style Quick Reference:**
| Direction | exitX | exitY | entryX | entryY |
|-----------|-------|-------|--------|--------|
| Left to Right | 1 | 0.5 | 0 | 0.5 |
| Right to Left | 0 | 0.5 | 1 | 0.5 |
| Top to Bottom | 0.5 | 1 | 0.5 | 0 |
| Bottom to Top | 0.5 | 0 | 0.5 | 1 |

### Page Management (Dialog-Free)
```javascript
// Create new page without dialog
const page = ui.insertPage();
ui.editor.graph.model.execute(new RenamePage(ui, page, 'Page Name'));

// Switch to existing page
const existing = ui.pages.find(p => p.getName() === 'Page Name');
if (existing) ui.selectPage(existing);
```

## Templates

See `templates/` directory for ready-to-use diagram templates:
- `rpc-flow.js` - RPC data flow with serialization
- `microservice.js` - Microservice architecture
- `database.js` - Database schema diagrams
- `flowchart.js` - Generic flowchart

## Style Reference

See `reference/style-guide.md` for:
- Color palettes
- Shape styles
- Edge styles
- Typography
