import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, Download } from "lucide-react";
import { api, download } from "../../lib/api";

const useBlobUrl = (path) => {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let alive = true, made = "";
    api.get(path, { responseType: "blob" }).then((r) => {
      made = URL.createObjectURL(r.data);
      if (alive) setUrl(made); else URL.revokeObjectURL(made);
    }).catch(() => alive && setUrl("error"));
    return () => { alive = false; if (made) URL.revokeObjectURL(made); };
  }, [path]);
  return url;
};

export const AuthImage = ({ path, alt, className, testid, onClick }) => {
  const url = useBlobUrl(path);
  if (!url) return <span className={`ck-img-loading ${className || ""}`} data-testid={testid} />;
  if (url === "error") return <span className={`ck-img-loading error ${className || ""}`} data-testid={testid}>Gagal memuat</span>;
  return <img src={url} alt={alt} className={className} data-testid={testid} onClick={onClick} />;
};

export const ImageLightbox = ({ image, onClose }) => {
  useEffect(() => {
    if (!image) return;
    const h = (e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [image, onClose]);
  if (!image) return null;
  return createPortal(
    <div className="ck-lightbox" role="dialog" data-testid="image-lightbox" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="ck-lightbox-bar">
        <span>{image.name}</span>
        <button type="button" data-testid="lightbox-download" onClick={() => download(image.path, image.name)}><Download size={16} /></button>
        <button type="button" data-testid="lightbox-close" onClick={onClose}><X size={18} /></button>
      </div>
      <AuthImage path={image.path} alt={image.name} className="ck-lightbox-img" testid="lightbox-image" />
    </div>,
    document.body,
  );
};
