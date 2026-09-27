---
name: testing-taniguard-runtime
description: Run TaniGuard browser tests with isolated simulated devices, optimizer timing fixtures, learning data and normal-speed demo evidence.
---

# TaniGuard runtime testing

## Environment
- Local Docker frontend: http://localhost:8080; API proxied under /api.
- Rebuild with `docker compose up -d --build frontend backend`.
- Apply schema migrations with `docker compose exec -T backend flask db upgrade`.
- Use dedicated local farmer/expert accounts and owned plots. Do not rely on seed plots remaining visible after ownership changes.
- Keep ordinary plot metadata separate from simulation labels: devices, readings, commands and scan history should carry simulation flags.
- When the scheduler is disabled, refresh simulated readings explicitly.

## Optimizer and learning fixtures
- Read config/optimizer.yaml and control.yaml before selecting fixtures. A valve and fresh moisture reading are needed for watering recommendations.
- Optimizer candidate hours may not include the current MYT hour. For deterministic Water now testing, temporarily change only `/srv/config/optimizer.yaml` inside the backend container, never production source; restart backend to clear cached configuration.
- Restore with `docker compose cp config/optimizer.yaml backend:/srv/config/optimizer.yaml`, restart backend, then compare host/container SHA256 checksums.
- Sufficient simulated learning history needs watering on at least 14 distinct days and at least 10 eligible scans per timing. Use two same-crop plots with contrasting timing outcomes.
- Learning effects describe association, not causality. Preserve the simulated-history disclaimer in evidence.
- Check request, confirm, cancel and schedule save against the separate Controls list without a browser reload.
- Test direct expert-to-farmer switching with a previously visible other-owner plot. Explicitly clear login fields before entering credentials.

## Evidence
- Capture visible cards, learned reason, score effects and harvest comparison before and after a valid submission.
- Physical hardware, scheduled execution and causal agronomic validity require separate testing.
- The recording tool automatically compresses its edited/clean outputs. For narration-ready 1x video, concatenate the original raw MKV segments without time scaling, export MP4 and verify duration with ffprobe.
- Build segment timestamps from source annotations, then spot-check actual frames in the final MP4.

## Devin Secrets Needed
- None for isolated local accounts created with the Flask CLI. Never reuse local QA credentials for production.
