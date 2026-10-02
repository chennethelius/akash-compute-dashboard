"""Deterministic, synthetic interface fixtures. Never persisted to research tables."""
from datetime import datetime, timedelta, timezone
from statistics import median

ANCHOR = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
PROVIDERS = [dict(id=f"demo-provider-{i}", name=name, region=region, gpu_model="H100", active_gpus=active, available_gpus=available, total_gpus=active+available, wins=4+i, bid_count=12+i*3, average_bid=2.1+i*.12, average_winning_price=1.9+i*.1, win_rate=(4+i)/(12+i*3), market_share=share, first_seen_at="2026-09-01T00:00:00Z", last_seen_at=ANCHOR.isoformat()) for i,(name,region,active,available,share) in enumerate([("Atlas Compute","us-east",24,8,.4),("Northstar GPUs","eu-west",18,6,.3),("Copper Cloud","us-west",12,8,.2),("Open Rack","us-east",6,4,.1)])]
ORDERS = []
OBSERVATIONS = []
for i in range(32):
    n = 1 + i % 4
    price = round(2.75 - n*.18 + (i%5)*.08, 3)
    provider = PROVIDERS[i%4]
    stamp = (ANCHOR-timedelta(hours=31-i)).isoformat()
    bids = [dict(id=f"demo-bid-{i}-{j}",provider_id=PROVIDERS[(i+j)%4]["id"],provider_name=PROVIDERS[(i+j)%4]["name"],price=round(price+j*.16,3),denom="USD / bundle GPU-hour",created_at=stamp,state="active",is_winner=j==0) for j in range(n)]
    market = dict(utilization=round(.52+(i%9)*.04,2),available_gpus=26-i%12,active_providers=4,provider_hhi=.3)
    ORDERS.append(dict(id=f"demo-order-{i+1:04d}",created_at=stamp,gpu_model="H100",gpu_count=1+i%2,cpu_units=8000,memory_bytes=64*1024**3,storage_bytes=200*1024**3,bid_count=n,lowest_bid=price,median_bid=median(b["price"] for b in bids),highest_bid=bids[-1]["price"],winner=provider["name"],region=provider["region"],bids=bids,market_at_order=market,attributes={"gpu_memory":"80Gi", "interface":"SXM"},provenance={"synthetic":True,"description":"Deterministic demonstration fixture, not Akash observations"}))
    OBSERVATIONS.append(dict(order_id=ORDERS[-1]["id"],timestamp=stamp,gpu_model="H100",region=provider["region"],bidder_count=n,winning_price=price,utilization=market["utilization"],provider_hhi=.3,bid_spread=round((n-1)*.16,3),available_gpus=market["available_gpus"]))
TIMESERIES = [dict(timestamp=(ANCHOR-timedelta(hours=23-i)).isoformat(),gpu_model="H100",median_price=round(2.2+(i%6)*.07,2),p10_price=1.8+(i%4)*.05,p90_price=2.9+(i%4)*.05,active_gpus=52+i%9,available_gpus=34-i%9,total_gpus=86,utilization=(52+i%9)/86,orders=1+i%4,leases=1+i%3,bidder_count=2+i%3,provider_hhi=.3) for i in range(24)]
