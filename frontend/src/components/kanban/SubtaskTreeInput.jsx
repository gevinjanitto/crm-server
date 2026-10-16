import React, { useState } from "react";
import { Plus, X, CornerDownRight } from "lucide-react";

export const MAX_SUBTASK_LEVEL = 3;
const node = (title) => ({ title, description: "", children: [] });
const updateAt = (list, path, fn) =>
  path.length === 1
    ? fn(list, path[0])
    : list.map((n, i) => (i === path[0] ? { ...n, children: updateAt(n.children, path.slice(1), fn) } : n));

const AddRow = ({ onAdd, testid, placeholder, autoFocus }) => {
  const [text, setText] = useState("");
  const add = () => { if (text.trim()) { onAdd(text.trim()); setText(""); } };
  return (
    <div className="subtask-add stree-add">
      <Plus size={15} />
      <input data-testid={`${testid}-input`} className="subtask-add-input" placeholder={placeholder} value={text} autoFocus={autoFocus}
        onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
      <button type="button" className="subtask-add-btn" data-testid={`${testid}-add`} onClick={add} disabled={!text.trim()}>
        <Plus size={14} /> Tambah
      </button>
    </div>
  );
};

const Node = ({ n, path, level, change, testid }) => {
  const [adding, setAdding] = useState(false);
  const id = `${testid}-${path.join("-")}`;
  const set = (patch) => change(path, (l, i) => l.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  return (
    <div className="stree-node" data-testid={id}>
      <div className="stree-head">
        {level > 1 ? <CornerDownRight size={13} className="stree-branch" /> : <span className="subtask-dot" />}
        <input className="stree-title" data-testid={`${id}-title`} value={n.title} onChange={(e) => set({ title: e.target.value })} />
        {level < MAX_SUBTASK_LEVEL && (
          <button type="button" className="stree-sub-btn" data-testid={`${id}-add-child`} onClick={() => setAdding(!adding)}>
            <Plus size={12} /> Sub
          </button>
        )}
        <button type="button" className="subtask-remove" data-testid={`${id}-remove`} aria-label="Hapus subtask"
          onClick={() => change(path, (l, i) => l.filter((_, j) => j !== i))}>
          <X size={14} />
        </button>
      </div>
      <textarea className="stree-desc" data-testid={`${id}-description`} rows={2} placeholder="Deskripsi subtask (opsional)"
        value={n.description} onChange={(e) => set({ description: e.target.value })} />
      {(n.children.length > 0 || adding) && (
        <div className="stree-children">
          {n.children.map((c, i) => <Node key={i} n={c} path={[...path, i]} level={level + 1} change={change} testid={testid} />)}
          {adding && <AddRow autoFocus testid={`${id}-child`} placeholder={`Tambah subtask tingkat ${level + 1}, tekan Enter`}
            onAdd={(t) => set({ children: [...n.children, node(t)] })} />}
        </div>
      )}
    </div>
  );
};

export const SubtaskTreeInput = ({ label = "Subtask", value = [], onChange, testid = "subtask" }) => {
  const change = (path, fn) => onChange(updateAt(value, path, fn));
  return (
    <div className="form-field subtask-field">
      <span>{label}<small className="opt-mark">(opsional, maks. {MAX_SUBTASK_LEVEL} tingkat)</small></span>
      <div className="subtask-builder" data-testid={`${testid}-builder`}>
        {value.length > 0 && (
          <div className="stree-list">
            {value.map((n, i) => <Node key={i} n={n} path={[i]} level={1} change={change} testid={`${testid}-row`} />)}
          </div>
        )}
        <AddRow testid={testid} placeholder="Tambahkan subtask, tekan Enter" onAdd={(t) => onChange([...value, node(t)])} />
      </div>
    </div>
  );
};
