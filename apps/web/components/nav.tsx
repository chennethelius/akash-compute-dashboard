"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
export function Nav() {
  const path = usePathname();
  return (
    <nav>
      {[
        ["/market", "01", "Market overview"],
        ["/orders", "02", "Order explorer"],
        ["/providers", "03", "Providers"],
        ["/research", "04", "Research"],
      ].map(([href, n, label]) => (
        <Link
          className={path.startsWith(href) ? "active" : ""}
          href={href}
          key={href}
        >
          <span>{n}</span>
          {label}
        </Link>
      ))}
    </nav>
  );
}
