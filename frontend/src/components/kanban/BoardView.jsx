import React, { useLayoutEffect, useRef, useState } from "react";
import { Plus, MoreHorizontal, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";
import { api, errorText, slug } from "../../lib/api";
import { createPortal } from 'react-dom';
import { DndContext, DragOverlay, MeasuringStrategy } from '@dnd-kit/core';
import { SortableContext, horizontalListSortingStrategy, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { DragColumn, DragTask, useBoardSensors, boardCollision } from './BoardDrag';
import { STATUS_COLORS, byOrder, midOrder, canMoveTask } from "./helpers";

const VISIBLE_TASKS = 10;

const ColumnCards = ({ count, testid, children }) => {
  const ref = useRef(null), [max, setMax] = useState(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || count <= VISIBLE_TASKS) return setMax(null);
    const measure = () => {
      const last = el.children[VISIBLE_TASKS - 1];
      if (last) setMax(Math.ceil(last.getBoundingClientRect().bottom - el.getBoundingClientRect().top + el.scrollTop) + 2);
    };
    measure();
    const ro = new ResizeObserver(measure);
    [...el.children].slice(0, VISIBLE_TASKS).forEach((c) => ro.observe(c));
    return () => ro.disconnect();
  }, [count]);
  return (
    <div ref={ref} className={`ck-cards ${max ? "ck-cards-scroll" : ""}`} style={max ? { maxHeight: max } : undefined} data-testid={testid}>
      {children}
    </div>
  );
};

const ColumnMenu = ({ col, project, statuses, onChange, onClose }) => {
  const [name, setName] = useState(col.name),
    [color, setColor] = useState(col.color),
    [kind, setKind] = useState(col.kind);
  const base = `/projects/${project.id}/statuses/${col.id}`;
  const save = async () => {
    try {
      const r = await api.patch(base, { name, color, kind });
      onChange(r.data);
      toast.success("Status diperbarui");
      onClose();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const remove = async () => {
    if (statuses.length < 2) return toast.error("Minimal satu status.");
    if (!window.confirm(`Hapus status "${col.name}"? Task akan dipindahkan.`))
      return;
    try {
      const r = await api.delete(base);
      onChange(r.data);
      onClose();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  return (
    <div className="ck-menu" data-testid={`column-menu-${slug(col.name)}`} onClick={(e) => e.stopPropagation()}>
      <label>
        Nama status
        <input
          data-testid="column-name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label>
        Jenis
        <select value={kind} onChange={(e) => setKind(e.target.value)} data-testid="column-kind-select">
          <option value="todo">Belum dikerjakan</option>
          <option value="active">Sedang berjalan</option>
          <option value="done">Selesai</option>
        </select>
      </label>
      <div className="ck-colors">
        {STATUS_COLORS.map((c) => (
          <button
            key={c}
            className={color === c ? "active" : ""}
            style={{ background: c }}
            onClick={() => setColor(c)}
            aria-label={c}
            data-testid={`column-color-${c.replace('#', '')}`}
          />
        ))}
      </div>
      <div className="ck-menu-actions">
        <button className="ck-danger" data-testid="column-delete" onClick={remove}>
          <Trash2 size={14} /> Hapus
        </button>
        <button className="ck-primary" data-testid="column-save" onClick={save}>
          <Pencil size={14} /> Simpan
        </button>
      </div>
    </div>
  );
};

const QuickAdd = ({ project, status, onAdded }) => {
  const [open, setOpen] = useState(false),
    [title, setTitle] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      const r = await api.post(`/projects/${project.id}/tasks`, {
        title: title.trim(),
        status,
      });
      onAdded(r.data);
      setTitle("");
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  if (!open)
    return (
      <button
        className="ck-add-task"
        data-testid={`quick-add-${slug(status)}`}
        onClick={() => setOpen(true)}
      >
        <Plus size={15} /> Tambah task
      </button>
    );
  return (
    <form className="ck-quick-add" onSubmit={submit}>
      <input
        autoFocus
        data-testid={`quick-add-input-${slug(status)}`}
        placeholder="Nama task, Enter untuk simpan"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onBlur={() => !title && setOpen(false)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      />
    </form>
  );
};

const AddColumn = ({ project, onChange }) => {
  const [open, setOpen] = useState(false),
    [name, setName] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const r = await api.post(`/projects/${project.id}/statuses`, {
        name: name.trim(),
        color: STATUS_COLORS[Math.floor(Math.random() * STATUS_COLORS.length)],
        kind: "active",
      });
      onChange(r.data);
      setName("");
      setOpen(false);
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  return (
    <div className="ck-col ck-add-col">
      {open ? (
        <form onSubmit={submit} className="ck-quick-add">
          <input
            autoFocus
            data-testid="add-column-input"
            placeholder="Nama status baru"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          />
        </form>
      ) : (
        <button data-testid="add-column" onClick={() => setOpen(true)}>
          <Plus size={16} /> Tambah status
        </button>
      )}
    </div>
  );
};

export const BoardView = ({
  project,
  tasks,
  statuses,
  setStatuses,
  user,
  manager,
  onOpen,
  onLocalUpdate,
  onAdded,
}) => {
  const [drag, setDrag] = useState(null),
    [over, setOver] = useState(null),
    [menu, setMenu] = useState(null),
    [saving, setSaving] = useState(false);
  const sensors = useBoardSensors();
  const boardRef = useRef(null);
  const columns = statuses || [];
  const move = async (t, status, index) => {
    const items = tasks
      .filter((x) => x.status === status && x.id !== t.id)
      .sort(byOrder);
    const order = midOrder(items[index - 1], items[index]);
    if (t.status === status && t.order === order) return;
    onLocalUpdate({ ...t, status, order });
    setSaving(true);
    try {
      const r = await api.patch(`/projects/${project.id}/tasks/${t.id}`, {
        status,
        order,
      });
      onLocalUpdate(r.data);
      if (t.status !== status) toast.success(`Dipindahkan ke ${status}`);
    } catch (e) {
      toast.error(errorText(e));
      onLocalUpdate(t);
    } finally {
      setSaving(false);
    }
  };
  const reorderCols = async (dragCol, targetId) => {
    if (!dragCol || dragCol === targetId) return;
    const ids = columns.map((c) => c.id),
      from = ids.indexOf(dragCol),
      to = ids.indexOf(targetId);
    ids.splice(from, 1);
    ids.splice(to, 0, dragCol);
    setStatuses(ids.map((i) => columns.find((c) => c.id === i)));
    setSaving(true);
    try {
      const r = await api.post(`/projects/${project.id}/statuses/reorder`, { ids });
      setStatuses(r.data);
    } catch (e) {
      toast.error(errorText(e));
      setStatuses(columns);
    } finally {
      setSaving(false);
    }
  };
  const end = () => {
    setDrag(null);
    setOver(null);
  };
  const drop = ({ active, over: target }) => {
    end();
    if (!target || active.id === target.id) return;
    const source = active.data.current;
    const destination = target.data.current;
    if (source?.type === 'column') { reorderCols(source.col.id, destination.col.id); return; }
    if (!source?.task || !destination) return;
    const status = destination.task?.status || destination.col?.name;
    const items = tasks.filter(t => t.status === status && t.id !== source.task.id).sort(byOrder);
    let index = items.length;
    if (destination.task) {
      if (source.task.status === status) {
        index = tasks.filter(t => t.status === status).sort(byOrder).findIndex(t => t.id === destination.task.id);
      } else {
        index = items.findIndex(t => t.id === destination.task.id);
        const rect = active.rect.current.translated;
        if (rect && rect.top + rect.height / 2 > target.rect.top + target.rect.height / 2) index += 1;
      }
    }
    move(source.task, status, Math.max(0, index));
  };
  return (
    <DndContext sensors={sensors} collisionDetection={args => boardCollision(args, boardRef.current)}
      measuring={{ droppable: { strategy: MeasuringStrategy.Always } }}
      onDragStart={({ active }) => { setMenu(null); setDrag(active.data.current); }}
      onDragOver={({ over }) => setOver(over?.data.current)}
      onDragEnd={drop} onDragCancel={end}>
    <SortableContext items={columns.map(col => `column:${col.id}`)} strategy={horizontalListSortingStrategy}>
    <div ref={boardRef} className="ck-board" data-testid="kanban-board"
      data-drag-type={drag?.type || 'none'} data-drop-target={over?.task?.id || over?.col?.name || 'none'}
      onClick={() => setMenu(null)}>
      {columns.map((col) => {
        const items = tasks.filter((t) => t.status === col.name).sort(byOrder);
        const isOver = drag?.type === 'task' && (over?.task?.status || over?.col?.name) === col.name;
        return (
          <DragColumn key={col.id} col={col} editable={manager && !saving} highlighted={isOver} header={<>
              <span
                className="ck-status-pill"
                style={{ background: col.color }}
                data-testid={`kanban-column-title-${slug(col.name)}`}
              >
                {col.name}
              </span>
              <span className="ck-col-count" data-testid={`kanban-count-${slug(col.name)}`}>
                {items.length}
              </span>
              <span className="ck-spacer" />
              {manager && (
                <button
                  className="ck-icon"
                  data-testid={`column-menu-btn-${slug(col.name)}`}
                  title="Pengaturan status"
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenu(menu === col.id ? null : col.id);
                  }}
                >
                  <MoreHorizontal size={16} />
                </button>
              )}
              {menu === col.id && (
                <ColumnMenu
                  col={col}
                  project={project}
                  statuses={columns}
                  onChange={setStatuses}
                  onClose={() => setMenu(null)}
                />
              )}
            </>}>
            <SortableContext items={items.map(t => `task:${t.id}`)} strategy={verticalListSortingStrategy}>
            <ColumnCards count={items.length} testid={`kanban-cards-${slug(col.name)}`}>
              {items.map(t => <DragTask key={t.id} t={t} statuses={columns}
                editable={canMoveTask(user) && !saving} onOpen={onOpen} />)}
              {!items.length && !isOver && (
                <p className="ck-empty" data-testid={`column-empty-${col.id}`}>Belum ada task</p>
              )}
              {isOver && <div className="ck-drop-line" data-testid={`column-drop-target-${col.id}`} />}
            </ColumnCards>
            </SortableContext>
            {manager && (
              <QuickAdd project={project} status={col.name} onAdded={onAdded} />
            )}
          </DragColumn>
        );
      })}
      {manager && <AddColumn project={project} onChange={setStatuses} />}
    </div>
    </SortableContext>
    {createPortal(<DragOverlay dropAnimation={{ duration: 200, easing: 'ease-out' }}>
      {drag && <div className={`ck-drag-preview ${drag.type === 'column' ? 'column-preview' : ''}`}
        data-testid="kanban-drag-preview" aria-hidden="true">
        <span style={{ background: drag.col?.color || '#2c63e8' }} />
        {drag.task?.title || drag.col?.name}
      </div>}
    </DragOverlay>, document.body)}
    </DndContext>
  );
};
