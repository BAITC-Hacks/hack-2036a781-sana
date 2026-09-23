const FIELD_DEFINITIONS = [
  { key: "title", label: "fieldTitle", kind: "input", full: true },
  { key: "context", label: "fieldContext", full: true },
  { key: "need", label: "fieldNeed", full: true },
  { key: "users", label: "fieldUsers", full: true },
  { key: "data_materials", label: "fieldData", full: true },
  { key: "constraints", label: "fieldConstraints", full: true },
  { key: "expected_result", label: "fieldExpected", full: true },
  { key: "success_criteria", label: "fieldSuccess", full: true },
  { key: "contact", label: "fieldContact" },
  { key: "interaction_format", label: "fieldInteraction" },
];

const INDUSTRIES = {
  online_school: "industryOnlineSchool",
  university: "industryUniversity",
  language_center: "industryLanguage",
  college: "industryCollege",
  school: "industrySchool",
  education: "industryEducation",
};

const LEVELS = {
  draft: "levelDraft",
  working: "levelWorking",
  ready: "levelReady",
  priority: "levelPriority",
};

const t = (key, values) => window.sanaI18n.t(key, values);
function readSavedMap(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch (_error) {
    return {};
  }
}
function saveMap(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (_error) { /* Private browsing may block storage. */ }
}
function saveSelectedTeam(teamId) {
  try { localStorage.setItem("sana-selected-team", teamId); } catch (_error) { /* The current tab still works. */ }
}
function saveUnpublishedDraft() {
  try {
    localStorage.setItem("sana-draft", byId("draft").value);
    localStorage.setItem("sana-industry", byId("industry").value);
  } catch (_error) { /* The editor remains usable in this tab. */ }
}
const state = {
  draft: "",
  industry: "online_school",
  questions: [],
  answers: {},
  card: null,
  rating: null,
  editingId: null,
  teams: [],
  ownerTokens: readSavedMap("sana-owner-tokens"),
  teamTokens: readSavedMap("sana-team-tokens"),
  selectedTeam: (() => { try { return localStorage.getItem("sana-selected-team") || ""; } catch (_error) { return ""; } })(),
  role: "business",
  locale: window.sanaI18n.locale,
  toastTimer: null,
};

const byId = (id) => document.getElementById(id);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char]));

async function request(path, options = {}) {
  const init = { method: options.method || "GET", headers: {} };
  if (options.ownerToken) init.headers["X-Sana-Owner"] = options.ownerToken;
  if (options.teamToken) init.headers["X-Sana-Team"] = options.teamToken;
  if (options.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, init);
  const payload = await response.json();
  if (!payload.ok) {
    const code = payload.error?.code || "generic";
    const key = `error_${code}`;
    const message = t(key);
    throw new Error(message === key ? t("error_generic") : message);
  }
  return payload.data;
}

function showToast(message, isError = false) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("show"), 3400);
}

function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.textContent = label;
  } else {
    button.disabled = false;
    if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
    delete button.dataset.originalHtml;
  }
}

function switchView(name) {
  if (state.role === "student" && name !== "catalog") name = "catalog";
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("hidden", view.id !== `view-${name}`);
    view.classList.toggle("active", view.id === `view-${name}`);
  });
  if (name === "catalog") loadCatalog();
  if (name === "proposals") loadProposals();
}

function renderQuestions() {
  const container = byId("questions");
  container.replaceChildren();
  state.questions.forEach((item, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "question-item";
    const id = `answer-${index}`;
    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = item.question;
    const textarea = document.createElement("textarea");
    textarea.id = id;
    textarea.className = "input answer-input";
    textarea.dataset.key = item.key;
    textarea.maxLength = 2000;
    textarea.placeholder = t("answerPlaceholder");
    textarea.value = state.answers[item.key] || "";
    textarea.addEventListener("input", () => {
      state.answers[item.key] = textarea.value;
    });
    wrapper.append(label, textarea);
    container.append(wrapper);
  });
}

function renderCardFields() {
  const container = byId("card-fields");
  container.replaceChildren();
  FIELD_DEFINITIONS.forEach((definition) => {
    const wrapper = document.createElement("div");
    wrapper.className = `card-field${definition.full ? " full" : ""}`;
    const label = document.createElement("label");
    label.textContent = t(definition.label);
    label.htmlFor = `card-${definition.key}`;
    const input = document.createElement(definition.kind === "input" ? "input" : "textarea");
    input.id = `card-${definition.key}`;
    input.className = "input card-input";
    input.dataset.field = definition.key;
    input.maxLength = 4000;
    input.value = state.card?.[definition.key] || "";
    input.classList.toggle("is-empty", !input.value.trim());
    input.addEventListener("input", () => {
      state.card[definition.key] = input.value;
      input.classList.toggle("is-empty", !input.value.trim());
      scheduleRating();
    });
    wrapper.append(label, input);
    container.append(wrapper);
  });

  const industryWrapper = document.createElement("div");
  industryWrapper.className = "card-field";
  const industryLabel = document.createElement("label");
  industryLabel.htmlFor = "card-industry";
  industryLabel.textContent = t("industry");
  const select = document.createElement("select");
  select.id = "card-industry";
  select.className = "input";
  Object.entries(INDUSTRIES).filter(([key]) => key !== "education").forEach(([key, label]) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = t(label);
    select.append(option);
  });
  select.value = state.card?.industry || state.industry;
  select.addEventListener("change", () => { state.card.industry = select.value; });
  industryWrapper.append(industryLabel, select);
  container.append(industryWrapper);

  byId("publish").querySelector("[data-i18n]").textContent = t(state.editingId ? "saveChanges" : "publish");
  byId("cancel-edit").classList.toggle("hidden", !state.editingId);
  renderRating(state.card.rating || state.rating || { score: 0, level: "draft", breakdown: [], missing: [], tips: [] });
}

function renderRating(rating) {
  const startScore = Number(state.rating?.score) || 0;
  state.rating = rating;
  const panel = byId("rating-panel");
  const metricLabels = {
    context_need: "metricContext", data_materials: "metricData", expected_result: "metricExpected",
    success_criteria: "metricSuccess", constraints: "metricConstraints", users: "metricUsers", business_link: "metricBusiness",
  };
  const tipLabels = {
    context_need: "tipContext", data_materials: "tipData", expected_result: "tipExpected",
    success_criteria: "tipSuccess", constraints: "tipConstraints", users: "tipUsers", business_link: "tipBusiness",
  };
  const metrics = (rating.breakdown || []).map((item) => `
    <div class="metric-row" data-filled="${Boolean(item.filled)}">
      <span class="metric-name">${escapeHtml(t(metricLabels[item.key] || item.label))}${item.filled ? "" : `<small class="metric-missing">${escapeHtml(t("metricMissing"))}</small>`}</span>
      <span class="metric-score">${Number(item.earned) || 0}/${Number(item.max) || 0}</span>
    </div>`).join("");
  const tips = (rating.breakdown || []).filter((item) => !item.filled).map((item) => {
    const key = tipLabels[item.key];
    return key ? `<li>${escapeHtml(t(key, { points: Number(item.max) - Number(item.earned) }))}</li>` : "";
  }).join("");
  const level = t(LEVELS[rating.level] || LEVELS.draft);
  panel.innerHTML = `
    <div class="rating-top">
      <div><span class="rating-score" data-value="${Number(rating.score) || 0}">${startScore}</span><span class="rating-out-of">${escapeHtml(t("ratingOutOf"))}</span></div>
      <span class="level-pill" data-level="${escapeHtml(rating.level || "draft")}">${escapeHtml(level)}</span>
    </div>
    <div class="progress-track"><div class="progress-fill" style="width:${Math.max(0, Math.min(100, Number(rating.score) || 0))}%"></div></div>
    <p class="rating-title">${escapeHtml(t("ratingBreakdown"))}</p>
    ${metrics || `<p class="helper-text">${escapeHtml(t("ratingLoading"))}</p>`}
    <p class="rating-title" style="margin-top:20px">${escapeHtml(t("ratingTips"))}</p>
    ${tips ? `<ul class="tips-list">${tips}</ul>` : `<p class="helper-text">${escapeHtml(t("noTips"))}</p>`}`;
  const scoreNode = panel.querySelector(".rating-score");
  const target = Number(rating.score) || 0;
  const started = performance.now();
  const animate = (now) => {
    const progress = Math.min((now - started) / 520, 1);
    const eased = 1 - (1 - progress) ** 3;
    scoreNode.textContent = String(Math.round(startScore + (target - startScore) * eased));
    if (progress < 1) requestAnimationFrame(animate);
  };
  requestAnimationFrame(animate);
}

let ratingTimer;
function scheduleRating() {
  clearTimeout(ratingTimer);
  ratingTimer = setTimeout(async () => {
    if (!state.card) return;
    try {
      const result = await request("/api/rating", { method: "POST", body: { card: state.card } });
      state.card.rating = result.rating;
      renderRating(result.rating);
    } catch (error) {
      showToast(error.message, true);
    }
  }, 400);
}

async function analyzeDraft(preserveAnswers = false) {
  const button = byId("analyze");
  const draft = byId("draft").value.trim();
  const industry = byId("industry").value;
  if (!draft) return showToast(t("toastDraft"), true);
  state.draft = draft;
  state.industry = industry;
  if (!preserveAnswers) state.answers = {};
  setBusy(button, true, t("analyzing"));
  try {
    const result = await request("/api/analyze", { method: "POST", body: { draft, industry, locale: state.locale } });
    state.questions = result.questions;
    renderQuestions();
    const badge = byId("source-badge");
    badge.textContent = result.source === "ai" ? t("sourceAi") : t("sourceFallback");
    badge.dataset.source = result.source;
    byId("analysis").classList.remove("hidden");
    byId("card-workspace").classList.add("hidden");
    byId("analysis").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function buildCard() {
  const button = byId("build-card");
  const answers = state.questions.map((item) => ({
    key: item.key,
    question: item.question,
    answer: state.answers[item.key] || "",
  }));
  setBusy(button, true, t("building"));
  try {
    const result = await request("/api/build-card", {
      method: "POST",
      body: { draft: state.draft, industry: state.industry, answers, locale: state.locale },
    });
    state.card = result.card;
    state.editingId = null;
    renderCardFields();
    const badge = byId("source-badge");
    badge.textContent = result.source === "ai" ? t("sourceCardAi") : t("sourceCardFallback");
    badge.dataset.source = result.source;
    byId("card-workspace").classList.remove("hidden");
    byId("card-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
  }
}

async function publishCard() {
  if (!state.card) return;
  const button = byId("publish");
  const body = { card: { ...state.card, industry: byId("card-industry").value } };
  const wasEditing = Boolean(state.editingId);
  setBusy(button, true, t("saving"));
  try {
    const result = state.editingId
      ? await request(`/api/tasks/${encodeURIComponent(state.editingId)}`, { method: "PUT", body, ownerToken: state.ownerTokens[state.editingId] })
      : await request("/api/tasks", { method: "POST", body });
    if (result.owner_token && result.task?.id) {
      state.ownerTokens[result.task.id] = result.owner_token;
      saveMap("sana-owner-tokens", state.ownerTokens);
    }
    state.card = result.task;
    state.editingId = null;
    byId("card-workspace").classList.add("hidden");
    byId("analysis").classList.add("hidden");
    if (!wasEditing) {
      byId("draft").value = "";
      saveUnpublishedDraft();
    }
    showToast(t("toastPublished"));
    switchView("proposals");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(button, false);
    button.querySelector("[data-i18n]").textContent = t(state.editingId ? "saveChanges" : "publish");
  }
}

function levelLabel(level) { return t(LEVELS[level] || "levelDraft"); }
function industryLabel(industry) { return INDUSTRIES[industry] ? t(INDUSTRIES[industry]) : (industry || ""); }
function formatOfferCount(count) {
  const value = Number(count) || 0;
  if (state.locale === "ru") {
    const tail = value % 10 === 1 && value % 100 !== 11 ? "offerOne" : value % 10 >= 2 && value % 10 <= 4 && (value % 100 < 12 || value % 100 > 14) ? "offerFew" : "offerMany";
    return `${value} ${t(tail)}`;
  }
  if (state.locale === "kk") return `${value} ${t("offerMany")}`;
  return `${value} ${t(value === 1 ? "offerOne" : "offerMany")}`;
}

function taskCardHtml(task) {
  const score = Number(task.rating?.score) || 0;
  const metricLabels = { context_need: "metricContext", data_materials: "metricData", expected_result: "metricExpected", success_criteria: "metricSuccess", constraints: "metricConstraints", users: "metricUsers", business_link: "metricBusiness" };
  const metrics = (task.rating?.breakdown || []).map((item) => `<div class="metric-row"><span class="metric-name">${escapeHtml(t(metricLabels[item.key] || item.label))}</span><span class="metric-score">${Number(item.earned) || 0}/${Number(item.max) || 0}</span></div>`).join("");
  const teamActions = state.role === "student" ? `<button class="button button-primary proposal-toggle" type="button">${escapeHtml(t(state.selectedTeam ? "propose" : "createTeamFirst"))} →</button>` : "";
  return `
    <article class="task-card" data-task-id="${escapeHtml(task.id)}">
      <div class="task-card-head">
        <div><h3 class="task-title">${escapeHtml(task.title)}</h3><div class="task-meta"><span>${escapeHtml(industryLabel(task.industry))}</span><span>·</span><span>${escapeHtml(levelLabel(task.rating?.level))}</span></div></div>
        <div class="score-chip">${score} ${escapeHtml(t("ratingOutOf"))}<small>${escapeHtml(t("scoreLabel"))}</small></div>
      </div>
      <p class="task-summary">${escapeHtml(task.need || task.context || t("fieldEmpty"))}</p>
      <div class="task-actions"><button class="button button-quiet details-toggle" type="button">${escapeHtml(t("details"))}</button>${teamActions}</div>
      <div class="task-details hidden">
      <div class="task-rating-details"><strong>${escapeHtml(t("ratingBreakdown"))}</strong>${metrics}</div>
        <div class="task-fields">${FIELD_DEFINITIONS.filter((field) => field.key !== "title").map((field) => `
          <div class="task-detail"><strong>${escapeHtml(t(field.label))}</strong><span>${escapeHtml(task[field.key] || t("fieldEmpty"))}</span></div>`).join("")}</div>
        ${state.role === "student" ? `<form class="proposal-form hidden" data-task-id="${escapeHtml(task.id)}">
          <label>${escapeHtml(t("proposalFormDeadline"))}<input class="input" name="deadline" maxlength="100" placeholder="${escapeHtml(t("deadlinePlaceholder"))}" required></label>
          <label class="full">${escapeHtml(t("proposalFormIdea"))}<textarea class="input" name="idea" maxlength="2000" required></textarea></label>
          <label class="full">${escapeHtml(t("proposalFormPlan"))}<textarea class="input" name="plan" maxlength="2000" required></textarea></label>
          <label class="full">${escapeHtml(t("proposalFormLink"))}<input class="input" name="link" type="url" placeholder="https://…" required></label>
          <button class="button button-dark" type="submit">${escapeHtml(t("sendProposal"))} →</button>
        </form>` : ""}
      </div>
    </article>`;
}

function updateTeamControls() {
  const owned = state.teams.filter((team) => Boolean(state.teamTokens[team.id]));
  if (!owned.some((team) => team.id === state.selectedTeam)) state.selectedTeam = owned[0]?.id || "";
  const select = byId("active-team");
  select.innerHTML = owned.map((team) => `<option value="${escapeHtml(team.id)}">${escapeHtml(team.name)}</option>`).join("");
  select.value = state.selectedTeam;
  const student = state.role === "student";
  byId("team-toolbar").classList.toggle("hidden", !student || !owned.length);
  byId("team-setup").classList.toggle("hidden", !student);
  byId("student-progress").classList.toggle("hidden", !student || !owned.length);
  if (student && !owned.length) byId("team-setup").open = true;
  saveSelectedTeam(state.selectedTeam);
}

async function loadCatalog() {
  updateTeamControls();
  const params = new URLSearchParams();
  if (byId("filter-industry").value) params.set("industry", byId("filter-industry").value);
  if (byId("filter-level").value) params.set("level", byId("filter-level").value);
  params.set("sort", byId("filter-sort").value || "rating");
  const container = byId("catalog-list");
  container.innerHTML = `<div class="empty-state">${escapeHtml(t("loadingCatalog"))}</div>`;
  try {
    const result = await request(`/api/tasks?${params.toString()}`);
    const tasks = result.tasks || [];
    if (!tasks.length) {
      const hint = state.role === "student" ? t("noTasksStudentHint") : t("noTasksHint");
      container.innerHTML = `<div class="empty-state"><strong>${escapeHtml(t("noTasks"))}</strong><p>${escapeHtml(hint)}</p>${state.role === "business" ? `<button type="button" class="button button-primary" data-go="business">${escapeHtml(t("createFirstTask"))}</button>` : ""}</div>`;
      if (state.role === "student" && state.selectedTeam) loadStudentProgress();
      return;
    }
    const select = byId("filter-industry");
    const currentIndustry = select.value;
    const values = Object.keys(INDUSTRIES).filter((value) => value !== "education");
    const options = [`<option value="">${escapeHtml(t("filterAllIndustries"))}</option>`, ...values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(industryLabel(value))}</option>`)];
    select.innerHTML = options.join("");
    select.value = currentIndustry;
    container.innerHTML = tasks.map(taskCardHtml).join("");
    if (state.role === "student" && state.selectedTeam) loadStudentProgress();
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><strong>${escapeHtml(t("catalogLoadError"))}</strong>${escapeHtml(error.message)}</div>`;
  }
}

async function loadStudentProgress() {
  const container = byId("student-progress-list");
  if (state.role !== "student" || !state.selectedTeam) {
    container.innerHTML = `<div class="empty-state">${escapeHtml(t("noTeam"))}</div>`;
    return;
  }
  const teamId = state.selectedTeam;
  const teamToken = state.teamTokens[teamId];
  container.innerHTML = `<div class="empty-state">${escapeHtml(t("loading"))}</div>`;
  try {
    const { proposals } = await request(`/api/teams/${encodeURIComponent(teamId)}/proposals`, { teamToken });
    if (teamId !== state.selectedTeam) return;
    if (!proposals.length) {
      container.innerHTML = `<div class="empty-state"><strong>${escapeHtml(t("noTeamProposals"))}</strong>${escapeHtml(t("noTeamProposalsHint"))}</div>`;
      return;
    }
    const items = await Promise.all(proposals.map(async (proposal) => {
      const { task } = await request(`/api/tasks/${encodeURIComponent(proposal.task_id)}`);
      const progress = proposal.status === "accepted"
        ? (await request(`/api/proposals/${encodeURIComponent(proposal.id)}/progress`, { teamToken })).progress
        : [];
      const statusKey = { new: "statusNew", accepted: "statusAccepted", rejected: "statusRejected" }[proposal.status] || "statusNew";
      const progressForm = proposal.status === "accepted" ? `<form class="progress-form student-progress-form" data-proposal-id="${escapeHtml(proposal.id)}"><label>${escapeHtml(t("progressResult"))}<textarea class="input" name="result" maxlength="2000" required></textarea></label><label>${escapeHtml(t("evidenceLink"))}<input class="input" name="evidence_link" type="url" placeholder="https://…" required></label><button class="button button-primary" type="submit">${escapeHtml(t("submitProgress"))}</button></form>` : "";
      return `<article class="proposal-task"><div class="proposal-item-head"><p class="eyebrow">${escapeHtml(industryLabel(task.industry))}</p><span class="proposal-status" data-status="${escapeHtml(proposal.status)}">${escapeHtml(t(statusKey))}</span></div><h3 class="task-title">${escapeHtml(task.title)}</h3><p class="task-summary">${escapeHtml(proposal.idea)}</p>${progressForm}${progress.map((entry) => `<div class="progress-entry"><strong>${escapeHtml(entry.result)}</strong><a href="${escapeHtml(entry.evidence_link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("evidence"))} ↗</a><span class="proposal-status" data-status="${escapeHtml(entry.status)}">${escapeHtml(t({ submitted: "progressPending", confirmed: "progressConfirmed", rejected: "progressRejected" }[entry.status], { points: entry.points }))}</span></div>`).join("")}</article>`;
    }));
    if (teamId !== state.selectedTeam) return;
    container.innerHTML = items.join("");
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><strong>${escapeHtml(t("progressLoadError"))}</strong>${escapeHtml(error.message)}</div>`;
  }
}

async function loadProposals() {
  const container = byId("proposal-list");
  const board = byId("progress-board");
  container.innerHTML = `<div class="empty-state">${escapeHtml(t("loading"))}</div>`;
  board.classList.add("hidden");
  try {
    const [{ tasks }, leaderboard] = await Promise.all([
      request("/api/tasks?sort=date"),
      request("/api/progress"),
    ]);
    const ownedTasks = tasks.filter((task) => Boolean(state.ownerTokens[task.id]));
    board.classList.toggle("hidden", !ownedTasks.length);
    if (ownedTasks.length) board.innerHTML = `<div class="scoreboard"><div><p class="eyebrow">${escapeHtml(t("progressBoard"))}</p><h3>${escapeHtml(t("teamProgressHeading"))}</h3><p>${escapeHtml(t("progressRule", { points: leaderboard.points_per_confirmed_stage }))}</p></div><ol>${leaderboard.teams.map((team) => `<li><strong>${escapeHtml(team.name)}</strong><span>${Number(team.progress_points) || 0} ${escapeHtml(t("points"))}</span></li>`).join("")}</ol></div>`;
    const grouped = await Promise.all(ownedTasks.map(async (task) => ({
      task,
      proposals: (await request(`/api/tasks/${encodeURIComponent(task.id)}/proposals`, { ownerToken: state.ownerTokens[task.id] })).proposals,
    })));
    const groups = grouped;
    if (!groups.length) {
      container.innerHTML = `<div class="empty-state"><strong>${escapeHtml(t("noPublishedTasks"))}</strong><p>${escapeHtml(t("noPublishedTasksHint"))}</p><button type="button" class="button button-primary" data-go="business">${escapeHtml(t("createFirstTask"))}</button></div>`;
      return;
    }
    const teamNames = Object.fromEntries(state.teams.map((team) => [team.id, team.name]));
    const groupHtml = await Promise.all(groups.map(async ({ task, proposals }) => {
      const proposalHtml = await Promise.all(proposals.map(async (proposal) => {
          const { progress } = await request(`/api/proposals/${encodeURIComponent(proposal.id)}/progress`, { ownerToken: state.ownerTokens[task.id] });
          return `
          <div class="proposal-item">
            <div class="proposal-item-head"><strong>${escapeHtml(teamNames[proposal.team_id] || proposal.team_id)}</strong><span class="proposal-status" data-status="${escapeHtml(proposal.status)}">${escapeHtml(t({ new: "statusNew", accepted: "statusAccepted", rejected: "statusRejected" }[proposal.status] || "statusNew"))}</span></div>
            <p><strong>${escapeHtml(t("idea"))}:</strong> ${escapeHtml(proposal.idea)}</p>
            <p><strong>${escapeHtml(t("plan"))}:</strong> ${escapeHtml(proposal.plan)} · <strong>${escapeHtml(t("proposalFormDeadline"))}:</strong> ${escapeHtml(proposal.deadline)}</p>
            <a href="${escapeHtml(proposal.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("openPrototype"))} ↗</a>
            ${proposal.status === "new" ? `<div class="task-actions" style="margin-top:10px"><button class="button button-primary decide" data-id="${escapeHtml(proposal.id)}" data-decision="accepted" type="button">${escapeHtml(t("choose"))}</button><button class="button button-quiet decide" data-id="${escapeHtml(proposal.id)}" data-decision="rejected" type="button">${escapeHtml(t("reject"))}</button></div>` : ""}
            ${progress.map((entry) => `<div class="progress-entry"><strong>${escapeHtml(t("progressResultLabel"))}</strong> ${escapeHtml(entry.result)} · <a href="${escapeHtml(entry.evidence_link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(t("evidenceLabel"))} ↗</a><span class="proposal-status" data-status="${escapeHtml(entry.status)}">${escapeHtml(entry.status === "confirmed" ? t("progressConfirmed", { points: entry.points }) : t({ submitted: "progressSubmitted", rejected: "progressRejected" }[entry.status] || "progressSubmitted"))}</span>${entry.status === "submitted" ? `<div class="task-actions"><button class="button button-primary progress-decision" data-id="${escapeHtml(entry.id)}" data-decision="confirmed" type="button">${escapeHtml(t("confirmStage"))}</button><button class="button button-quiet progress-decision" data-id="${escapeHtml(entry.id)}" data-decision="rejected" type="button">${escapeHtml(t("reject"))}</button></div>` : ""}</div>`).join("")}
          </div>`;
      }));
      return `<article class="proposal-task" data-task-id="${escapeHtml(task.id)}">
        <div class="task-card-head"><div><p class="eyebrow">${escapeHtml(industryLabel(task.industry))} · ${Number(task.rating?.score) || 0} ${escapeHtml(t("points"))} · ${escapeHtml(formatOfferCount(proposals.length))}</p><h3 class="task-title">${escapeHtml(task.title)}</h3></div><button class="button button-quiet edit-task" type="button" data-task-id="${escapeHtml(task.id)}">${escapeHtml(t("editTask"))}</button></div>
        ${proposalHtml.length ? proposalHtml.join("") : `<p class="no-proposals">${escapeHtml(t("noOffers"))}</p>`}
      </article>`;
    }));
    container.innerHTML = groupHtml.join("");
  } catch (error) {
    container.innerHTML = `<div class="empty-state"><strong>${escapeHtml(t("proposalLoadError"))}</strong>${escapeHtml(error.message)}</div>`;
  }
}

async function editTask(taskId) {
  if (!state.ownerTokens[taskId]) return showToast(t("error_forbidden"), true);
  try {
    const result = await request(`/api/tasks/${encodeURIComponent(taskId)}`);
    state.card = result.task;
    state.industry = result.task.industry;
    state.editingId = taskId;
    renderCardFields();
    byId("card-workspace").classList.remove("hidden");
    switchView("business");
    byId("card-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  }
}

async function renderAccessList() {
  const container = byId("access-list");
  container.innerHTML = `<p class="helper-text">${escapeHtml(t("loading"))}</p>`;
  try {
    const [{ tasks }, { teams }] = await Promise.all([
      request("/api/tasks?sort=date"), request("/api/teams"),
    ]);
    const entries = [
      ...tasks.filter((task) => state.ownerTokens[task.id]).map((task) => ({
        label: task.title, kind: t("accessTask"), code: `task:${task.id}:${state.ownerTokens[task.id]}`,
      })),
      ...teams.filter((team) => state.teamTokens[team.id]).map((team) => ({
        label: team.name, kind: t("accessTeam"), code: `team:${team.id}:${state.teamTokens[team.id]}`,
      })),
    ];
    container.innerHTML = entries.length ? entries.map((entry) => `
      <div class="access-entry"><div><small>${escapeHtml(entry.kind)}</small><strong>${escapeHtml(entry.label)}</strong></div>
      <code>${escapeHtml(entry.code)}</code><button class="button button-quiet copy-access" type="button">${escapeHtml(t("accessCopyButton"))}</button></div>`).join("")
      : `<p class="access-empty">${escapeHtml(t("accessEmpty"))}</p>`;
  } catch (error) {
    container.innerHTML = `<p class="access-empty">${escapeHtml(error.message)}</p>`;
  }
}

async function importAccessCode(rawCode) {
  const match = /^(task|team):(t_\d+|team_\d+):([A-Za-z0-9_-]{32,128})$/.exec(rawCode.trim());
  if (!match || (match[1] === "task" && !match[2].startsWith("t_")) || (match[1] === "team" && !match[2].startsWith("team_"))) {
    throw new Error(t("accessInvalid"));
  }
  const [, kind, id, token] = match;
  if (kind === "task") {
    await request(`/api/tasks/${encodeURIComponent(id)}/proposals`, { ownerToken: token });
    state.ownerTokens[id] = token;
    saveMap("sana-owner-tokens", state.ownerTokens);
    byId("role-switch").value = "business";
    byId("role-switch").dispatchEvent(new Event("change"));
    switchView("proposals");
  } else {
    await request(`/api/teams/${encodeURIComponent(id)}/proposals`, { teamToken: token });
    state.teamTokens[id] = token;
    saveMap("sana-team-tokens", state.teamTokens);
    state.selectedTeam = id;
    saveSelectedTeam(id);
    const result = await request("/api/teams");
    state.teams = result.teams || [];
    byId("role-switch").value = "student";
    byId("role-switch").dispatchEvent(new Event("change"));
  }
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => switchView(tab.dataset.view)));
  byId("analyze").addEventListener("click", analyzeDraft);
  byId("build-card").addEventListener("click", buildCard);
  byId("publish").addEventListener("click", publishCard);
  byId("draft").addEventListener("input", saveUnpublishedDraft);
  byId("industry").addEventListener("change", saveUnpublishedDraft);
  byId("cancel-edit").addEventListener("click", () => {
    state.editingId = null;
    state.card = null;
    byId("card-workspace").classList.add("hidden");
  });
  ["filter-industry", "filter-level", "filter-sort"].forEach((id) => byId(id).addEventListener("change", loadCatalog));
  byId("refresh-catalog").addEventListener("click", loadCatalog);
  byId("refresh-proposals").addEventListener("click", loadProposals);
  byId("open-access").addEventListener("click", () => {
    byId("access-dialog").showModal();
    renderAccessList();
  });
  byId("close-access").addEventListener("click", () => byId("access-dialog").close());
  byId("access-dialog").addEventListener("click", (event) => {
    if (event.target === byId("access-dialog")) byId("access-dialog").close();
  });
  byId("access-list").addEventListener("click", async (event) => {
    const button = event.target.closest(".copy-access");
    if (!button) return;
    const code = button.closest(".access-entry")?.querySelector("code")?.textContent;
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      showToast(t("accessCopied"));
    } catch (_error) {
      showToast(t("accessCopyManual"), true);
    }
  });
  byId("access-import").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const submit = form.querySelector("button[type=submit]");
    setBusy(submit, true, t("saving"));
    try {
      await importAccessCode(byId("access-code").value);
      form.reset();
      byId("access-dialog").close();
      showToast(t("accessRestored"));
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });
  byId("catalog-list").addEventListener("click", (event) => {
    if (event.target.closest('[data-go="business"]')) switchView("business");
  });
  byId("proposal-list").addEventListener("click", (event) => {
    if (event.target.closest('[data-go="business"]')) switchView("business");
  });
  byId("role-switch").addEventListener("change", (event) => {
    state.role = event.target.value;
    document.querySelectorAll("[data-business-only]").forEach((item) => item.classList.toggle("hidden", state.role !== "business"));
    document.querySelector('[data-view="business"]').classList.toggle("hidden", state.role !== "business");
    document.querySelector('[data-view="catalog"]').click();
  });
  byId("language-switch").value = state.locale;
  byId("language-switch").addEventListener("change", async (event) => {
    state.locale = event.target.value;
    window.sanaI18n.applyLanguage(state.locale);
    const service = byId("service-status");
    if (service.dataset.state === "ok") service.textContent = t("serviceOnline");
    if (service.dataset.state === "error") service.textContent = t("serviceOffline");
    if (!byId("analysis").classList.contains("hidden") && byId("card-workspace").classList.contains("hidden") && byId("draft").value.trim()) {
      await analyzeDraft(true);
    }
    if (state.card && !byId("card-workspace").classList.contains("hidden")) {
      renderCardFields();
    }
    const badge = byId("source-badge");
    if (badge.dataset.source) {
      const isCard = !byId("card-workspace").classList.contains("hidden");
      badge.textContent = t(isCard ? (badge.dataset.source === "ai" ? "sourceCardAi" : "sourceCardFallback") : (badge.dataset.source === "ai" ? "sourceAi" : "sourceFallback"));
    }
    if (!byId("view-catalog").classList.contains("hidden")) loadCatalog();
    if (!byId("view-proposals").classList.contains("hidden")) loadProposals();
    if (byId("access-dialog").open) renderAccessList();
  });
  byId("active-team").addEventListener("change", (event) => {
    state.selectedTeam = event.target.value;
    saveSelectedTeam(state.selectedTeam);
    loadStudentProgress();
  });
  byId("team-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const submit = form.querySelector("button[type=submit]");
    const values = Object.fromEntries(new FormData(form).entries());
    const splitTags = (value) => String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
    setBusy(submit, true, t("saving"));
    try {
      const result = await request("/api/teams", { method: "POST", body: {
        name: String(values.name || "").trim(),
        interests: splitTags(values.interests),
        skills: splitTags(values.skills),
        technologies: splitTags(values.technologies),
      } });
      state.teamTokens[result.team.id] = result.team_token;
      saveMap("sana-team-tokens", state.teamTokens);
      state.teams.push(result.team);
      state.selectedTeam = result.team.id;
      saveSelectedTeam(state.selectedTeam);
      form.reset();
      byId("team-setup").open = false;
      showToast(t("toastTeamCreated"));
      loadCatalog();
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });

  byId("catalog-list").addEventListener("click", async (event) => {
    const card = event.target.closest(".task-card");
    if (!card) return;
    if (event.target.closest(".details-toggle")) card.querySelector(".task-details").classList.toggle("hidden");
    if (event.target.closest(".proposal-toggle")) {
      if (!state.selectedTeam || !state.teamTokens[state.selectedTeam]) {
        byId("team-setup").open = true;
        byId("team-setup").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      card.querySelector(".task-details").classList.remove("hidden");
      card.querySelector(".proposal-form").classList.toggle("hidden");
    }
  });
  byId("catalog-list").addEventListener("submit", async (event) => {
    if (!event.target.matches(".proposal-form")) return;
    event.preventDefault();
    const form = event.target;
    const values = Object.fromEntries(new FormData(form).entries());
    const submit = form.querySelector("button[type=submit]");
    setBusy(submit, true, t("sending"));
    try {
      await request(`/api/tasks/${encodeURIComponent(form.dataset.taskId)}/proposals`, {
        method: "POST", body: { ...values, team_id: state.selectedTeam }, teamToken: state.teamTokens[state.selectedTeam],
      });
      showToast(t("toastProposal"));
      form.reset();
      await loadStudentProgress();
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });
  byId("student-progress-list").addEventListener("submit", async (event) => {
    if (!event.target.matches(".student-progress-form")) return;
    event.preventDefault();
    const form = event.target;
    const submit = form.querySelector("button[type=submit]");
    setBusy(submit, true, t("sending"));
    try {
      await request(`/api/proposals/${encodeURIComponent(form.dataset.proposalId)}/progress`, {
        method: "POST", body: Object.fromEntries(new FormData(form).entries()), teamToken: state.teamTokens[state.selectedTeam],
      });
      showToast(t("toastProgress"));
      await loadStudentProgress();
    } catch (error) {
      showToast(error.message, true);
    } finally {
      setBusy(submit, false);
    }
  });
  byId("proposal-list").addEventListener("click", async (event) => {
    const decisionButton = event.target.closest(".decide");
    const progressButton = event.target.closest(".progress-decision");
    const editButton = event.target.closest(".edit-task");
    const taskId = event.target.closest(".proposal-task")?.dataset.taskId;
    const ownerToken = taskId ? state.ownerTokens[taskId] : "";
    if (decisionButton) {
      const decision = decisionButton.dataset.decision;
      setBusy(decisionButton, true, t("saving"));
      try {
        await request(`/api/proposals/${encodeURIComponent(decisionButton.dataset.id)}/decision`, {
          method: "POST",
          body: { decision: decisionButton.dataset.decision }, ownerToken,
        });
        showToast(decision === "accepted" ? t("toastAccepted") : t("toastRejected"));
        await loadProposals();
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(decisionButton, false);
      }
    } else if (progressButton) {
      const decision = progressButton.dataset.decision;
      setBusy(progressButton, true, t("saving"));
      try {
        await request(`/api/progress/${encodeURIComponent(progressButton.dataset.id)}/decision`, {
          method: "POST", body: { decision: progressButton.dataset.decision },
          ownerToken,
        });
        showToast(decision === "confirmed" ? t("toastStageConfirmed") : t("toastStageRejected"));
        await loadProposals();
      } catch (error) {
        showToast(error.message, true);
      } finally {
        setBusy(progressButton, false);
      }
    } else if (editButton) {
      editTask(editButton.dataset.taskId);
    }
  });
}

async function start() {
  bindEvents();
  try {
    byId("draft").value = localStorage.getItem("sana-draft") || "";
    byId("industry").value = localStorage.getItem("sana-industry") || "online_school";
  } catch (_error) { /* Storage is optional. */ }
  try {
    const response = await fetch("/api/health");
    const result = await response.json();
    const label = byId("service-status");
    label.textContent = result.status === "ok" ? t("serviceOnline") : t("serviceOffline");
    label.dataset.state = result.status === "ok" ? "ok" : "error";
  } catch (_error) {
    const label = byId("service-status");
    label.textContent = t("serviceOffline");
    label.dataset.state = "error";
  }
  try {
    const result = await request("/api/teams");
    state.teams = result.teams || [];
    updateTeamControls();
  } catch (error) {
    showToast(error.message, true);
  }
}

start();
