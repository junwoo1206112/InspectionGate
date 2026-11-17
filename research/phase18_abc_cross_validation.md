# Phase 18 A/B/C 교차검증 — Redis 옵션 분산 상태·2개 컨테이너 smoke

검토일: 2026-11-09. 목표는 SQLite 기본 경로를 유지하면서 **Redis를 선택적 분산 상태 백엔드**로 추가하고, 한 Docker Desktop 호스트에서 **두 앱 컨테이너가 Redis를 공유**해 예측·멱등 검토·대기열이 이어지는지 실제로 검증하는 것이다. 진짜 다중 호스트 일관성이나 운영 배포·보안 인증은 주장하지 않는다.

## 세 관점

- **A. 분산 상태**: predictions와 idempotency를 Redis에 저장하면 서로 다른 컨테이너/프로세스가 같은 상태를 본다. 한 컨테이너에서 `/predict`로 만든 예측을 다른 컨테이너에서 `/review`·`/audit`·목록 조회로 이어갈 수 있어야 한다. Redis TTL은 idempotency key 만료에 사용한다.
- **B. 컨테이너·보안**: 두 앱 컨테이너는 `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, 비root `app` 사용자, `/tmp` tmpfs에 감사 로그를 쓴다. Redis 컨테이너는 `redis` 사용자, read-only rootfs, cap-drop ALL, no-new-privileges, 영속화 비활성으로 실행한다. smoke는 상태 공유와 보안 설정을 `docker inspect`로 기록한다.
- **C. 정직성**: 두 컨테이너는 **한 호스트**에 있고 다중 호스트가 아니다. Redis는 단일 인스턴스이며 고가용성·복제·장애 조치·이미지 취약점 스캔·비밀 관리·규제 준수를 검증하지 않는다. SQLite는 로컬 단일 검토자 기본값으로 유지한다.

## 교차검증 결론

| 결정 | A | B | C | 채택 |
| --- | --- | --- | --- | --- |
| 백엔드 | 공유 상태 | optional Redis | SQLite 기본 유지 | `INSPECTION_GATE_REDIS_URL` |
| 원자성 | 중복 확정 방지 | WATCH/MULTI | 분산 보장 아님 | `RedisStore.finalize` |
| TTL | 키 만료 | Redis EX | 운영 정책 아님 | ttl_seconds |
| 검증 | 두 컨테이너 | 같은 네트워크 | 한 호스트 명시 | `scripts/redis_smoke.py` |
| 보안 | 비root·최소 권한 | read-only/cap-drop | 인증 아님 | inspect 기록 |
| 범위 | 로컬 | Docker Desktop | 다중 호스트 아님 | 한계 명시 |

## 외부 근거

- [Redis transactions (WATCH/MULTI)](https://redis.io/docs/latest/develop/using-commands/transactions/)
- [Redis EXPIRE / TTL](https://redis.io/docs/latest/commands/expire/)
- [Docker run security options](https://docs.docker.com/reference/cli/docker/container/run/#security-opt)
- [Docker read-only root filesystem](https://docs.docker.com/reference/cli/docker/container/run/#read-only)

## 저장소 근거

- `inspection_gate/redis_store.py`, `inspection_gate/domain.py`, `app.py`
- `scripts/redis_smoke.py`, `artifacts/redis-smoke/redis_smoke_report.json`
- `tests/test_redis_store.py`, `tests/test_redis_smoke_contract.py`

## 실행 결과

- Redis `7.4.12`, `redis:7-alpine`, 한 Docker Desktop 호스트.
- 앱 컨테이너 A `/predict` 200 → 컨테이너 B `/review` 200(FINALIZED) → B `/audit` `PREDICTION_CREATED`,`REVIEW_FINALIZED` → A `/predictions?status=FINALIZED` 포함.
- 같은 `Idempotency-Key` 재시도 B 200(FINALIZED), 다른 payload 409.
- 보안 inspect: app 컨테이너 `user=app`, `CapDrop=ALL`, `ReadonlyRootfs=true`, `SecurityOpt=no-new-privileges`, `/tmp` tmpfs; Redis `user=redis`, read-only, cap-drop ALL.
- 보고서: `artifacts/redis-smoke/redis_smoke_report.json`.
- 전체 테스트: `python -m pytest -q` → `159 passed, 1 skipped`.

## 한계

다중 호스트·Redis Cluster/Sentinel·고가용성·장애 조치·백업·TLS/인증·이미지 취약점 스캔·비밀 관리·규제 준수는 미검증이다. 두 컨테이너 smoke는 로컬 Docker Desktop 한 호스트의 분산 상태 동작 증거일 뿐이다. 실제 데이터·모델 성능과도 무관하다.
