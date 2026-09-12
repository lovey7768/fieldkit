# FieldKit — Technical Assessment Responses

### 1. Webhook arrival while Postgres is down
The webhook intake endpoint operates independently of Postgres. When a webhook arrives, FastAPI verifies the HMAC signature in-memory using CPU-bound cryptographic operations. Idempotency is checked via Redis using an atomic `SET key val EX 86400 NX` command, and the validated event is pushed directly to a Redis Stream (`events:stream`). The API immediately returns `202 Accepted` to the sender. The background worker attempting to read the stream catches database connection exceptions, leaves messages unacknowledged in the Redis consumer group, and applies an exponential backoff sleep. Once Postgres recovers, the worker picks up where it left off with zero data loss and zero dropped requests.

### 2. HMAC signature verification vs. Secret URL tokens
Secret tokens in URLs leak through server access logs, browser histories, proxy caches, and TLS termination referer headers. They also provide no integrity protection: an attacker or an intermediary with a leaked URL can alter the payload undetected. HMAC-SHA256 signs the raw payload body using a shared secret key. This guarantees both authenticity (the sender holds the secret) and data integrity (tampered bytes yield a mismatched hash). It also protects against replay attacks when combined with an intake timestamp tolerance window.

### 3. Handling regex misses on international PII (+852 9XXX XXXX (Ms. Chan))
If a phone number like `+852 9XXX XXXX (Ms. Chan)` slips past regex matching, the raw phone number and personal name persist into the application logs and downstream event records. To catch this systematically, we implement three layers:
1. **Secondary Statistical NER:** A local, lightweight Named Entity Recognition model (e.g., HuggingFace Presidio or SpaCy) inspects text after regex execution to catch international naming and contact patterns.
2. **Canary Pattern Auditing:** Automated background tests continuously inject synthetic international test data to measure pattern coverage and flag regressions.
3. **Strict Column-Level Vault Isolation:** All unmasked payload storage is blocked by default; fields must be explicitly whitelisted before being marked as clean.

### 4. What breaks first at 100 simultaneous scans?
The primary bottleneck is the transmission of uncompressed base64 photo uploads from mobile devices. If 100 field workers submit photos at the same second over cellular connections, the network ingress bandwidth and FastAPI's in-memory body parsing can cause request timeouts and connection saturation. We would detect this early through Prometheus metrics on HTTP connection durations and Redis stream ingestion latency. To prevent this, client-side JavaScript resizes and compresses photos to WebP format before transmission, and large binary media is uploaded directly to S3-compatible object storage via pre-signed URLs, sending only the resulting media reference over the event stream.

### 5. Where AI tools got it wrong and how it was caught
AI code generators commonly generate HMAC verification using `request.json()` rather than the raw binary body (`request.body()`). JSON deserialization alters key ordering, formatting, and spacing, which causes HMAC validation to fail unpredictably across different clients. This was caught by running unit tests with distinct payloads and comparing verification results against canonical cryptographic test vectors. The implementation was corrected to verify raw binary bytes using `hmac.compare_digest` before any JSON parsing takes place.

### 6. What did you deliberately NOT build and why
We deliberately excluded full user authentication/RBAC and multi-step image OCR from the field page. Adding JWT authentication, session handling, and heavy client-side OCR libraries would add complexity that distracts from the core assessment requirements: proving deterministic HMAC verification, failure-resilient queueing, zero-loss offline sync, and strict PII isolation under real-world failure conditions.