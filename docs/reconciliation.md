# Real Akash fixture reconciliation

The fixture in `backend/tests/fixtures/akash` contains unmodified public RPC responses from two bounded windows on `akashnet-2`: **28860258–28860263** and **28879940–28879992**. These are 59 block/result pairs, not a continuous range between the outermost heights. `manifest.json` records each response URL, SHA-256 file digest, download time, block hash and timestamp. Digests protect local fixture integrity; they do not independently verify consensus signatures or node honesty.

Endpoints were discovered through the [official network metadata](https://raw.githubusercontent.com/akash-network/net/main/mainnet/meta.json). Responses came from `https://rpc.akt.dev/rpc/block`, `/block_results`, and `https://rpc.akt.dev/rest/cosmos/tx/v1beta1/txs/{hash}`. Each block's height, chain, transaction count and corresponding execution-result height/count must reconcile before projection. The REST transaction JSON provides an independent rendering of resource messages for comparison with the raw protobuf decoder; it is still supplied by the same endpoint operator.

## Selected successful GPU auction

Order: `akashnet-2/akash10czfq8xx8nh92ue7svg4t5ffs0lhsd6rxeaqwe/1790795508665/1/1`.

- Created in height **28860258**, transaction index **3**, tx hash `8E111F6C5BC0B7812EDFCCB9E2F35CEAB1906B38BFF112FD804B47C96D7583CB`.
- Request: **1 NVIDIA RTX3090**, CPU **4000 millicores**, memory **17179869184 bytes**, storage **53687091200 bytes**, resource count **1**.
- Height **28860259**, tx index **0**: provider `akash1rja3y2ctj3tzmesvh0zfhzzx95rfjw405hwt8d` bids **282.496994000000000000 uact per block**.
- Height **28860259**, tx index **1**: provider `akash1p5qkxeu3hcxzx9nvfvva93pyvxcyqduly9udz9` bids **265.753915000000000000 uact per block**.
- Height **28860261**, tx index **0**: the latter provider wins at **265.753915000000000000 uact per block**. Bid sequence is **0**.

This selected order has two observed bidders and the cheaper bid wins. No selected lease close occurs in its six-block fixture. That means its close is outside observed coverage or had not occurred; it is not evidence of perpetual activity. Native amounts remain native; no USD or hourly conversion is asserted.

## Additional lifecycle evidence

The second interval includes a P40 request at **28879982** (tx index 0), owner `akash14n4rkmz64rn0tey0r5g07l8q5x0fh2h4hu44kt`, dseq `1790911986959`. It requests one GPU, 8000 CPU millicores, 68719476736 memory bytes and 64424509440 storage bytes. It closes at **28879991** with no bids or lease observed across its complete creation-to-close interval. It must not receive a fabricated winning price.

Other orders provide bid, lease and close events, including lease closes in **28879984**, bids in **28879947/28879963/28879974**, and leases in **28879968/28879980/28879989**. They include CPU-only orders and must not all be labeled GPU observations. Block **28879982** also contains a failed transaction at index **3** (code **5**), which must not create marketplace projections.

Typed event names use `akash.market.v1.Event*` and `akash.deployment.v1.Event*`; IDs and prices are JSON-encoded attribute values. Bid/lease IDs include `bseq`. Resource messages here use `/akash.deployment.v1beta4.MsgCreateDeployment`. These fixtures establish behavior for these versions only, not all historical Akash upgrades.

## Limits

This is a small, selected validation sample, unsuitable for market estimates or regressions. Inventory and exchange-rate observations are absent. Events referencing orders created outside either fixture interval are retained as evidence and must be marked incomplete rather than supplied with invented resources. This collection did not require a wallet, account credentials, chain transaction, or hosted database connection.
