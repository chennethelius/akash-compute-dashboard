import { providers, num, pct } from "@/lib/api";
import type { Filters } from "@/lib/types";
import { Header, Status, Panel, Empty } from "@/components/common";
import { FiltersBar } from "@/components/filters";
import { Chart } from "@/components/chart";
export default async function Providers({
  searchParams,
}: {
  searchParams: Promise<Filters>;
}) {
  const f = await searchParams;
  const r = await providers(f);
  const rows = r.data || [];
  return (
    <>
      <Header
        eyebrow="03 / PROVIDERS"
        title="Who supplies the market?"
        description="Compare provider participation, allocated capacity, and award concentration."
      />
      <Status result={r} />
      <FiltersBar filters={f} />
      <div className="chart-grid">
        <Panel
          title="Provider market share"
          subtitle="Award share within the selected cohort"
        >
          {rows.length ? (
            <Chart
              bar
              title="Provider market share"
              percent
              labels={rows.map((p) => p.provider_name || p.provider_id)}
              series={[
                { name: "Share", values: rows.map((p) => p.market_share) },
              ]}
            />
          ) : (
            <Empty />
          )}
        </Panel>
        <Panel
          title="GPU capacity by provider"
          subtitle="Latest observed active and available inventory"
        >
          {rows.length ? (
            <Chart
              bar
              title="Capacity by provider"
              labels={rows.map((p) => p.provider_name || p.provider_id)}
              series={[
                { name: "Active", values: rows.map((p) => p.gpu_count_active) },
                {
                  name: "Available",
                  values: rows.map((p) => p.gpu_count_available),
                },
              ]}
            />
          ) : (
            <Empty />
          )}
        </Panel>
      </div>
      <Panel
        title="Provider directory"
        subtitle="First and last seen describe observations; a missing snapshot does not establish exit."
      >
        {rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "Provider",
                    "Region",
                    "Active / available",
                    "Bids",
                    "Wins",
                    "Win rate",
                    "First seen",
                    "Last seen",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.provider_id}>
                    <td>
                      <strong>{p.provider_name || p.provider_id}</strong>
                      <small className="block mono">{p.provider_id}</small>
                    </td>
                    <td>{p.region || "Unknown"}</td>
                    <td>
                      {num(p.gpu_count_active)} / {num(p.gpu_count_available)}
                    </td>
                    <td>{num(p.bid_count)}</td>
                    <td>{num(p.wins)}</td>
                    <td>{pct(p.win_rate)}</td>
                    <td>{p.first_seen_at?.slice(0, 10) || "—"}</td>
                    <td>{p.last_seen_at?.slice(0, 10) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty />
        )}
      </Panel>
    </>
  );
}
