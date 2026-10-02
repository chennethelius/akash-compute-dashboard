import Link from "next/link";
import { num, price, type Result } from "@/lib/api";
import type { Order } from "@/lib/types";
export function Header({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="page-header">
      <div className="eyebrow">{eyebrow}</div>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
export function Status({ result }: { result: Result<unknown> }) {
  return (
    <div className={`status ${result.error ? "failure" : ""}`}>
      <div>
        <strong>
          {result.error
            ? "Data temporarily unavailable"
            : result.meta.mode === "demo"
              ? "Synthetic demo · Not market evidence"
              : result.meta.label}
        </strong>
        <span>
          {result.error
            ? "The data source could not be reached. Please try again shortly; no substitute observations are shown."
            : result.meta.coverage_note}
        </span>
      </div>
      {result.meta.as_of && (
        <time>
          As of{" "}
          {new Date(result.meta.as_of).toLocaleString("en-US", {
            timeZone: "UTC",
          })}{" "}
          UTC
        </time>
      )}
    </div>
  );
}
export function Empty({
  message = "No observations match this selection. Try another date range or model.",
}: {
  message?: string;
}) {
  return (
    <div className="empty">
      <h3>No observations yet</h3>
      <p>{message}</p>
    </div>
  );
}
export function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{note}</div>
    </div>
  );
}
export function Panel({
  title,
  subtitle,
  children,
  href,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  href?: string;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {href && <Link href={href}>Inspect orders</Link>}
      </div>
      {children}
    </section>
  );
}
export function OrderTable({ rows }: { rows: Order[] }) {
  return rows.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {[
              "Created · UTC",
              "Order",
              "GPU / qty",
              "CPU units / RAM / disk",
              "Bidders",
              "Low / median / high",
              "Selected provider",
            ].map((s) => (
              <th key={s}>{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((o) => (
            <tr key={o.order_id}>
              <td>
                {new Date(o.created_at).toLocaleString("en-US", {
                  timeZone: "UTC",
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </td>
              <td>
                <Link
                  className="mono accent"
                  href={`/orders/${encodeURIComponent(o.order_id)}`}
                >
                  {o.order_id.slice(-22)}
                </Link>
              </td>
              <td>
                <span className="badge">{o.gpu_model || "Unknown"}</span> ×{" "}
                {num(o.gpu_count)}
              </td>
              <td>
                {num(o.cpu_units)} /{" "}
                {num(o.memory_bytes == null ? null : o.memory_bytes / 2 ** 30)}{" "}
                GiB /{" "}
                {num(
                  o.storage_bytes == null ? null : o.storage_bytes / 2 ** 30,
                )}{" "}
                GiB
              </td>
              <td>{o.bid_count}</td>
              <td className="mono">
                {price(o.lowest_bid)} / {price(o.median_bid)} /{" "}
                {price(o.highest_bid)}
              </td>
              <td className="truncate">{o.winner || "Unawarded"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty />
  );
}
