import type { Metadata } from "next";
import Link from "next/link";
import { Nav } from "@/components/nav";
import "./globals.css";
export const metadata: Metadata = {
  title: "Compute Market | Research Workbench",
  description:
    "An auditable research interface for GPU compute market microstructure.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <aside className="sidebar">
          <Link href="/market" className="brand">
            <span className="brand-icon">▥</span>
            <span>
              COMPUTE<span className="brand-sub">MARKET RESEARCH</span>
            </span>
          </Link>
          <div className="workspace-label">RESEARCH WORKBENCH</div>
          <Nav />
          <div className="sidebar-bottom">
            <span className="badge">PHASE 01</span>
            <p>Akash microstructure laboratory</p>
            <small>
              Transparent market mechanics.
              <br />
              Reproducible research.
            </small>
          </div>
        </aside>
        <div className="workspace">
          <div className="topbar">
            <span>
              Markets <span className="divider">/</span> Akash Network
            </span>
            <span className="topbar-note">OBSERVATIONS, NOT PREDICTIONS</span>
          </div>
          <main>{children}</main>
          <footer>
            COMPUTE MARKET RESEARCH{" "}
            <span>
              Akash is a microstructure laboratory, not a global GPU price
              benchmark.
            </span>
          </footer>
        </div>
      </body>
    </html>
  );
}
