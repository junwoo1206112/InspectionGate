# 이미지 취약점 스캔 증거 계약

`python -m scripts.image_scan --image <local-image>`는 새 출력 디렉터리에 한 번의 local-image 스캔 준비성 보고서를 만든다. Trivy가 있을 때도 `--image-src docker --skip-db-update`를 강제해 registry fallback과 암묵 DB 갱신을 막는다. 자동 scanner 설치, image pull, 취약점 DB 다운로드, registry 전송은 하지 않는다.

- `not_measured`: Docker CLI/daemon, local image identity, 또는 scanner가 준비되지 않았다. 취약점 없음이나 보안 승인 뜻이 아니다.
- `tool_error`: scanner를 시작했으나 유효한 결과를 얻지 못했다.
- `measured`: local image ID와 scanner JSON을 같은 실행에 기록했다. 보고서는 local scanner executable 경로·SHA-256·version을 기록하지만, DB freshness와 승인 policy는 아직 측정/구현하지 않아 `policy_verdict=not_evaluated`이다.

이미지가 배포·공유·고객 제공되는 promotion에는 `not_measured` 또는 `tool_error` 보고서를 통과 증거로 사용할 수 없다. promotion 정책은 digest 또는 local image ID에 결합된 최신 `measured` 결과와 별도 명시 정책을 요구해야 한다. 이 도구는 TLS, 인증, 비밀 관리, HA, 복제, 이미지 서명, 취약점 없음, 보안 인증을 검증하지 않는다.
