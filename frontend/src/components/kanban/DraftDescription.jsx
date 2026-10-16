import React from "react";
import { RichDescription } from "./RichDescription";

/* Description field for create forms: text, formatting and pasted photos are saved together with the form. */
export const DraftDescription = ({ value, onChange, testid }) => (
  <div className="form-field" data-testid={`${testid}-field`}>
    <span>Deskripsi</span>
    <RichDescription docKey="draft" html={value.html} editable onDraft={(html, files) => onChange({ html, files })}
      imagePath={() => ""} preview={false} className="compact"
      placeholder="Tulis deskripsi… tempel (Ctrl+V) atau seret foto langsung ke sini"
      ids={{ root: `${testid}-editor`, input: `${testid}-input`, view: testid, tool: `${testid}-tool`, file: `${testid}-image-input` }} />
  </div>
);
