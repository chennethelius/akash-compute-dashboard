import type { Filters } from "@/lib/types";
export function FiltersBar({ filters }: { filters: Filters }) {
  return (
    <form className="filters">
      <label>
        GPU MODEL
        <select name="gpu_model" defaultValue={filters.gpu_model || ""}>
          <option value="">All models</option>
          <option>H100</option>
          <option>A100</option>
          <option>A6000</option>
          <option>RTX 4090</option>
        </select>
      </label>
      <label>
        FROM · UTC
        <input
          type="date"
          name="start"
          defaultValue={filters.start?.slice(0, 10) || ""}
        />
      </label>
      <label>
        BEFORE · UTC
        <input
          type="date"
          name="end"
          defaultValue={filters.end?.slice(0, 10) || ""}
        />
      </label>
      <label>
        REGION
        <input
          name="region"
          placeholder="All regions"
          defaultValue={filters.region || ""}
        />
      </label>
      <button type="submit">
        Apply filters <span>↗</span>
      </button>
    </form>
  );
}
