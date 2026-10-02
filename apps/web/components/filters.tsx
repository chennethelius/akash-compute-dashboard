import type { Filters } from "@/lib/types";
export function FiltersBar({ filters }: { filters: Filters }) {
  return (
    <form className="filters">
      <label>
        GPU model · source ID
        <input
          name="gpu_model"
          list="gpu-model-suggestions"
          placeholder="All models"
          defaultValue={filters.gpu_model || ""}
          title="Exact source model identifier; model names are not fully normalized."
        />
        <datalist id="gpu-model-suggestions">
          <option value="p40" />
          <option value="rtx3090" />
          <option value="h100" />
          <option value="a100" />
          <option value="H100" />
          <option value="A100" />
        </datalist>
      </label>
      <label>
        From · UTC
        <input
          type="date"
          name="start"
          defaultValue={filters.start?.slice(0, 10) || ""}
        />
      </label>
      <label>
        Before · UTC
        <input
          type="date"
          name="end"
          defaultValue={filters.end?.slice(0, 10) || ""}
        />
      </label>
      <label>
        Region
        <input
          name="region"
          placeholder="All regions"
          defaultValue={filters.region || ""}
        />
      </label>
      <button type="submit">Apply filters</button>
    </form>
  );
}
