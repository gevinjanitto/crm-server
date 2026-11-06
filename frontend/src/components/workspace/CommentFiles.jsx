import React, { useRef, useState } from "react";
import { Paperclip, FileText, Download, X } from "lucide-react";
import { download } from "../../lib/api";
import { AuthImage, ImageLightbox } from "../kanban/AuthImage";
import { DocPreview, PreviewButton } from "../DocPreview";

export const COMMENT_ACCEPT = "image/png,image/jpeg,image/gif,image/webp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.rar";
const size = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

export const CommentFiles = ({ comment, base }) => {
  const [open, setOpen] = useState(null), [preview, setPreview] = useState(null);
  const files = comment.attachments || [];
  if (!files.length) return null;
  const path = (a) => `${base}/comments/${comment.id}/attachments/${a.id}`;
  return (
    <div className="pw-comment-files" data-testid={`comment-files-${comment.id}`}>
      {files.filter((a) => a.is_image).map((a) => (
        <AuthImage key={a.id} path={path(a)} alt={a.name} className="pw-comment-image" testid={`comment-image-${a.id}`} onClick={() => setOpen({ name: a.name, path: path(a) })} />
      ))}
      {files.filter((a) => !a.is_image).map((a) => (
        <span key={a.id} className="pw-comment-doc-row">
          <button type="button" className="pw-comment-doc" data-testid={`comment-doc-${a.id}`} onClick={() => download(path(a), a.name)}>
            <FileText size={15} /><span>{a.name}<small>{size(a.size)}</small></span><Download size={13} />
          </button>
          <PreviewButton className="doc-preview-inline" size={14} testid={`comment-doc-preview-${a.id}`} onClick={() => setPreview({ name: a.name, path: path(a), type: a.content_type })} />
        </span>
      ))}
      <ImageLightbox image={open} onClose={() => setOpen(null)} />
      <DocPreview file={preview} onClose={() => setPreview(null)} />
    </div>
  );
};

export const AttachPicker = ({ files, setFiles }) => {
  const input = useRef(null);
  return (
    <>
      <button type="button" className="pw-icon" data-testid="comment-attach" title="Lampirkan foto / dokumen" onClick={() => input.current?.click()}><Paperclip size={16} /></button>
      <input ref={input} type="file" hidden multiple accept={COMMENT_ACCEPT} data-testid="comment-file-input"
        onChange={(e) => { setFiles((f) => [...f, ...e.target.files].slice(0, 5)); e.target.value = ""; }} />
    </>
  );
};

export const PickedFiles = ({ files, setFiles }) => !!files.length && (
  <div className="pw-picked-files" data-testid="comment-picked-files">
    {files.map((f, i) => (
      <span key={`${f.name}-${i}`} data-testid={`comment-picked-${i}`}>
        {f.name}
        <button type="button" data-testid={`comment-picked-remove-${i}`} onClick={() => setFiles(files.filter((_, j) => j !== i))}><X size={11} /></button>
      </span>
    ))}
  </div>
);
