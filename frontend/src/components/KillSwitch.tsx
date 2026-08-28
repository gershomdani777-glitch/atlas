"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAtlas } from "@/context/AtlasProvider";
import ClickSpark from "@/components/reactbits/ClickSpark";

export function KillSwitch() {
  const { running } = useAtlas();
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    try {
      if (running) {
        await api.killAgent();
      } else {
        await api.resumeAgent();
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <ClickSpark sparkColor="#c8f169" sparkCount={10} sparkRadius={22} duration={450}>
      <button className={running ? "btn-filled" : "btn-ghost"} onClick={toggle} disabled={busy} style={{ fontSize: 14, padding: "10px 18px" }}>
        {running ? "Kill Switch" : "Resume Agent"}
      </button>
    </ClickSpark>
  );
}
