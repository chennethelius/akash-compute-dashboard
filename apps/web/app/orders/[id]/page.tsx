import Link from "next/link";
import { orderDetail, num, pct, price } from "@/lib/api";
import { Header, Status, Panel, Metric, Empty } from "@/components/common";
export default async function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: routeId } = await params;
  // Encoded slashes stay escaped in Next route parameters. Decode once before the API adapter re-encodes the full identifier.
  const id = decodeURIComponent(routeId);
  const r = await orderDetail(id);
  const o = r.data;
  return (
    <>
      <Link href="/orders" className="back">
        ← Order explorer
      </Link>
      <Header
        eyebrow="ORDER / EVIDENCE"
        title="One order. Every bid."
        description={id}
      />
      <Status result={r} />
      {!o ? (
        <Empty message="This order is unavailable. Verify its identifier and API coverage." />
      ) : (
        <>
          <div className="metrics four">
            <Metric
              label="Requested GPU"
              value={`${num(o.gpu_count)} × ${o.gpu_model || "Unknown"}`}
              note="Requested capabilities"
            />
            <Metric
              label="CPU units / RAM"
              value={`${num(o.cpu_units)} / ${num(o.memory_bytes == null ? null : o.memory_bytes / 2 ** 30)} GiB`}
              note={`${num(o.storage_bytes == null ? null : o.storage_bytes / 2 ** 30)} GiB storage`}
            />
            <Metric
              label="Distinct bidders"
              value={num(o.bid_count)}
              note="Distinct providers in indexed bids"
            />
            <Metric
              label="Selected provider"
              value={o.winner || "Unawarded"}
              note="Buyer selection may differ from lowest bid"
            />
          </div>
          <Panel
            title="Bid timeline"
            subtitle="Every indexed bid. Native amounts are per-block bundle prices; USD is shown only when a validated normalization exists."
          >
            {o.bids?.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Provider</th>
                      <th>Native amount / block</th>
                      <th>Bundle USD / GPU-hour</th>
                      <th>Height</th>
                      <th>Timestamp · UTC</th>
                      <th>State / selection</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.bids.map((b, i) => (
                      <tr key={`${b.provider_id}-${i}`}>
                        <td>
                          {b.provider_name &&
                            b.provider_name !== b.provider_id && (
                              <strong>{b.provider_name}</strong>
                            )}
                          <span className="block mono">{b.provider_id}</span>
                        </td>
                        <td className="mono">
                          {b.native_price == null
                            ? "—"
                            : `${b.native_price} ${b.price_denom}`}
                        </td>
                        <td className="mono">{price(b.price_amount)}</td>
                        <td className="mono">{num(b.created_height)}</td>
                        <td>{new Date(b.created_at).toISOString()}</td>
                        <td>
                          <span className="badge">{b.state || "Unknown"}</span>
                          {b.is_winner && (
                            <span className="badge">Selected</span>
                          )}
                          {b.closed_at && (
                            <small className="block">
                              Closed {b.closed_at}
                            </small>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty message="No bids are indexed for this order." />
            )}
          </Panel>
          <Panel
            title="Lease lifecycle"
            subtitle="Observed lease creation and closure. Missing closure evidence does not establish current activity."
          >
            {o.leases?.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Lease / provider</th>
                      <th>Created height</th>
                      <th>Created · UTC</th>
                      <th>Closed · UTC</th>
                      <th>Native award / block</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.leases.map((lease) => (
                      <tr key={lease.id}>
                        <td>
                          <strong className="mono">{lease.id}</strong>
                          <span className="block mono">
                            {lease.provider_id}
                          </span>
                        </td>
                        <td className="mono">{num(lease.created_height)}</td>
                        <td>{new Date(lease.created_at).toISOString()}</td>
                        <td>
                          {lease.closed_at
                            ? new Date(lease.closed_at).toISOString()
                            : "No closure observed"}
                        </td>
                        <td className="mono">
                          {lease.winning_bid_price == null
                            ? "—"
                            : `${lease.winning_bid_price} ${lease.price_denom}`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty message="No lease lifecycle records are indexed for this order." />
            )}
          </Panel>
          <Panel
            title="Market preceding the order"
            subtitle="Only observations preceding the auction are eligible; unavailable measurements remain blank."
          >
            <div className="metrics four">
              <Metric
                label="Utilization"
                value={pct(o.market_at_order?.utilization)}
                note="Capacity allocation proxy"
              />
              <Metric
                label="Available GPUs"
                value={num(o.market_at_order?.available_gpu_count)}
                note="Within observation coverage"
              />
              <Metric
                label="Provider HHI"
                value={num(o.market_at_order?.provider_hhi, 3)}
                note="Capacity concentration"
              />
              <Metric
                label="Lowest bid"
                value={price(o.lowest_bid)}
                note="Normalized bundle USD / GPU-hour"
              />
            </div>
          </Panel>
          <Panel
            title="Source evidence"
            subtitle="Exact record evidence, including available transaction hashes and block heights. Unknown fields are not inferred."
          >
            <pre className="evidence">
              {JSON.stringify(
                {
                  order: {
                    id: o.order_id,
                    created_height: o.created_height ?? null,
                    created_at: o.created_at,
                    attributes: o.attributes || {},
                    provenance: o.provenance || {},
                  },
                  bids:
                    o.bids?.map((b) => ({
                      id: b.id,
                      provider_id: b.provider_id,
                      created_height: b.created_height,
                      native_price: b.native_price,
                      denom: b.price_denom,
                      provenance: b.provenance,
                    })) ?? [],
                  leases: o.leases ?? [],
                },
                null,
                2,
              )}
            </pre>
          </Panel>
        </>
      )}
    </>
  );
}
