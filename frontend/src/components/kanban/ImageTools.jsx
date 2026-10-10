import React, { useEffect, useState } from "react";
import { AlignLeft, AlignCenter, AlignRight, Maximize2 } from "lucide-react";

const SIZES = [25, 50, 75, 100];
const ALIGNS = [["left", AlignLeft, "Rata kiri"], ["center", AlignCenter, "Tengah"], ["right", AlignRight, "Rata kanan"]];

// Apply stored data-width / data-align to the image's inline style.
export const applyLayout = (img) => {
  const w = img.dataset.width, a = img.dataset.align;
  img.style.width = w ? `${w}%` : "";
  img.style.marginLeft = a === "center" || a === "right" ? "auto" : "";
  img.style.marginRight = a === "center" ? "auto" : "";
};

export const ImageTools = ({ img, editor, wrap, onDone, onPreview }) => {
  const [, setTick] = useState(0), [drag, setDrag] = useState(false);
  const rerender = () => setTick((t) => t + 1);
  useEffect(() => {
    const ro = new ResizeObserver(rerender);
    ro.observe(editor);
    window.addEventListener("resize", rerender);
    return () => { ro.disconnect(); window.removeEventListener("resize", rerender); };
  }, [editor]);
  if (!editor.contains(img)) return null;
  const set = (key, value) => { img.dataset[key] = value; applyLayout(img); rerender(); onDone(); };
  const startResize = (e) => {
    e.preventDefault();
    const x0 = e.clientX, w0 = img.getBoundingClientRect().width, full = editor.clientWidth - 24;
    const dir = (img.dataset.align === "right" ? -1 : 1) * (img.dataset.align === "center" ? 2 : 1);
    const move = (ev) => {
      img.dataset.width = Math.max(10, Math.min(100, Math.round(((w0 + (ev.clientX - x0) * dir) / full) * 100)));
      applyLayout(img); rerender();
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); setDrag(false); onDone(); };
    setDrag(true);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const r = img.getBoundingClientRect(), w = wrap.getBoundingClientRect();
  const box = { top: r.top - w.top, left: r.left - w.left, width: r.width, height: r.height };
  const width = Number(img.dataset.width) || 100, align = img.dataset.align || "left";
  return (
    <>
      <div className="ck-img-frame" style={box} data-testid="image-frame">
        <span className="ck-img-size" data-testid="image-size-label">{width}%</span>
        <button type="button" className={`ck-img-handle ${drag ? "on" : ""}`} title="Seret untuk ubah ukuran" data-testid="image-resize-handle" onPointerDown={startResize} />
      </div>
      <div className="ck-img-toolbar" style={{ top: Math.max(box.top - 44, 4), left: box.left + 8 }} role="toolbar" data-testid="image-toolbar" onMouseDown={(e) => e.preventDefault()}>
        {ALIGNS.map(([k, Icon, t]) => (
          <button key={k} type="button" title={t} className={align === k ? "on" : ""} data-testid={`image-align-${k}`} onClick={() => set("align", k)}><Icon size={14} /></button>
        ))}
        <i />
        {SIZES.map((s) => (
          <button key={s} type="button" className={width === s ? "on" : ""} data-testid={`image-size-${s}`} onClick={() => set("width", s)}>{s}%</button>
        ))}
        <i />
        <button type="button" title="Lihat penuh" data-testid="image-preview" onClick={onPreview}><Maximize2 size={14} /></button>
      </div>
    </>
  );
};
