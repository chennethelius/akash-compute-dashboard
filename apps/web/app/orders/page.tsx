import { orders, query } from "@/lib/api";
import type { Filters } from "@/lib/types";
import { Header, Status, Panel, OrderTable } from "@/components/common";
import { FiltersBar } from "@/components/filters";
export default async function Orders({
  searchParams,
}: {
  searchParams: Promise<Filters>;
}) {
  const f = await searchParams;
  const r = await orders(f);
  return (
    <>
      <Header
        eyebrow="Transactions"
        title="Order explorer"
        description="Follow each resource request through its bids and provider selection."
      />
      <Status result={r} />
      <FiltersBar filters={f} />
      <div className="section-toolbar">
        <span>{r.data?.length || 0} orders in loaded sample</span>
        <a className="export" href={`/api/export?${query(f)}`}>
          Export CSV ↓
        </a>
      </div>
      <Panel
        title="Order explorer"
        subtitle="Normalized prices: bundle USD / GPU-hour. Unknown prices remain blank."
      >
        <OrderTable rows={r.data || []} />
      </Panel>
    </>
  );
}
