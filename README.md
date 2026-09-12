# ⚡ FieldKit — Resilient Field Operations Platform

[![CI Pipeline](https://github.com/YOUR_USERNAME/fieldkit/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/fieldkit/actions)
[![Python Version](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

FieldKit is an event-driven edge platform built for field service crews and back-office ERP synchronization. Built with **FastAPI**, **PostgreSQL**, **Redis Streams**, and **offline-first PWA technologies**, it handles high-throughput inbound webhooks, provides cryptographic HMAC verification, performs reversible PII masking, coordinates offline field submissions, and ensures zero-loss ERP sync with automatic dead-letter queueing.

---

## 🏛️ System Architecture

```text
                                  ┌─────────────────────────────────────────┐
                                  │      Client / Mobile PWA (Field)        │
                                  │  • Camera Barcode / QR Scanner          │
                                  │  • Photo Capture & Local Compression    │
                                  │  • IndexedDB Offline Queue Auto-Flush   │
                                  └────────────────────┬────────────────────┘
                                                       │ HTTPS (client_uuid)
                                                       ▼
┌───────────────────────────┐         ┌─────────────────────────────────────┐
│  External Event Provider  │────────►│        FastAPI Ingestion Node       │
│  (X-Signature-256: HMAC)  │         │  1. Raw Byte HMAC-SHA256 Auth       │
└───────────────────────────┘         │  2. Redis SETNX Atomic Deduplication│
                                      │  3. Redis Stream Dispatch (XADD)    │
                                      └──────────────────┬──────────────────┘
                                                         │
                                                         ▼
                                      ┌─────────────────────────────────────┐
                                      │            Redis Stream             │
                                      │         key: events:stream          │
                                      └──────────────────┬──────────────────┘
                                                         │
                                                         ▼
                                      ┌─────────────────────────────────────┐
                                      │     Distributed Background Worker   │
                                      │  • Reversible PII Masking Engine    │
                                      │  • AI Intent Classification (LLM)   │
                                      │  • PostgreSQL Atomic Persistence    │
                                      │  • Outbound ERP Sync + Backoff/DLQ  │
                                      └──────────┬────────────────┬─────────┘
                                                 │                │
                        ┌────────────────────────┘                └────────────────────────┐
                        ▼                                                                  ▼
          ┌───────────────────────────┐                                      ┌───────────────────────────┐
          │     PostgreSQL Storage    │                                      │    Mock ERP REST Service  │
          │  • `events` (Masked)      │                                      │  • Bearer Token Auth      │
          │  • `pii_vault` (Encrypted)│                                      │  • Auto-DLQ Routing on    │
          │  • `dead_letter_events`   │                                      │    Terminal Retries       │
          │  • `ai_reviews` (Pending) │                                      └───────────────────────────┘
          └───────────────────────────┘


