import React, { useEffect, useRef, useState } from "react";
import * as D from "@radix-ui/react-dialog";
import { X, Download, FileText, Loader2, Eye } from "lucide-react";
import { api, download } from "../lib/api";
import "./doc-preview.css";

const KINDS = { pdf: "pdf", png: "image", jpg: "image", jpeg: "image", gif: "image", webp: "image", txt: "text", csv: "text", docx: "docx", xlsx: "sheet" };
const kindOf = (name = "", type = "") => KINDS[(name.split(".").pop() || "").toLowerCase()] || (type.startsWith("image/") ? "image" : type === "application/pdf" ? "pdf" : null);
const cellText = (c) => (c instanceof Date ? c.toLocaleDateString("id-ID") : String(c ?? ""));

const Sheets = ({ sheets }) => {
  const [i, setI] = useState(0), rows = sheets[i]?.data || [];
  return (
    <div className="doc-preview-sheet" data-testid="doc-preview-sheet">
      {sheets.length > 1 && <div className="doc-preview-tabs">{sheets.map((s, k) => <button key={s.sheet} type="button" className={k === i ? "on" : ""} data-testid={`doc-preview-sheet-tab-${k}`} onClick={() => setI(k)}>{s.sheet}</button>)}</div>}
      <div className="doc-preview-table-wrap">
        <table><tbody>{rows.slice(0, 1000).map((r, y) => <tr key={y}>{r.map((c, x) => <td key={x}>{cellText(c)}</td>)}</tr>)}</tbody></table>
        {!rows.length && <p className="doc-preview-note">Sheet ini kosong.</p>}
      </div>
    </div>
  );
};

const Body = ({ file, state, docxBox }) => {
  if (state.status === "loading") return <div className="doc-preview-note" data-testid="doc-preview-loading"><Loader2 size={22} className="spin" /> Memuat pratinjau…</div>;
  if (state.status !== "ready") return (
    <div className="doc-preview-note" data-testid="doc-preview-unavailable">
      <FileText size={34} />
      <b>{state.status === "error" ? "Pratinjau gagal dimuat." : "Pratinjau belum tersedia untuk format ini."}</b>
      <button type="button" className="doc-preview-download" data-testid="doc-preview-download-fallback" onClick={() => download(file.path, file.name)}><Download size={15} /> Unduh dokumen</button>
    </div>
  );
  if (state.kind === "image") return <img className="doc-preview-image" src={state.url} alt={file.name} data-testid="doc-preview-image" />;
  if (state.kind === "pdf") return <iframe className="doc-preview-frame" src={state.url} title={file.name} data-testid="doc-preview-pdf" />;
  if (state.kind === "text") return <pre className="doc-preview-text" data-testid="doc-preview-text">{state.text}</pre>;
  if (state.kind === "sheet") return <Sheets sheets={state.sheets} />;
  return <div ref={docxBox} className="doc-preview-docx" data-testid="doc-preview-docx" />;
};

export const DocPreview = ({ file, onClose }) => {
  const [state, setState] = useState({ status: "loading" });
  const docxBox = useRef(null);
  useEffect(() => {
    if (!file) return;
    const kind = kindOf(file.name, file.type);
    if (!kind) return setState({ status: "unsupported" });
    let alive = true, url = "";
    setState({ status: "loading" });
    (async () => {
      const blob = (await api.get(file.path, { responseType: "blob" })).data;
      if (kind === "image" || kind === "pdf") {
        url = URL.createObjectURL(kind === "pdf" ? new Blob([blob], { type: "application/pdf" }) : blob);
        return { kind, url };
      }
      if (kind === "text") return { kind, text: await blob.text() };
      if (kind === "sheet") return { kind, sheets: await (await import("read-excel-file/browser")).default(blob) };
      return { kind, blob };
    })().then((s) => alive && setState({ status: "ready", ...s })).catch(() => alive && setState({ status: "error" }));
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [file]);
  useEffect(() => {
    if (state.kind !== "docx" || !docxBox.current) return;
    import("docx-preview").then(({ renderAsync }) => renderAsync(state.blob, docxBox.current, null, { inWrapper: true, ignoreLastRenderedPageBreak: true }))
      .catch(() => setState({ status: "error" }));
  }, [state]);
  return (
    <D.Root open={!!file} onOpenChange={(v) => !v && onClose()}>
      <D.Portal>
        <D.Content className="doc-preview" aria-describedby={undefined} data-testid="doc-preview"
          onEscapeKeyDown={(e) => e.stopPropagation()} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
          {file && (
            <div className="doc-preview-panel">
              <header className="doc-preview-bar">
                <D.Title className="doc-preview-title" data-testid="doc-preview-title"><FileText size={16} />{file.name}</D.Title>
                <button type="button" title="Unduh" data-testid="doc-preview-download" onClick={() => download(file.path, file.name)}><Download size={16} /></button>
                <button type="button" title="Tutup" data-testid="doc-preview-close" onClick={onClose}><X size={18} /></button>
              </header>
              <div className="doc-preview-body"><Body file={file} state={state} docxBox={docxBox} /></div>
            </div>
          )}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
};

export const PreviewButton = ({ onClick, testid, className = "icon-button", size = 15 }) => (
  <button type="button" className={className} title="Pratinjau dokumen" aria-label="Pratinjau dokumen" data-testid={testid}
    onClick={(e) => { e.preventDefault(); e.stopPropagation(); onClick(); }}>
    <Eye size={size} />
  </button>
);
