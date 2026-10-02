import Link from "next/link";
export default function NotFound() {
  return (
    <section className="empty">
      <h1>Page not found</h1>
      <p>This address does not match a research view.</p>
      <Link href="/market" className="back">
        Return to market overview
      </Link>
    </section>
  );
}
