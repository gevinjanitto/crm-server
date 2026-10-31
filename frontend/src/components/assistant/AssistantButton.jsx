import React, { useState } from "react";
import { Sparkles } from "lucide-react";
import { useAiStatus } from "./useAiStatus";
import { AssistantPanel } from "./AssistantPanel";
import "./assistant.css";

export const AssistantButton = () => {
  const status = useAiStatus(), [open, setOpen] = useState(false);
  if (!status?.enabled || !status.allowed) return null;
  return (
    <>
      <button type="button" className="ai-trigger" data-testid="assistant-open-button" onClick={() => setOpen(true)} title="Asisten AI">
        <Sparkles size={15} /><span>Asisten AI</span>
      </button>
      <AssistantPanel open={open} onOpenChange={setOpen} ready={status.assistant_ready} />
    </>
  );
};
