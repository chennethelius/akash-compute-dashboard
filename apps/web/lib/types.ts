export type Filters = {
  gpu_model?: string;
  start?: string;
  end?: string;
  region?: string;
};
export type Order = {
  provenance?: Record<string, unknown>;
  attributes?: Record<string, unknown>;
  created_height?: number | null;
  order_id: string;
  created_at: string;
  gpu_model: string | null;
  gpu_count: number | null;
  cpu_units: number | null;
  memory_bytes: number | null;
  storage_bytes: number | null;
  bid_count: number;
  lowest_bid: number | null;
  median_bid: number | null;
  highest_bid: number | null;
  winner: string | null;
  price_denom?: string;
  bids?: {
    id?: string;
    provider_id: string;
    provider_name: string | null;
    native_price: string | null;
    price_amount: number | null;
    price_denom: string;
    created_at: string;
    created_height: number | null;
    closed_at?: string | null;
    state: string;
    is_winner: boolean;
    provenance: Record<string, unknown>;
  }[];
  leases?: {
    id: string;
    provider_id: string;
    created_height: number | null;
    created_at: string;
    closed_at: string | null;
    winning_bid_price: string | null;
    price_denom: string;
    provenance: Record<string, unknown>;
  }[];
  market_at_order?: {
    utilization: number | null;
    available_gpu_count: number | null;
    provider_hhi: number | null;
  };
};
export type Point = {
  timestamp: string;
  median_price: number | null;
  p10_price: number | null;
  p90_price: number | null;
  active_gpu_count: number | null;
  available_gpu_count: number | null;
  total_gpu_count: number | null;
  utilization: number | null;
  orders: number;
  leases: number;
  provider_hhi: number | null;
};
export type Summary = {
  active_gpu_count: number | null;
  available_gpu_count: number | null;
  utilization: number | null;
  provider_count: number | null;
  orders: number;
  leases: number;
  median_price: number | null;
  median_bidders_per_order: number | null;
  provider_hhi: number | null;
};
export type Provider = {
  provider_id: string;
  provider_name: string | null;
  region: string | null;
  bid_count: number;
  wins: number;
  win_rate: number | null;
  gpu_count_active: number | null;
  gpu_count_available: number | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  market_share: number | null;
};
export type Observation = {
  order_id: string;
  gpu_model: string | null;
  bidder_count: number;
  winning_price: number | null;
  utilization: number | null;
  provider_hhi: number | null;
  bid_spread: number | null;
};
