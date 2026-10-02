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
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <header className="site-header">
          <div className="masthead">
            <Link href="/market" className="brand">
              Compute Market<span className="brand-sub">Data & research</span>
            </Link>
            <div className="edition">
              <span>Akash Network</span>
              <span>Research preview</span>
            </div>
          </div>
          <Nav />
        </header>
        <main id="main-content">{children}</main>
        <footer>
          <span>Compute Market Research</span>
          <span>
            Akash observations describe one marketplace, not the global GPU
            market.
          </span>
        </footer>
      </body>
    </html>
  );
}
