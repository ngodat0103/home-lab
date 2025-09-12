# Kubernetes Safe Shutdown with Longhorn & Controller Awareness

## Problem
- **Problem:** Need to shut down a Kubernetes cluster **safely** with Longhorn storage to avoid **data loss**, **replica desync**, or **stuck volumes/pods**.
- **Scope:** One K8s cluster (multi-node) with Longhorn; script triggered manually (one-shot runbook) but extendable to automation/CI. Out-of-scope: restart, cleanup, upgrade.

## Goals / Guardrails
- **KPI/SLO:**
  - 0 Longhorn volumes left `attached` (SLO 100%).
  - 0 pods on node after drain (SLO 100%).
  - Target shutdown time: ≤15min for ≤10 nodes, ≤60min for ≤50 nodes.
  - 0 new degraded volumes after shutdown.
- **Budget:** Use existing tools (kubectl, Longhorn API/CRD, SSH).
- **Compliance:** Graceful termination, data integrity, audit logs, DR policy (RPO ~0, RTO not bound).

## Constraints
- **Infra:** Linux nodes (systemd), stable internal network; `kubectl` installed; Longhorn CRDs ready.
- **Security/Access:** `cluster-admin`; CRUD on Longhorn CRD; SSH keys for nodes if needed.
- **Versions:** K8s 1.24–1.30; Longhorn 1.4+.
- **Data:** Mainly RWO volumes; RWX ignored for shutdown logic.
- **People:** 1 DRI operator; notify DevOps/QA/PO teams.

## Assumptions & Unknowns
- **Assumptions:**
  - Longhorn healthy (manager pods Running).
  - Valid kubeconfig context.
  - PDBs reasonable.
- **Unknowns (spike tests):**
  1. Behavior of detach while rebuilding volume → spike test detach under rebuild.
  2. Behavior of draining critical pods (DaemonSet, system pods) → spike test drain staging node.

## Options
1. **Baseline:** Pure kubectl cordon/drain, rely on auto detach.
2. **Safe (recommended):** Explicit Longhorn API detach before drain.
3. **Ambitious:** Orchestrator with state machine, observability, rollback.

### Trade-offs
| Option | Cost | Risk | TTM | Complexity | Operability |
|---|---|---|---|---|---|
| Baseline | Low | Medium | Fast | Low | Medium |
| Safe | Low-Mid | Low | Medium | Medium | High |
| Ambitious | Mid-High | Low | Slow | High | Very high |

## Failure Modes
- **Detach timeout** → workload failure; mitigate retry/backoff, runbook check logs.
- **Drain stuck due PDB** → mitigate wait/force-evict with approval.
- **Longhorn manager down** → abort early; runbook restore Longhorn first.
- **Network partition** → limit blast radius, isolate faulty node.
- **Wrong context** → preflight check `kubectl cluster-info` sentinel.
- **Script crash** → checkpoint, idempotent resume.
- **Argo CD resync** → resources scaled back up; mitigate by pausing automation or ignoring replicas diffs.
- **Other operators (Prometheus, Loki, ECK, Strimzi, etc.)** → reconcile CRs back; mitigate by patching top-level CRs or scaling operator deployments.

## Plan
- **Milestones:** Preflight → Safe shutdown flow → Timeouts/backoff → Observability → Dry-run → Staging → Prod.
- **Order:** Workers → Control-plane last.
- **DRI:** DevOps team.
- **Communication:** T-30’ Slack/Email notify; update on start/end/rollback.

## Observability-first
- **Logs:** Structured JSON per step with IDs, saved to file.
- **Metrics:** pod_evicted_total, volumes_detached_total, step_duration_seconds; optional Prometheus Pushgateway.
- **Tracing:** optional spans per node/volume.
- **Alerts:** timeout detach/drain, Longhorn unhealthy, API errors.
- **Release criteria:** 100% volumes detached + 100% nodes drained.
- **Rollback criteria:** timeout exceeded or volumes stuck >N.

## Execution Flow
1. **Preflight:** verify context, CRDs, nodes Ready, log inventory.
2. **App quiesce hooks (optional).**
3. **Controller-aware scale-down:**
   - Detect Argo CD owners → pause/ignore replicas before scaling.
   - Detect Prometheus Operator CRs (Prometheus/Alertmanager/ThanosRuler) → patch `spec.replicas=0` or scale operator deployment.
   - Detect other operators (Loki, ECK, Strimzi, Flux, etc.) → patch CRs or pause operator.
4. **Workers:** cordon, detach volumes, drain, verify.
5. **Control-plane:** same but API-server last.
6. **Finalize:** restore controllers, report + metrics + notify.

## Interfaces & Tech
- **Language:** Python 3.10+.
- **Libs:** kubernetes, requests (Longhorn REST), tenacity, typer/click, loguru, pyyaml.
- **CLI args:** --dry-run, --context, --node-selector, --timeout, --force-evict-pdb, --pushgateway-url.
- **Idempotency:** checkpoint file for resume.

## Security
- No secret logs; redact sensitive fields.
- Prefer K8s API, fallback SSH.
- Cluster-admin needed for drain.
## Deliverables
- `k8s-safe-shutdown.py` + `requirements.txt`.
- `RUNBOOK.md`, `OBSERVABILITY.md`, `ADR-0001.md`, `POSTMORTEM.md`.