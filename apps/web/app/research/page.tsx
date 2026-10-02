import { observations, query } from "@/lib/api";
import type { Filters, Observation } from "@/lib/types";
import { Header, Status, Panel, Empty } from "@/components/common";
import { FiltersBar } from "@/components/filters";
import { Chart } from "@/components/chart";
export default async function Research({
  searchParams,
}: {
  searchParams: Promise<Filters>;
}) {
  const f = await searchParams;
  const r = await observations(f);
  const rows = r.data || [];
  const charts: {
    title: string;
    hypothesis: string;
    x: keyof Observation;
    y: keyof Observation;
  }[] = [
    {
      title: "Winning price vs. bidder count",
      hypothesis: "H1 · Does increased competition correspond to lower prices?",
      x: "bidder_count",
      y: "winning_price",
    },
    {
      title: "Winning price vs. utilization",
      hypothesis: "H2 · Is there a scarcity premium near capacity constraints?",
      x: "utilization",
      y: "winning_price",
    },
    {
      title: "Bid dispersion vs. utilization",
      hypothesis: "H5 · Do bids diverge as available supply tightens?",
      x: "utilization",
      y: "bid_spread",
    },
    {
      title: "Winning price vs. concentration",
      hypothesis: "H3 · Does concentration correspond to higher prices?",
      x: "provider_hhi",
      y: "winning_price",
    },
  ];
  return (
    <>
      <Header
        eyebrow="04 / RESEARCH"
        title="Questions first. Evidence next."
        description="Explore competing explanations for price formation. Each point links to its underlying order."
      />
      <Status result={r} />
      <FiltersBar filters={f} />
      <div className="research-note">
        <span className="badge">EXPLORATORY</span>
        <p>
          These are descriptive associations. Hardware, location, resource
          bundles, and selection effects can confound comparisons. No causal
          estimates or predictive models are presented.
        </p>
      </div>
      <div className="chart-grid">
        {charts.map((c) => {
          const eligible = rows.filter((o) => o[c.x] != null && o[c.y] != null);
          return (
            <Panel
              key={c.title}
              title={c.title}
              subtitle={c.hypothesis}
              href={`/orders?${query(f)}`}
            >
              {eligible.length ? (
                <>
                  <Chart
                    title={c.title}
                    orderIds={eligible.map((o) => o.order_id)}
                    scatter={[
                      {
                        name: "Order observation",
                        points: eligible.map((o) => [
                          o[c.x] as number,
                          o[c.y] as number,
                        ]),
                      },
                    ]}
                  />
                  <div className="chart-caption">
                    x:{" "}
                    {c.x === "utilization"
                      ? "allocation ratio (0–1)"
                      : c.x === "provider_hhi"
                        ? "HHI (0–1)"
                        : "distinct providers"}{" "}
                    · y: bundle USD / GPU-hour · n = {eligible.length}
                  </div>
                </>
              ) : (
                <Empty message="Matched price and market observations are required for this comparison." />
              )}
            </Panel>
          );
        })}
      </div>
      <div className="method-note">
        <strong>H4 · Provider entry</strong> Event studies require a verified
        entry date, sufficient observations before and after entry, and a
        comparison cohort. This analysis will follow validated historical
        coverage.
      </div>
    </>
  );
}
