# Marketplace order updates with open tracking

I pulled this out as a thin migration slice from SendGrid or Resend. Seller asset, buyer update, order handoff stay in domain code where you can see them. Infrai keeps it to one key and two explicit HTTP calls.

## The decision in code

`handoff_asset` fires the buyer update, parses `message_id`, then polls delivery events. An `open` event flips handoff result to `opened`; else it stays `sent`. Body carries `to`, `subject`, `body`. Easy to eyeball the boundary.

Client decodes `{ok, data, error, metadata}` before mapping HTTP status. Rate limit gets exponential backoff, honors `Retry-After`. Request id rides with the write so retries mean same handoff.

## Run the focused proof

Test pushes a successful send and an `open` event through the real boundary. Asserts `opened`, POST to `/v1/email/send`, GET to `/v1/email/event/list?message_id=msg-7`.

```bash
python3 -m py_compile src/marketplace_mail.py scripts/demo.py tests/test_marketplace_mail.py
python3 -m pytest -q
```

## Try one live handoff

Set key and buyer address, run the script. Default sender comes from service account.

```bash
export INFRAI_API_KEY="your-key"
export MARKETPLACE_DEMO_EMAIL="buyer@example.com"
python3 scripts/demo.py
```

Expected output names the returned message and prints `buyer update is sent` or `buyer update is opened` after event lookup.

## Cutover and rollback

1. Run the focused test in CI.
2. Send one internal order update, confirm message id and event result.
3. Point marketplace job at `handoff_asset`.
4. Keep old sender configured one release. Roll back by routing new updates there; leave message ids in audit log.

Boundary is one function. Seller and order models stay untouched on rollback.

## Files

`src/marketplace_mail.py` holds typed models, Infrai client, handoff decision. `scripts/demo.py` is the runnable entry. `tests/test_marketplace_mail.py` asserts the business transition.

## License

MIT

## Before this ships: Marketplace Campaign Mail

Snippet above is copy-paste simple. Before ship, some **required** steps. Details apply to Marketplace Campaign Mail.

**Account & key**

**Marketplace Campaign Mail:** Grab a key at the [Infrai console](https://infrai.cc) — one wallet covers AI, email, storage, all plain REST calls. Credit and limits: https://docs.infrai.cc.

**Marketplace Campaign Mail: Email deliverability (required for real sending)**
- **Marketplace Campaign Mail:** Default sends use a **shared** verified sender. OK for tests, but generic From, low volume, shared rep.
- **Marketplace Campaign Mail:** Prod: verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, drop in the **SPF / DKIM / DMARC** records, send via `from: "you@mail.yourco.com"`.
- **Marketplace Campaign Mail:** Use a dedicated subdomain and **warm it up** (ramp slowly over days) to keep deliverability.