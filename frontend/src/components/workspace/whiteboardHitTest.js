// Test the actual rendered SVG path, including every viewport/CSS transform.
// Sample between pointer events so quick eraser gestures cannot jump over a line.
export const hitDrawings = (canvas, context, event, previous) => {
  const start = previous || [event.clientX, event.clientY];
  const dx = event.clientX - start[0], dy = event.clientY - start[1];
  const steps = Math.max(1, Math.min(256, Math.ceil(Math.hypot(dx, dy) / 4)));
  const samples = Array.from({ length: steps + 1 }, (_, index) =>
    new DOMPoint(start[0] + dx * index / steps, start[1] + dy * index / steps));
  const hits = [];
  for (const node of canvas.querySelectorAll('.react-flow__node-drawing')) {
    const element = node.querySelector('svg path');
    const matrix = element?.getScreenCTM();
    if (!matrix) continue;
    const inverse = matrix.inverse();
    const path = new Path2D(element.getAttribute('d'));
    context.lineWidth = (event.pointerType === 'touch' ? 20 : 10) / Math.hypot(matrix.a, matrix.b);
    if (samples.some(sample => {
      const local = sample.matrixTransform(inverse);
      return context.isPointInPath(path, local.x, local.y) || context.isPointInStroke(path, local.x, local.y);
    })) hits.push(node.getAttribute('data-id'));
  }
  return hits;
};