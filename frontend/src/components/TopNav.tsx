"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { KillSwitch } from "@/components/KillSwitch";
import { useAtlas } from "@/context/AtlasProvider";

const LINKS = [
  { href: "/", label: "Live Ops" },
  { href: "/decisions", label: "Decisions" },
  { href: "/performance", label: "Performance" },
  { href: "/risk", label: "Risk Console" },
];

export function TopNav() {
  const pathname = usePathname();
  const { connected } = useAtlas();

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "var(--color-paper-white)",
        borderBottom: "1px solid rgba(4, 63, 46, 0.08)",
      }}
    >
      <div
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 40px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="font-grenette" style={{ fontSize: 22, letterSpacing: "-0.3px" }}>ATLAS</span>
          <span className="live-dot" data-connected={connected} title={connected ? "Connected" : "Reconnecting"} />
        </div>

        <nav style={{ display: "flex", gap: 4 }}>
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link key={link.href} href={link.href} className="nav-pill" data-active={active} style={{ position: "relative" }}>
                {active && (
                  <motion.span
                    layoutId="nav-active-underline"
                    style={{
                      position: "absolute",
                      left: 16,
                      right: 16,
                      bottom: -6,
                      height: 2,
                      background: "var(--color-chartreuse-lime)",
                    }}
                    transition={{ type: "spring", stiffness: 500, damping: 40 }}
                  />
                )}
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div style={{ flexShrink: 0 }}>
          <KillSwitch />
        </div>
      </div>
    </header>
  );
}
