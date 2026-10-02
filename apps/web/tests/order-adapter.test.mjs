import assert from 'node:assert/strict';
import test from 'node:test';
import { adaptOrder } from '../lib/api.ts';

test('native bid precision and provider identity survive the API boundary', () => {
  const amount = '12345678901234567890.123456789012345678';
  const provenance = { tx_hash: 'ABC123', event_index: 4 };
  const result = adaptOrder({
    id: 'chain/owner/1/1/1',
    bids: [{ id: 'bid-1', provider_id: 'akash1address', provider_name: 'Readable name', native_price: amount, denom: 'uakt', price: null, created_height: 42, provenance, state: 'closed', is_winner: true }],
    leases: [{id: 'lease-1', provider_id: 'akash1address', winning_bid_price: amount, price_denom: 'uakt', created_height: 43, closed_at: '2026-09-30T00:00:00Z', provenance}],
  });
  assert.equal(result.bids[0].native_price, amount);
  assert.equal(result.bids[0].price_amount, null);
  assert.equal(result.bids[0].provider_id, 'akash1address');
  assert.equal(result.bids[0].provider_name, 'Readable name');
  assert.equal(result.bids[0].state, 'closed');
  assert.equal(result.bids[0].is_winner, true);
  assert.deepEqual(result.bids[0].provenance, provenance);
  assert.equal(result.leases[0].winning_bid_price, amount);
  assert.equal(result.leases[0].closed_at, '2026-09-30T00:00:00Z');
});

test('normalized demo prices never become fabricated native per-block prices', () => {
  const result = adaptOrder({id:'demo', bids:[{provider_id:'demo-provider', price:2.1, denom:'USD / bundle GPU-hour'}]});
  assert.equal(result.bids[0].price_amount, 2.1);
  assert.equal(result.bids[0].native_price, null);
  assert.equal(result.bids[0].created_height, null);
});
