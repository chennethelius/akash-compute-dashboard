import Link from "next/link";
import { orderDetail, num, pct, price } from "@/lib/api";
import { Header, Status, Panel, Metric, Empty } from "@/components/common";
export default async function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
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
              note="Observed before selection"
            />
            <Metric
              label="Selected provider"
              value={o.winner || "Unawarded"}
              note="Buyer selection may differ from lowest bid"
            />
          </div>
          <Panel
            title="Bid timeline"
            subtitle="Raw bid amount and denomination retained; compare only compatible units."
          >
            {o.bids?.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Provider</th>
                      <th>Amount</th>
                      <th>Denomination</th>
                      <th>Timestamp · UTC</th>
                      <th>State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.bids.map((b, i) => (
                      <tr key={`${b.provider_id}-${i}`}>
                        <td>{b.provider_id}</td>
                        <td className="mono">{num(b.price_amount, 6)}</td>
                        <td>{b.price_denom}</td>
                        <td>{new Date(b.created_at).toISOString()}</td>
                        <td>
                          <span className="badge">{b.state}</span>
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
            subtitle="Requested attributes and record provenance"
          >
            <pre className="evidence">
              {JSON.stringify(
                {
                  attributes: o.attributes || {},
                  provenance: o.provenance || {},
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
