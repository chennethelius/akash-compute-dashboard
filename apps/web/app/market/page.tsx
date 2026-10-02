import { summary, timeseries, orders, num, pct, price, query } from "@/lib/api";
import type { Filters } from "@/lib/types";
import { Header, Status, Metric, Panel, Empty } from "@/components/common";
import { FiltersBar } from "@/components/filters";
import { Chart } from "@/components/chart";
export default async function Market({
  searchParams,
}: {
  searchParams: Promise<Filters>;
}) {
  const f = await searchParams;
  const [s, t, o] = await Promise.all([summary(f), timeseries(f), orders(f)]);
  const points = t.data || [];
  const labels = points.map((p) =>
    new Date(p.timestamp).toLocaleString("en-US", {
      timeZone: "UTC",
      month: "short",
      day: "numeric",
      hour: "2-digit",
    }),
  );
  const href = `/orders?${query(f)}`;
  const x = s.data;
  const counts = Array.from(
    { length: Math.max(1, ...(o.data || []).map((o) => o.bid_count)) + 1 },
    (_, i) => i,
  );
  return (
    <>
      <Header
        eyebrow="Market data"
        title="Market overview"
        description="Trace compute prices to competition, available supply, and the orders that formed them."
      />
      <Status result={s} />
      <FiltersBar filters={f} />
      <div className="metrics">
        <Metric
          label="Active GPUs"
          value={num(x?.active_gpu_count)}
          note="Reported allocated capacity"
        />
        <Metric
          label="Available GPUs"
          value={num(x?.available_gpu_count)}
          note="Reported unallocated capacity"
        />
        <Metric
          label="Estimated utilization"
          value={pct(x?.utilization)}
          note="Active / (active + available)"
        />
        <Metric
          label="Active providers"
          value={num(x?.provider_count)}
          note="Within observed coverage"
        />
        <Metric
          label="Orders · 24h"
          value={num(x?.orders)}
          note={`${num(x?.leases)} leases awarded`}
        />
        <Metric
          label="Median winning price"
          value={price(x?.median_price)}
          note="Bundle USD / GPU-hour"
        />
        <Metric
          label="Median bidders"
          value={num(x?.median_bidders_per_order, 1)}
          note="Distinct providers per order"
        />
        <Metric
          label="Provider HHI"
          value={num(x?.provider_hhi, 3)}
          note="Capacity shares · 0–1 scale"
        />
      </div>
      <div className="chart-grid market-charts">
        <Panel
          title="Winning price over time"
          subtitle="Bundle USD / GPU-hour · median, p10, p90"
          href={href}
        >
          {points.length ? (
            <Chart
              title="Winning price percentiles"
              labels={labels}
              series={["median_price", "p10_price", "p90_price"].map(
                (key, i) => ({
                  name: ["Median", "P10", "P90"][i],
                  values: points.map((p) => p[key as "median_price"]),
                }),
              )}
            />
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel
          title="Capacity over time"
          subtitle="Reported GPU counts · inventory observations"
          href={href}
        >
          {points.length ? (
            <Chart
              title="GPU capacity"
              labels={labels}
              series={[
                {
                  name: "Active",
                  values: points.map((p) => p.active_gpu_count),
                },
                {
                  name: "Available",
                  values: points.map((p) => p.available_gpu_count),
                },
                { name: "Total", values: points.map((p) => p.total_gpu_count) },
              ]}
            />
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel
          title="Estimated utilization"
          subtitle="Allocation proxy · does not measure GPU processing load"
          href={href}
        >
          {points.length ? (
            <Chart
              title="Utilization"
              percent
              labels={labels}
              series={[
                {
                  name: "Utilization",
                  values: points.map((p) => p.utilization),
                },
              ]}
            />
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel
          title="Bidder count distribution"
          subtitle="Orders grouped by distinct bidding providers · loaded sample"
          href={href}
        >
          {o.data?.length ? (
            <Chart
              bar
              title="Bidder count distribution"
              labels={counts.map(String)}
              series={[
                {
                  name: "Orders",
                  values: counts.map(
                    (n) => o.data.filter((o) => o.bid_count === n).length,
                  ),
                },
              ]}
            />
          ) : (
            <Empty />
          )}
        </Panel>
      </div>
      <div className="method-note">
        <strong>Read the evidence with its limits.</strong> Winning prices
        include the resource bundle. Capacity depends on provider reporting.
        Associations do not establish causal effects.
      </div>
    </>
  );
}
