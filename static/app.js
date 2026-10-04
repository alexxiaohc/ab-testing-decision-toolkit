function setControlsEnabled(container, enabled) {
  container.querySelectorAll("input, select, textarea").forEach((control) => {
    control.disabled = !enabled;
  });
}

// 顶部五步导航：一次只展示一个阶段，让完整流程保持清晰。
const stepPanels = document.querySelectorAll("[data-step-panel]");
const navButtons = document.querySelectorAll(".step-nav [data-step-target]");

function showStep(step) {
  stepPanels.forEach((panel) => {
    panel.hidden = panel.dataset.stepPanel !== step;
  });
  navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.stepTarget === step);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll("[data-step-target]").forEach((button) => {
  button.addEventListener("click", () => showStep(button.dataset.stepTarget));
});

showStep(window.initialStep || "overview");

// 模块 1：根据设计指标类型切换比例/均值参数。
const designType = document.querySelector("#design-metric-type");
function updateDesignType() {
  if (!designType) return;
  document.querySelectorAll("[data-design-kind]").forEach((section) => {
    const active = section.dataset.designKind === designType.value;
    section.hidden = !active;
    setControlsEnabled(section, active);
  });
}
designType?.addEventListener("change", updateDesignType);
updateDesignType();

// 模块 2：质量清单即时计数，但不替用户判定实验是否有效。
const checklistInputs = document.querySelectorAll("input[name='quality_check']");
const checklistCount = document.querySelector("#checklist-count");
function updateChecklistCount() {
  if (!checklistCount) return;
  const passed = [...checklistInputs].filter((input) => input.checked).length;
  checklistCount.textContent = `${passed} / ${checklistInputs.length}`;
}
checklistInputs.forEach((input) => input.addEventListener("change", updateChecklistCount));
updateChecklistCount();

// 模块 3：保留 V3 的单指标切换逻辑。
const metricTypeSelect = document.querySelector("#metric-type");
const methodName = document.querySelector("#method-name");
function updateMetricType() {
  if (!metricTypeSelect) return;
  const selectedType = metricTypeSelect.value;
  document.querySelectorAll("[data-metric-section]").forEach((section) => {
    const active = section.dataset.metricSection === selectedType;
    section.hidden = !active;
    setControlsEnabled(section, active);
  });
  methodName.textContent = selectedType === "proportion"
    ? "两比例 Z 检验（Two-proportion Z-test）"
    : "韦尔奇独立样本 t 检验（Welch's t-test）";
}
metricTypeSelect?.addEventListener("change", updateMetricType);
updateMetricType();

// 模块 4：每个核心/护栏指标都可以独立选择比例型或均值型。
function updateSuiteMetric(card) {
  const typeSelect = card.querySelector(".suite-metric-type");
  if (!typeSelect || card.hidden) return;
  card.querySelectorAll("[data-suite-kind]").forEach((section) => {
    const active = section.dataset.suiteKind === typeSelect.value;
    section.hidden = !active;
    setControlsEnabled(section, active);
  });
  const methodChip = card.querySelector("[data-suite-method]");
  methodChip.textContent = typeSelect.value === "proportion"
    ? "两比例 Z 检验"
    : "韦尔奇 t 检验";
}

document.querySelectorAll(".suite-metric-type").forEach((select) => {
  select.addEventListener("change", () => updateSuiteMetric(select.closest("[data-suite-card]")));
});

const guardrailCount = document.querySelector("#guardrail-count");
function updateGuardrails() {
  if (!guardrailCount) return;
  const count = Number(guardrailCount.value);
  document.querySelectorAll("[data-suite-card]").forEach((card) => {
    const name = card.dataset.suiteCard;
    const index = name.startsWith("guardrail_") ? Number(name.split("_")[1]) : 0;
    const active = index === 0 || index <= count;
    card.hidden = !active;
    setControlsEnabled(card, active);
    if (active) updateSuiteMetric(card);
  });
}
guardrailCount?.addEventListener("change", updateGuardrails);
updateGuardrails();
