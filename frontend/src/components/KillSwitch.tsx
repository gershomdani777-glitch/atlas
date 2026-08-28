"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAtlas } from "@/context/AtlasProvider";
import ClickSpark from "@/components/reactbits/ClickSpark";

export function KillSwitch() {
  const { running } = useAtlas();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function toggle() {
    setBusy(true);
    setFailed(false);
    try {
      if (running) {
        await api.killAgent();
      } else {
        await api.resumeAgent();
      }
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ClickSpark sparkColor="#c8f169" sparkCount={10} sparkRadius={22} duration={450}>
      <button
        className={running ? "btn-filled" : "btn-ghost"}
        onClick={toggle}
        disabled={busy}
        title={failed ? "Last attempt failed — backend may be unreachable" : undefined}
        style={{ fontSize: 14, padding: "10px 18px", outline: failed ? "2px solid var(--color-charcoal)" : undefined }}
      >
        {running ? "Kill Switch" : "Resume Agent"}
      </button>
    </ClickSpark>
  );
}
