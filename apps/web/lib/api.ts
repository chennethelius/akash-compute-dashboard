import type {
  Filters,
  Order,
  Point,
  Provider,
  Observation,
  Summary,
} from "./types";
export type Meta = {
  mode: "demo" | "live";
  label: string;
  as_of: string | null;
  coverage_note: string;
};
export type Result<T> = { meta: Meta; data: T; error?: string };
type Raw = Record<string, any>; // Transport fields are adapted at this boundary.
export function query(filters: Filters) {
  return new URLSearchParams(
    Object.entries(filters)
      .filter(([, v]) => !!v)
      .map(([k, v]) => [
        k,
        (k === "start" || k === "end") && /^\d{4}-\d{2}-\d{2}$/.test(v || "")
          ? `${v}T00:00:00Z`
          : v,
      ]) as [string, string][],
  ).toString();
}
async function get(path: string, filters: Filters = {}): Promise<Result<any>> {
  try {
    const response = await fetch(
      `${process.env.API_BASE_URL || "http://localhost:8000"}/v1/${path}?${query(filters)}`,
      { cache: "no-store", signal: AbortSignal.timeout(8000) },
    );
    if (!response.ok) throw new Error(`API returned ${response.status}`);
    const body = await response.json();
    if (!body.meta || !("data" in body))
      throw new Error("Unexpected API response");
    return body;
  } catch (error) {
    return {
      meta: {
        mode: "live",
        label: "Source unavailable",
        as_of: null,
        coverage_note: "No observations loaded.",
      },
      data: null,
      error: error instanceof Error ? error.message : "Could not reach the API",
    };
  }
}
function map<T>(result: Result<any>, adapt: (raw: any) => T): Result<T> {
  return {
    ...result,
    data: result.data === null ? (null as T) : adapt(result.data),
  };
}
export const adaptOrder = (o: Raw): Order =>
  ({
    ...o,
    order_id: o.id,
    winner: o.winner,
    bids: o.bids?.map((b: Raw) => ({
      id: b.id,
      provider_id: b.provider_id,
      provider_name: b.provider_name ?? null,
      native_price: b.native_price == null ? null : String(b.native_price),
      price_amount: b.price ?? null,
      price_denom: b.denom,
      created_at: b.created_at,
      created_height: b.created_height ?? null,
      closed_at: b.closed_at ?? null,
      state: b.state,
      is_winner: b.is_winner ?? false,
      provenance: b.provenance ?? {},
    })),
    leases: o.leases?.map((lease: Raw) => ({
      ...lease,
      winning_bid_price:
        lease.winning_bid_price == null
          ? null
          : String(lease.winning_bid_price),
      provenance: lease.provenance ?? {},
    })),
    market_at_order: o.market_at_order
      ? {
          ...o.market_at_order,
          available_gpu_count: o.market_at_order.available_gpus,
        }
      : undefined,
  }) as Order;
export async function summary(f: Filters) {
  return map<Summary>(await get("market/summary", f), (s: Raw) => ({
    active_gpu_count: s.active_gpus,
    available_gpu_count: s.available_gpus,
    utilization: s.utilization,
    provider_count: s.active_providers,
    orders: s.orders_24h,
    leases: s.leases_24h,
    median_price: s.median_winning_price,
    median_bidders_per_order: s.median_bidders_per_order,
    provider_hhi: s.provider_hhi,
  }));
}
export async function timeseries(f: Filters) {
  return map<Point[]>(await get("market/timeseries", f), (rows: Raw[]) =>
    rows.map(
      (p) =>
        ({
          ...p,
          active_gpu_count: p.active_gpus,
          available_gpu_count: p.available_gpus,
          total_gpu_count: p.total_gpus,
        }) as Point,
    ),
  );
}
export async function orders(f: Filters) {
  return map<Order[]>(await get("orders", f), (rows: Raw[]) => rows.map(adaptOrder));
}
export async function orderDetail(id: string) {
  return map<Order>(await get(`orders/${encodeURIComponent(id)}`), adaptOrder);
}
export async function providers(f: Filters) {
  return map<Provider[]>(await get("providers", f), (rows: Raw[]) =>
    rows.map(
      (p) =>
        ({
          ...p,
          provider_id: p.id,
          provider_name: p.name,
          gpu_count_active: p.active_gpus,
          gpu_count_available: p.available_gpus,
        }) as Provider,
    ),
  );
}
export async function observations(f: Filters) {
  return get("research/observations", f) as Promise<Result<Observation[]>>;
}
export function num(value: number | null | undefined, digits = 0) {
  return value == null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(
        value,
      );
}
export function pct(value: number | null | undefined) {
  return value == null ? "—" : `${num(value * 100, 1)}%`;
}
export function price(value: number | null | undefined) {
  return value == null ? "—" : `$${num(value, 2)}`;
}
