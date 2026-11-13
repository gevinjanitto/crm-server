import React from 'react';
import { MouseSensor, TouchSensor, KeyboardSensor, useSensor, useSensors, pointerWithin, closestCenter } from '@dnd-kit/core';
import { useSortable, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';
import { slug } from '../../lib/api';
import { TaskCard } from './TaskCard';

export const useBoardSensors = () => useSensors(
  useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
  useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
  useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
);

export const boardCollision = (args, board) => {
  const isColumn = args.active.data.current?.type === 'column';
  const droppableContainers = args.droppableContainers.filter(item =>
    !isColumn || item.data.current?.type === 'column');
  const candidates = { ...args, droppableContainers };
  if (args.pointerCoordinates && board) {
    const { x, y } = args.pointerCoordinates;
    const bounds = board.getBoundingClientRect();
    if (x < bounds.left || x > bounds.right || y < bounds.top || y > bounds.bottom) return [];
    // A column is a full-height drop lane, including blank space below cards.
    // This remains usable while the horizontal scroll container auto-scrolls.
    const lane = droppableContainers.find(item => {
      const rect = args.droppableRects.get(item.id);
      return item.data.current?.type === 'column' && rect && x >= rect.left && x <= rect.right;
    });
    if (lane) {
      if (!isColumn) {
        const taskHits = pointerWithin({ ...candidates, droppableContainers: droppableContainers.filter(item =>
          item.data.current?.type === 'task' && item.data.current.task.status === lane.data.current.col.name) });
        if (taskHits.length) return taskHits;
      }
      return [{ id: lane.id }];
    }
    return [];
  }
  const hits = pointerWithin(candidates);
  if (hits.length) {
    const taskHits = hits.filter(hit => droppableContainers.find(item => item.id === hit.id)?.data.current?.type === 'task');
    return !isColumn && taskHits.length ? taskHits : hits;
  }
  // Pointer outside the board cancels; keyboard gets geometric targets.
  return args.pointerCoordinates ? [] : closestCenter(candidates);
};

export const DragColumn = ({ col, editable, highlighted, children, header }) => {
  const { setNodeRef, setActivatorNodeRef, listeners, attributes, transform, transition, isDragging } = useSortable({
    id: `column:${col.id}`, data: { type: 'column', col }, disabled: { draggable: !editable },
  });
  return <section ref={setNodeRef} data-testid={`kanban-column-${slug(col.name)}`}
    className={`ck-col ${highlighted ? 'over' : ''} ${isDragging ? 'dragging' : ''}`}
    style={{ transform: CSS.Translate.toString(transform), transition }}>
    <header className="ck-col-head">
      {editable && <button ref={setActivatorNodeRef} {...attributes} {...listeners}
        className="ck-drag-handle ck-column-handle" data-testid={`column-drag-${col.id}`}
        aria-label={`Geser kolom ${col.name}`} title={`Geser kolom ${col.name}`} onClick={event => event.stopPropagation()}>
        <GripVertical size={16} />
      </button>}
      {header}
    </header>
    {children}
  </section>;
};

export const DragTask = ({ t, editable, statuses, onOpen }) => {
  const { setNodeRef, setActivatorNodeRef, attributes, listeners, transform, transition, isDragging } = useSortable({
    id: `task:${t.id}`, data: { type: 'task', task: t }, disabled: { draggable: !editable },
  });
  const handle = editable ? <button ref={setActivatorNodeRef} {...attributes} {...listeners}
    className="ck-drag-handle ck-task-handle" data-testid={`task-drag-${t.id}`}
    aria-label={`Geser task ${t.title}`} title="Geser task" onClick={event => event.stopPropagation()}
    onKeyDown={event => { listeners?.onKeyDown?.(event); event.stopPropagation(); }}>
    <GripVertical size={16} />
  </button> : null;
  return <TaskCard t={t} statuses={statuses} onOpen={onOpen} dragging={isDragging}
    nodeRef={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }} handle={handle}
    dragListeners={editable ? { onMouseDown: listeners?.onMouseDown, onTouchStart: listeners?.onTouchStart } : {}} />;
};