const state = { prediction: null };
const $ = (selector) => document.querySelector(selector);

function showMessage(message) {
  $("#message").textContent = message;
  $("#error").textContent = "";
}

function showError(message) {
  $("#error").textContent = message;
  $("#message").textContent = "";
  $("#error").focus();
}

function setBusy(form, busy) {
  const button = form.querySelector('button[type="submit"]');
  if (button) button.disabled = busy;
  form.setAttribute("aria-busy", busy ? "true" : "false");
}

function value(value) {
  return value === null || value === undefined || value === "" ? "없음" : String(value);
}

function detailMessage(detail, fallback) {
  if (typeof detail === "string" && detail) return detail;
  if (detail && typeof detail === "object") return detail.message || detail.code || fallback;
  return fallback;
}

function renderPrediction(prediction) {
  state.prediction = prediction;
  $("#prediction-section").hidden = false;
  const fields = [
    ["예측 ID", prediction.prediction_id], ["입력 파일", prediction.input_name],
    ["모델 버전", prediction.model_version], ["임계값", prediction.threshold],
    ["모델 제안", prediction.proposal_label], ["최대 확률", prediction.max_probability],
    ["상태", prediction.status], ["HOLD 이유", prediction.hold_reason],
    ["사람 최종결정", prediction.final_decision], ["최종 라벨", prediction.final_label],
    ["검토 사유", prediction.review_reason], ["생성 시각", prediction.created_at]
  ];
  const details = $("#prediction-details");
  details.replaceChildren();
  for (const [label, item] of fields) {
    const term = document.createElement("dt"); term.textContent = label;
    const description = document.createElement("dd"); description.textContent = value(item);
    details.append(term, description);
  }
  const inputQuality = prediction.status === "HOLD_INPUT_QUALITY";
  const finalized = prediction.status === "FINALIZED";
  $("#input-quality-guidance").hidden = !inputQuality;
  $("#review-form").hidden = inputQuality || finalized;
}

async function renderAudit(predictionId) {
  const response = await fetch(`/predictions/${encodeURIComponent(predictionId)}/audit`);
  if (!response.ok) throw new Error("감사 이력을 불러오지 못했습니다.");
  const events = await response.json();
  const list = $("#audit-list"); list.replaceChildren();
  for (const event of events) {
    const item = document.createElement("li");
    item.textContent = `${event.at || ""} — ${event.event}${event.decision ? ` (${event.decision})` : ""}${event.reason ? `: ${event.reason}` : ""}`;
    list.append(item);
  }
  $("#audit-section").hidden = false;
}

async function loadQueue() {
  const filter = $("#queue-filter").value;
  const query = filter ? `?limit=20&status=${encodeURIComponent(filter)}` : "?limit=20";
  const response = await fetch(`/predictions${query}`);
  if (!response.ok) throw new Error("검토 대기열을 불러오지 못했습니다.");
  const items = await response.json();
  const list = $("#queue-list");
  list.replaceChildren();
  $("#queue-status").textContent = `${items.length}건`;
  $("#queue-empty").hidden = items.length > 0;
  for (const item of items) {
    const li = document.createElement("li");
    const summary = document.createElement("span");
    summary.textContent = `${item.status} | ${item.input_name} | 제안 ${value(item.proposal_label)} | 최대확률 ${value(item.max_probability)} | ${value(item.created_at)}`;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "불러오기";
    button.setAttribute("aria-label", `${item.status} ${item.input_name} 예측 불러오기`);
    button.addEventListener("click", async () => {
      try {
        const detail = await fetch(`/predictions/${encodeURIComponent(item.prediction_id)}`);
        if (!detail.ok) throw new Error("예측을 불러오지 못했습니다.");
        const prediction = await detail.json();
        renderPrediction(prediction);
        await renderAudit(prediction.prediction_id);
        showMessage(`예측을 불러왔습니다: ${prediction.prediction_id}`);
        $("#prediction-heading").focus();
      } catch (error) { showError(error.message); }
    });
    li.append(summary, button);
    list.append(li);
  }
}

$("#queue-filter").addEventListener("change", () => loadQueue().catch((error) => showError(error.message)));
$("#queue-refresh").addEventListener("click", () => loadQueue().catch((error) => showError(error.message)));

$("#upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const file = $("#image-file").files[0];
  if (!file) { showError("이미지 파일을 선택하세요."); return; }
  setBusy(form, true);
  try {
    const scenario = $("#scenario").value;
    const useRealModel = scenario === "real_model";
    const url = useRealModel ? "/predict" : `/predictions?demo_scenario=${encodeURIComponent(scenario)}`;
    const response = await fetch(url, { method: "POST", body: new FormData(form) });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const fallback = useRealModel
        ? "ONNX reference 모델 추론에 실패했습니다. INSPECTION_GATE_ARTIFACT_MANIFEST 설정을 확인하세요."
        : "예측 생성에 실패했습니다.";
      throw new Error(detailMessage(payload.detail, fallback));
    }
    const prediction = await response.json();
    renderPrediction(prediction);
    await renderAudit(prediction.prediction_id);
    await loadQueue();
    showMessage(`${useRealModel ? "ONNX reference 모델 제안" : "새 예측 ID"}이 생성되었습니다: ${prediction.prediction_id}`);
    $("#prediction-heading").focus();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(form, false);
  }
});

$("#review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.prediction) return;
  const form = event.currentTarget;
  const data = new FormData(form);
  const payload = { decision: data.get("decision"), reason: data.get("reason"), corrected_label: data.get("corrected_label") || null };
  setBusy(form, true);
  try {
    const response = await fetch(`/predictions/${encodeURIComponent(state.prediction.prediction_id)}/review`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error((await response.json()).detail || "최종결정을 저장하지 못했습니다.");
    const prediction = await response.json();
    renderPrediction(prediction);
    await renderAudit(prediction.prediction_id);
    await loadQueue();
    showMessage("최종결정과 감사 이력을 저장했습니다.");
    $("#prediction-heading").focus();
  } catch (error) {
    // 실패 응답에서는 state/renderPrediction을 바꾸지 않는다.
    showError(`저장되지 않았습니다: ${error.message}`);
  } finally {
    setBusy(form, false);
  }
});

loadQueue().catch((error) => showError(error.message));
