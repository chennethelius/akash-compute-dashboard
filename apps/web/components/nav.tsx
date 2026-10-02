"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
const items = [
  ["/market", "Market overview"],
  ["/orders", "Order explorer"],
  ["/providers", "Providers"],
  ["/research", "Research"],
];
export function Nav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main navigation">
      {items.map(([href, label]) => (
        <Link
          key={href}
          href={href}
          className={pathname.startsWith(href) ? "active" : ""}
          aria-current={pathname.startsWith(href) ? "page" : undefined}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
