import React, { useRef, useState } from 'react';
import { ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, ViewportPortal, useReactFlow, applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react';
import { createDrawing, drawingPath, drawingBounds, whiteboardNodeTypes } from './WhiteboardNodes';
import { hitDrawings } from './whiteboardHitTest';

const Canvas = ({ history, tool, ink, width, busy, change, remove, open, canvasRef, flowRef, onDrawing }) => {
  const flow = useReactFlow(), gesture = useRef(null), hitContext = useRef(null);
  const [points, setPoints] = useState([]);
  const point = event => { const p = flow.screenToFlowPosition({ x: event.clientX, y: event.clientY }); return [p.x, p.y]; };
  const erase = event => {
    // ReactFlow disables node pointer-events in drawing mode. Hit-test the vector
    // outline instead of relying on the DOM target, respecting viewport zoom/pan.
    if (!hitContext.current) hitContext.current = document.createElement('canvas').getContext('2d');
    const hits = hitDrawings(canvasRef.current, hitContext.current, event, gesture.current.lastErase);
    gesture.current.lastErase = [event.clientX, event.clientY];
    if (hits.length) {
      if (!gesture.current.erased) { history.checkpoint(); gesture.current.erased = true; }
      hits.forEach(id => remove(id, false));
    }
  };
  const start = event => {
    if (busy || tool === 'select' || !event.isPrimary || event.button !== 0 || event.target.closest('.react-flow__controls, .react-flow__minimap, .react-flow__attribution')) return;
    event.preventDefault(); event.stopPropagation();
    event.currentTarget.focus({ preventScroll: true });
    event.currentTarget.setPointerCapture(event.pointerId);
    gesture.current = { id: event.pointerId, points: [point(event)] };
    onDrawing(true);
    if (tool === 'eraser') erase(event); else setPoints(gesture.current.points);
  };
  const move = event => {
    if (!gesture.current || gesture.current.id !== event.pointerId) return;
    event.preventDefault(); event.stopPropagation();
    if (tool === 'eraser') { erase(event); return; }
    const next = point(event), list = gesture.current.points, last = list.at(-1);
    if (list.length < 2000 && Math.hypot(next[0] - last[0], next[1] - last[1]) >= 0.8) {
      gesture.current.points = [...list, next]; setPoints(gesture.current.points);
    }
  };
  const end = (event, cancelled = false) => {
    if (!gesture.current || gesture.current.id !== event.pointerId) return;
    event.preventDefault(); event.stopPropagation();
    if (!cancelled && tool === 'pen') {
      const drawing = createDrawing(gesture.current.points, ink, width);
      history.update(state => ({ ...state, nodes: [...state.nodes, drawing] }));
    }
    gesture.current = null; setPoints([]); onDrawing(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const nodes = history.nodes.map(node => ({ ...node,
    ...(node.type === 'drawing' ? { style: { ...drawingBounds(node.data), pointerEvents: 'none' } } : {}),
    data: { ...node.data, change, remove, open, busy },
  }));
  return <div ref={canvasRef} className={`pw-whiteboard-canvas pw-board-${tool}`} data-testid="whiteboard-canvas"
    tabIndex={0} aria-label="Kanvas whiteboard" aria-busy={busy}
    onPointerDownCapture={start} onPointerMoveCapture={move} onPointerUpCapture={event => end(event)} onPointerCancelCapture={event => end(event, true)}>
    <ReactFlow nodes={nodes} edges={history.edges} nodeTypes={whiteboardNodeTypes}
      onInit={instance => { flowRef.current = instance; }}
      onNodeClick={(event, node) => {
        if (busy || tool !== 'select' || event.target.closest('textarea, input, button, .react-flow__handle')) return;
        history.update(state => ({ ...state, nodes: state.nodes.map(item => ({ ...item, selected: item.id === node.id })) }), { remember: false, dirty: false });
        canvasRef.current?.focus({ preventScroll: true });
      }}
      selectNodesOnDrag={false}
      onNodesChange={changes => {
        const removed = changes.filter(c => c.type === 'remove').map(c => c.id);
        history.update(state => ({ nodes: applyNodeChanges(changes, state.nodes), edges: removed.length ? state.edges.filter(e => !removed.includes(e.source) && !removed.includes(e.target)) : state.edges }),
          { remember: !!removed.length, dirty: changes.some(c => c.type === 'remove' || (c.type === 'position' && c.position)) });
      }}
      onNodeDragStart={history.checkpoint}
      onBeforeDelete={async ({ nodes: deletedNodes, edges: deletedEdges }) => {
        const nodeIds = new Set(deletedNodes.map(node => node.id)), edgeIds = new Set(deletedEdges.map(edge => edge.id));
        // One atomic history entry restores a deleted note together with its edges.
        history.update(state => ({ nodes: state.nodes.filter(node => !nodeIds.has(node.id)),
          edges: state.edges.filter(edge => !edgeIds.has(edge.id) && !nodeIds.has(edge.source) && !nodeIds.has(edge.target)) }));
        return false;
      }}
      onEdgesChange={changes => history.update(state => ({ ...state, edges: applyEdgeChanges(changes, state.edges) }), { remember: changes.some(c => c.type === 'remove'), dirty: changes.some(c => c.type === 'remove') })}
      onConnect={connection => { if (!busy && connection.source !== connection.target) history.update(state => ({ ...state, edges: addEdge({ ...connection, type: 'smoothstep' }, state.edges) })); }}
      nodesDraggable={!busy && tool === 'select'} nodesConnectable={!busy && tool === 'select'} elementsSelectable={!busy && tool === 'select'}
      panOnDrag={!busy && tool === 'select'} zoomOnScroll={!busy && !gesture.current} zoomOnPinch={!busy && tool === 'select'} zoomOnDoubleClick={tool === 'select'}
      fitView minZoom={0.2} maxZoom={2} fitViewOptions={{ maxZoom: 1, padding: 0.25 }}
      deleteKeyCode={busy || tool !== 'select' ? null : ['Backspace', 'Delete']}>
      <Background gap={24} size={1} color="#d3dbea" />
      <Controls showInteractive={false} />
      <MiniMap nodeColor={node => node.data.color} pannable zoomable />
      {!!points.length && <ViewportPortal><svg className="pw-drawing-preview" data-testid="whiteboard-drawing-preview"><path d={drawingPath(points, width)} fill={ink} /></svg></ViewportPortal>}
    </ReactFlow>
  </div>;
};
export const WhiteboardCanvas = props => <ReactFlowProvider><Canvas {...props} /></ReactFlowProvider>;