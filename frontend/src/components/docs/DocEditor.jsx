import React, { useEffect, useRef, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import { api } from "../../lib/api";

export const getPath = (obj, path) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
export const setPath = (obj, path, value) => {
  const [k, ...rest] = path.split(".");
  const copy = Array.isArray(obj) ? [...obj] : { ...obj };
  copy[k] = rest.length ? setPath(obj[k], rest.join("."), value) : value;
  return copy;
};

export const useBlobUrl = (path) => {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!path) { setUrl(""); return undefined; }
    let u = "", alive = true;
    api.get(path, { responseType: "blob" })
      .then((r) => { if (alive) { u = URL.createObjectURL(r.data); setUrl(u); } })
      .catch(() => alive && setUrl(""));
    return () => { alive = false; if (u) URL.revokeObjectURL(u); };
  }, [path]);
  return url;
};

export const useFileUrl = (file) => {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!file) { setUrl(""); return undefined; }
    const u = URL.createObjectURL(file); setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  return url;
};

export const useRatio = (url) => {
  const [ratio, setRatio] = useState(1);
  useEffect(() => {
    if (!url) return;
    const img = new Image();
    img.onload = () => img.naturalHeight && setRatio(img.naturalWidth / img.naturalHeight);
    img.src = url;
  }, [url]);
  return ratio;
};

// Generic image picker (logo / TTD); `url` is what is currently shown.
export const ImagePicker = ({ label, note, url, hasOwn, onFile, onRemove, testid, removeLabel = "Hapus" }) => (
  <div className="receipt-logo-picker" data-testid={`${testid}-picker`}>
    <span className="receipt-label">{label} <small className="opt-mark">(opsional)</small></span>
    <div className="receipt-logo-row">
      <div className="receipt-logo-preview" data-testid={`${testid}-preview`}>
        {url ? <img src={url} alt={label} /> : <ImagePlus size={20} />}
      </div>
      <label className="secondary-button receipt-upload-btn">
        {hasOwn ? "Ganti file" : "Unggah file"}
        <input type="file" accept="image/png,image/jpeg,image/webp" data-testid={`${testid}-input`} hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      </label>
      {hasOwn && (
        <button type="button" className="icon-button danger" title={removeLabel} data-testid={`${testid}-remove`} onClick={onRemove}>
          <X size={15} />
        </button>
      )}
    </div>
    {note && <small className="form-note">{note}</small>}
  </div>
);

export const ScaleSlider = ({ label, name, value, onChange }) => (
  <label className="doc-scale" data-testid={`scale-${name}`}>
    <span>{label}</span>
    <input type="range" min="30" max="250" step="5" value={value || 100} data-testid={`field-${name}`}
      onChange={(e) => onChange(name, Number(e.target.value))} />
    <b>{Math.round(value || 100)}%</b>
  </label>
);

const GRAD = ["#3C49A6", "#2454BF", "#1599D4"];
const PT = 2.54 / 72;

const GradShape = ({ e, k, i }) => {
  const id = `g${i}`;
  return (
    <svg className="doc-el" style={{ left: e.x * k, top: e.y * k, width: e.w * k, height: e.h * k }} viewBox="0 0 1000 1000" preserveAspectRatio="none">
      <defs><linearGradient id={id} x1="0" x2="1" y1="0" y2="0">{GRAD.map((c, j) => <stop key={c} offset={j / 2} stopColor={c} />)}</linearGradient></defs>
      {e.path ? <path d="M 0 0 L 690 0 C 770 0 790 45 825 235 L 1000 1000 L 0 1000 Z" fill={`url(#${id})`} /> : <rect width="1000" height="1000" fill={`url(#${id})`} />}
    </svg>
  );
};

const HANDLES = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
const r2 = (v) => Math.round(v * 100) / 100;

const delta = (h, mx, my, e) => {
  if (h === "move") return { dx: mx, dy: my, dw: 0, dh: 0 };
  let dw = h.includes("e") ? mx : h.includes("w") ? -mx : 0;
  let dh = h.includes("s") ? my : h.includes("n") ? -my : 0;
  dw = Math.max(0.3 - e.w, dw); dh = Math.max(0.3 - e.h, dh);
  return { dx: h.includes("w") ? -dw : 0, dy: h.includes("n") ? -dh : 0, dw, dh };
};

const ResizableImg = ({ e, k, src, box, onBox, editable }) => {
  const [d, setD] = useState(null);
  const start = (ev, h) => {
    ev.preventDefault(); ev.stopPropagation();
    const sx = ev.clientX, sy = ev.clientY;
    const calc = (m) => {
      const v = delta(h, (m.clientX - sx) / k, (m.clientY - sy) / k, e);
      const w = Math.min(21, e.w + v.dw), hh = Math.min(29.7, e.h + v.dh);
      const x = Math.max(0, Math.min(21 - w, e.x + v.dx)), y = Math.max(0, Math.min(29.7 - hh, e.y + v.dy));
      return { dx: x - e.x, dy: y - e.y, dw: w - e.w, dh: hh - e.h };
    };
    const move = (m) => setD(calc(m));
    const up = (m) => {
      window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
      const v = calc(m); setD(null);
      if (Math.abs(v.dx) + Math.abs(v.dy) + Math.abs(v.dw) + Math.abs(v.dh) < 0.02) return;
      const b = box || {};
      onBox(e.key, { dx: r2((b.dx || 0) + v.dx), dy: r2((b.dy || 0) + v.dy), dw: r2((b.dw || 0) + v.dw), dh: r2((b.dh || 0) + v.dh) });
    };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  if (!src) return null;
  const v = d || { dx: 0, dy: 0, dw: 0, dh: 0 };
  const fill = e.stretch || v.dw || v.dh;
  return (
    <div className={`doc-el doc-img ${editable ? "is-editable" : ""} ${d ? "is-dragging" : ""}`} data-testid={`preview-img-${e.key}`}
      onPointerDown={editable ? (ev) => start(ev, "move") : undefined}
      onDoubleClick={editable ? () => onBox(e.key, {}) : undefined}
      title={editable ? "Tarik untuk geser, tarik titik untuk ubah ukuran, klik dua kali untuk reset" : undefined}
      style={{ left: (e.x + v.dx) * k, top: (e.y + v.dy) * k, width: (e.w + v.dw) * k, height: (e.h + v.dh) * k }}>
      <img src={src} alt={e.key} draggable={false} style={{ objectFit: fill ? "fill" : "contain" }} />
      {editable && HANDLES.map((h) => <span key={h} className={`doc-handle doc-handle-${h}`} data-testid={`preview-resize-${e.key}-${h}`} onPointerDown={(ev) => start(ev, h)} />)}
    </div>
  );
};

const InlineEditor = ({ el, k, form, onChange, onClose }) => {
  const raw = getPath(form, el.f);
  const [v, setV] = useState(raw ?? "");
  const numeric = /\.(qty|price)$/.test(el.f);
  const multi = ["received_from", "to_name", "to_title", "to_address"].includes(el.f) || el.f.endsWith(".description");
  const commit = () => { onChange(el.f, numeric ? Number(v || 0) : v); onClose(); };
  const props = {
    autoFocus: true, value: v, "data-testid": "preview-inline-input",
    onChange: (e) => setV(e.target.value), onBlur: commit,
    onKeyDown: (e) => { if (e.key === "Escape") onClose(); if (e.key === "Enter" && (!multi || !e.shiftKey)) { e.preventDefault(); commit(); } },
  };
  const style = { left: Math.max(0, Math.min(el.x * k, 21 * k - 220)), top: el.y * k - 4, width: Math.max(220, el.w * k) };
  return (
    <div className="doc-inline" style={style}>
      {multi ? <textarea rows={3} {...props} /> : <input type={el.f === "date" ? "date" : numeric ? "number" : "text"} step="any" {...props} />}
      <small>Enter untuk simpan, Shift+Enter baris baru, Esc batal</small>
    </div>
  );
};

export const DocPreview = ({ elements, images, form, onChange, editable, loading }) => {
  const ref = useRef(null);
  const [width, setWidth] = useState(520), [editing, setEditing] = useState(null);
  useEffect(() => {
    const el = ref.current; if (!el) return undefined;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el); setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const k = width / 21;
  return (
    <div className="doc-preview-wrap" data-testid="doc-preview">
      <div className="doc-preview-bar">
        <b>Preview</b>
        <span>{editable ? "Klik teks untuk edit, tarik gambar untuk geser, tarik titik sisi/sudut untuk ubah ukuran" : "Pratinjau dokumen"}</span>
        {loading && <i className="doc-dot" data-testid="doc-preview-loading" />}
      </div>
      <div className="doc-page" ref={ref} style={{ height: 29.7 * k }} data-testid="doc-preview-page">
        {(elements || []).map((e, i) => {
          if (e.t === "rect") return <div key={i} className="doc-el" style={{ left: e.x * k, top: e.y * k, width: e.w * k, height: Math.max(1, e.h * k), background: `#${e.fill}` }} />;
          if (e.t === "grad") return <GradShape key={i} e={e} k={k} i={i} />;
          if (e.t === "img") return <ResizableImg key={`${i}-${e.key}`} e={e} k={k} src={images[e.key]} box={form.image_boxes?.[e.key]} onBox={(key, b) => onChange("image_boxes", { ...(form.image_boxes || {}), [key]: b })} editable={editable} />;
          const fs = e.size * PT * k;
          const can = editable && e.f;
          return (
            <div key={i} className={`doc-el doc-text ${can ? "is-editable" : ""}`} data-testid={can ? `preview-text-${e.f.replace(/\./g, "-")}` : undefined}
              onClick={can ? () => setEditing(e) : undefined}
              style={{ left: e.x * k, top: e.y * k, width: e.w * k, minHeight: fs * 1.2, fontSize: fs, color: `#${e.color}`, fontWeight: e.bold ? 700 : 400,
                fontStyle: e.italic ? "italic" : "normal", textAlign: e.align, lineHeight: 1.32 }}>
              {e.lines.map((l, j) => <div key={j}>{l || "\u00a0"}</div>)}
            </div>
          );
        })}
        {editing && <InlineEditor el={editing} k={k} form={form} onChange={onChange} onClose={() => setEditing(null)} />}
      </div>
    </div>
  );
};

export const usePreview = (endpoint, form, extra) => {
  const [elements, setElements] = useState(null), [loading, setLoading] = useState(false);
  const key = JSON.stringify([form, extra]);
  useEffect(() => {
    if (!form) return undefined;
    setLoading(true);
    const t = setTimeout(() => {
      api.post(endpoint, { ...form, ...extra }).then((r) => setElements(r.data.elements)).catch(() => {}).finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [endpoint, key]);
  return { elements, loading };
};

// Shared image state for logo + TTD of a document.
export const useDocImages = (base, doc, showSignature) => {
  const [logoFile, setLogoFile] = useState(null), [logoRemoved, setLogoRemoved] = useState(false);
  const [signFile, setSignFile] = useState(null), [signRemoved, setSignRemoved] = useState(false);
  const brand = useBlobUrl("/doc-assets/brand");
  const defaultSign = useBlobUrl(showSignature ? "/doc-assets/ttd-default" : "");
  const storedLogo = useBlobUrl(doc?.logo_path && !logoRemoved && !logoFile ? `${base}/${doc.id}/logo` : "");
  const storedSign = useBlobUrl(doc?.sign_path && !signRemoved && !signFile && showSignature ? `${base}/${doc.id}/signature` : "");
  const logoLocal = useFileUrl(logoFile), signLocal = useFileUrl(signFile);
  const logo = logoLocal || storedLogo;
  const ownSign = signLocal || storedSign;
  const sign = ownSign || defaultSign;
  const clientRatio = useRatio(logo), signRatio = useRatio(sign);
  const reset = () => { setLogoFile(null); setLogoRemoved(false); setSignFile(null); setSignRemoved(false); };
  return {
    logo, sign, ownSign: Boolean(ownSign), urls: { brand, client: logo, sign },
    extra: { has_logo: Boolean(logo), client_ratio: clientRatio, sign_ratio: signRatio },
    logoFile, signFile, logoRemoved, signRemoved, reset,
    pickLogo: (f) => { setLogoFile(f); setLogoRemoved(false); },
    dropLogo: () => { setLogoFile(null); setLogoRemoved(true); },
    pickSign: (f) => { setSignFile(f); setSignRemoved(false); },
    dropSign: () => { setSignFile(null); setSignRemoved(true); },
  };
};

export const uploadDocImages = async (base, id, imgs, onError) => {
  for (const [file, kind, label] of [[imgs.logoFile, "logo", "logo"], [imgs.signFile, "signature", "TTD"]]) {
    if (!file) continue;
    try { const fd = new FormData(); fd.append("file", file); await api.post(`${base}/${id}/${kind}`, fd); }
    catch (e) { onError(label, e); }
  }
};

export const SignatureFields = ({ form, setField, imgs, prefix }) => (
  <div className="doc-sign-box" data-testid={`${prefix}-signature-section`}>
    <label className="receipt-tax">
      <input type="checkbox" checked={Boolean(form.show_signature)} data-testid="field-show_signature"
        onChange={(e) => setField("show_signature", e.target.checked)} /> Tampilkan tanda tangan (TTD)
    </label>
    {form.show_signature && (
      <ImagePicker label="File TTD" testid={`${prefix}-sign`} url={imgs.sign} hasOwn={imgs.ownSign}
        onFile={imgs.pickSign} onRemove={imgs.dropSign} removeLabel="Kembali ke TTD bawaan"
        note={imgs.ownSign ? "TTD khusus dokumen ini." : "Memakai TTD bawaan. Unggah file untuk mengganti TTD dokumen ini saja."} />
    )}
  </div>
);

export const SizeFields = ({ form, setField, imgs }) => (
  <div className="doc-scales" data-testid="doc-size-fields">
    <ScaleSlider label="Ukuran logo perusahaan" name="logo_scale" value={form.logo_scale} onChange={setField} />
    {imgs.logo && <ScaleSlider label="Ukuran logo penerima" name="client_logo_scale" value={form.client_logo_scale} onChange={setField} />}
    {form.show_signature && <ScaleSlider label="Ukuran TTD" name="sign_scale" value={form.sign_scale} onChange={setField} />}
  </div>
);
