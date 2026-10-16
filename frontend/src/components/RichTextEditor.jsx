import React, { useEffect, useRef, useState } from "react";
import {
  Bold,
  Italic,
  Code2,
  Link2,
  List,
  ListOrdered,
  Quote,
  Eraser,
} from "lucide-react";

export default function RichTextEditor({
  value,
  onChange,
  placeholder,
  testid = "rte",
}) {
  const ref = useRef(null);
  const [, force] = useState(0);
  useEffect(() => {
    if (ref.current && (ref.current.innerHTML || "") !== (value || ""))
      if (!value || !ref.current.innerHTML) ref.current.innerHTML = value || "";
  }, [value]);
  const emit = () => {
    const html = ref.current?.innerHTML || "";
    onChange(html === "<br>" ? "" : html);
    force((n) => n + 1);
  };
  const exec = (cmd, arg) => {
    ref.current?.focus();
    document.execCommand(cmd, false, arg);
    emit();
  };
  const link = () => {
    const url = window.prompt("Masukkan URL (https://...)");
    if (url && /^https?:\/\//i.test(url)) exec("createLink", url);
  };
  const code = () => {
    const sel = window.getSelection()?.toString();
    if (sel) exec("insertHTML", `<code>${sel.replace(/</g, "&lt;")}</code>`);
  };
  const tools = [
    ["Tebal (Ctrl+B)", <Bold size={15} />, () => exec("bold"), "bold"],
    ["Miring (Ctrl+I)", <Italic size={15} />, () => exec("italic"), "italic"],
    ["Kode", <Code2 size={15} />, code, "code"],
    ["Tautan", <><Link2 size={15} /> Link</>, link, "link"],
    null,
    ["Daftar poin", <List size={15} />, () => exec("insertUnorderedList"), "ul"],
    ["Daftar angka", <ListOrdered size={15} />, () => exec("insertOrderedList"), "ol"],
    ["Kutipan", <Quote size={15} />, () => exec("formatBlock", "blockquote"), "quote"],
    null,
    ["Hapus format", <Eraser size={15} />, () => exec("removeFormat"), "clear"],
  ];
  return (
    <div className="rte" data-testid={testid}>
      <div className="rte-toolbar" role="toolbar">
        {tools.map((t, i) =>
          t ? (
            <button
              key={t[3]}
              type="button"
              title={t[0]}
              data-testid={`${testid}-${t[3]}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={t[2]}
            >
              {t[1]}
            </button>
          ) : (
            <i key={`sep-${i}`} />
          ),
        )}
      </div>
      <div
        ref={ref}
        className="rte-editor"
        contentEditable
        suppressContentEditableWarning
        data-placeholder={placeholder}
        data-testid={`${testid}-editor`}
        onInput={emit}
        onBlur={emit}
      />
    </div>
  );
}
