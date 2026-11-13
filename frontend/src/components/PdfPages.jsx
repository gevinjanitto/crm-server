import React, { useEffect, useRef, useState } from "react";
import { Loader2, FileText } from "lucide-react";
import "./pdf-pages.css";

let lib;
const loadPdf = async () => {
  if (!lib) { lib = await import("pdfjs-dist/legacy/build/pdf"); lib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.js"; }
  return lib;
};

// iOS crops iframe PDFs to the first page and Android Chrome cannot render them, so touch devices draw pages to canvas.
export const needsPdfCanvas = () => typeof window !== "undefined" && (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
  || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1) || window.matchMedia("(pointer: coarse)").matches);

export const PdfPages = ({ src, testid = "pdf-pages", fallback = null }) => {
  const box = useRef(null);
  const [status, setStatus] = useState("loading");
  useEffect(() => {
    let alive = true, doc;
    const urls = [];
    setStatus("loading");
    (async () => {
      const pdfjs = await loadPdf();
      doc = await pdfjs.getDocument({ url: src }).promise;
      const el = box.current;
      if (!alive || !el) return;
      el.innerHTML = "";
      const width = Math.max(el.clientWidth - 16, 280), ratio = Math.min(window.devicePixelRatio || 1, 2);
      for (let n = 1; n <= doc.numPages && alive; n++) {
        const page = await doc.getPage(n);
        const vp = page.getViewport({ scale: (width / page.getViewport({ scale: 1 }).width) * ratio });
        const c = document.createElement("canvas");
        c.width = Math.floor(vp.width); c.height = Math.floor(vp.height);
        await page.render({ canvasContext: c.getContext("2d"), viewport: vp }).promise;
        // Mobile Chrome repaints big canvases on every frame (flicker); a static image is composited once.
        const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.9));
        c.width = c.height = 0;
        if (!alive) return;
        const img = new Image();
        img.className = "pdf-page"; img.alt = `Halaman ${n}`; img.dataset.testid = `pdf-page-${n}`; img.decoding = "async";
        img.width = Math.floor(vp.width); img.height = Math.floor(vp.height);
        img.src = URL.createObjectURL(blob); urls.push(img.src);
        el.appendChild(img);
        page.cleanup();
        if (n === 1 && alive) setStatus("ready");
      }
    })().catch(() => alive && setStatus("error"));
    return () => { alive = false; doc?.destroy(); urls.forEach((u) => URL.revokeObjectURL(u)); };
  }, [src]);
  return (
    <div className="pdf-pages-wrap" data-testid={testid} data-status={status}>
      {status === "loading" && <div className="pdf-pages-note"><Loader2 size={20} className="spin" /> Memuat halaman PDF…</div>}
      {status === "error" && <div className="pdf-pages-note" data-testid={`${testid}-error`}><FileText size={22} /> PDF gagal dimuat. {fallback}</div>}
      <div ref={box} className="pdf-pages" />
    </div>
  );
};
