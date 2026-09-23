import { useEffect, useMemo, useRef, useState } from "react";
import brandReference from "./assets/sana-brand-reference.png";

const FIELD_DEFS = [
  ["title", "Название задачи", "input"],
  ["context", "Контекст: что происходит сейчас"],
  ["need", "Потребность: что необходимо изменить"],
  ["users", "Кто будет пользоваться решением"],
  ["data_materials", "Данные и материалы"],
  ["constraints", "Ограничения"],
  ["expected_result", "Ожидаемый результат"],
  ["success_criteria", "Критерии успеха"],
  ["contact", "Контакт бизнеса", "input"],
  ["interaction_format", "Формат взаимодействия", "input"],
];

const INDUSTRIES = {
  online_school: "Онлайн-школа",
  university: "Университет",
  language_center: "Языковой центр",
  college: "Колледж",
  school: "Школа",
  education: "Образование",
};

const LEVELS = {
  draft: ["Нужны уточнения", "#e58a64"],
  working: ["Рабочая", "#d8a52d"],
  ready: ["Готовая", "#3f8f76"],
  priority: ["Приоритетная", "#116149"],
};

const METRIC_LABELS = {
  context_need: "Контекст и потребность",
  data_materials: "Данные и материалы",
  expected_result: "Ожидаемый результат",
  success_criteria: "Критерии успеха",
  constraints: "Ограничения",
  users: "Пользователи",
  business_link: "Связь с бизнесом",
};

const initialCard = () => ({
  title: "", context: "", need: "", users: "", data_materials: "",
  constraints: "", expected_result: "", success_criteria: "", contact: "",
  interaction_format: "", industry: "online_school",
  rating: { score: 0, level: "draft", breakdown: [], missing: [], tips: [] },
});

function readJson(key, fallback) {
  try {
    const value = JSON.parse(localStorage.getItem(key));
    return value ?? fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Local mode still works. */ }
}

async function api(path, { method = "GET", body, ownerToken, teamToken } = {}) {
  const headers = {};
  if (ownerToken) headers["X-Sana-Owner"] = ownerToken;
  if (teamToken) headers["X-Sana-Team"] = teamToken;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!payload.ok && payload.status !== "ok") {
    throw new Error(payload.error?.message || "Не удалось выполнить запрос");
  }
  return payload.data ?? payload;
}

function Icon({ name }) {
  const paths = {
    chat: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/><path d="M8 9h8M8 13h5"/></>,
    catalog: <><path d="M4 5h16v14H4z"/><path d="M4 9h16M9 9v10"/></>,
    offers: <><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    send: <><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></>,
    spark: <><path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    arrow: <path d="m9 18 6-6-6-6"/>,
    plus: <path d="M12 5v14M5 12h14"/>,
    refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function BrandGlyph() {
  return <svg className="reference-logo" viewBox="220 103 835 245" aria-hidden="true">
    <image href={brandReference} width="1280" height="490" />
  </svg>;
}

function SanaFace({ mood = "ready" }) {
  return <span className={`sana-face sana-face-${mood}`} aria-hidden="true">
    <i className="sana-eye sana-eye-left" />
    <i className="sana-eye sana-eye-right" />
    <i className="sana-mouth" />
    {mood === "thinking" && <span className="thought-dots"><i /><i /><i /></span>}
    {mood === "sleeping" && <span className="sleep-z">z</span>}
  </span>;
}

function SanaMascot({ mood = "ready", compact = false }) {
  const labels = { ready: "Sana готова помочь", curious: "Sana слушает", thinking: "Sana думает", happy: "Карточка готова", worried: "Проверьте сообщение", sleeping: "Sana отдыхает" };
  return <div className={`sana-mascot reference-mascot sana-mascot-${mood} ${compact ? "sana-mascot-compact" : ""}`} role="img" aria-label={labels[mood]}>
    <svg className="reference-head" viewBox="0 0 165 137" aria-hidden="true" shapeRendering="crispEdges">
      <g fill="none" stroke="#18e98a" strokeWidth="5">
        <path d="M82 48V19M68 48V37H61V29H52M96 48V37H103V29H113" />
        <path d="M76 5H89V18H76ZM42 19H54V31H42ZM111 19H123V31H111Z" />
      </g>
      <path fill="#07894c" d="M8 72H17V115H8ZM148 72H157V115H148Z" />
      <path fill="#35f49d" d="M5 77H11V109H5ZM154 77H160V109H154Z" />
      <path fill="#10d878" d="M34 51H131V56H141V63H148V119H141V127H131V132H34V127H24V119H17V63H24V56H34Z" />
      <path fill="#92ffcb" d="M34 51H131V56H141V63H135V60H30V64H24V59H34Z" />
      <path fill="#079956" d="M24 116H31V123H135V116H148V119H141V127H131V132H34V127H24Z" />
      <path fill="#00150c" d="M35 65H130V70H137V113H130V120H35V113H28V72H35Z" />
    </svg>
    <SanaFace mood={mood} />
  </div>;
}

function Toast({ toast }) {
  if (!toast) return null;
  return <div className={`toast ${toast.error ? "toast-error" : ""}`}>{toast.text}</div>;
}

function ScoreRing({ rating, compact = false }) {
  const score = Number(rating?.score) || 0;
  const level = rating?.level || "draft";
  const color = LEVELS[level]?.[1] || LEVELS.draft[1];
  return (
    <div className={`score-ring ${compact ? "score-ring-compact" : ""}`} style={{ "--score": score, "--score-color": color }}>
      <div><strong>{score}</strong><span>/100</span></div>
    </div>
  );
}

function RatingPanel({ rating }) {
  const score = Number(rating?.score) || 0;
  const level = rating?.level || "draft";
  const next = score < 40 ? 40 : score < 70 ? 70 : score < 90 ? 90 : 100;
  const left = Math.max(0, next - score);
  return (
    <section className="rating-card">
      <div className="rating-summary">
        <ScoreRing rating={rating} />
        <div>
          <span className="eyebrow">ГОТОВНОСТЬ ЗАДАЧИ</span>
          <h3>{LEVELS[level]?.[0]}</h3>
          <p>{left ? `Ещё ${left} баллов до следующего уровня` : "Максимальный уровень достигнут"}</p>
        </div>
      </div>
      <div className="metric-list">
        {(rating?.breakdown || []).map((item) => (
          <div className="metric" key={item.key}>
            <div><span>{METRIC_LABELS[item.key] || item.label}</span><strong>{item.earned}/{item.max}</strong></div>
            <div className="metric-track"><i style={{ width: `${(item.earned / item.max) * 100}%` }} /></div>
          </div>
        ))}
      </div>
      {!!rating?.tips?.length && (
        <div className="rating-tip"><Icon name="spark" /><span>{rating.tips[0]}</span></div>
      )}
    </section>
  );
}

function CardEditor({ card, setCard, onPublish, busy, businessProfile, mascotMood, expanded, onToggle, editing = false }) {
  const applyProfile = () => {
    if (!businessProfile?.name && !businessProfile?.email) return;
    setCard((current) => ({
      ...current,
      contact: [businessProfile.name, businessProfile.company, businessProfile.email].filter(Boolean).join(" · "),
    }));
  };
  return (
    <div className={`preview-panel ${expanded ? "" : "collapsed"}`}>
      <header className="panel-heading">
        <div className="preview-heading-copy"><span className="eyebrow">ЖИВАЯ КАРТОЧКА</span><h2>Задача собирается справа</h2></div>
        <div className="preview-heading-actions">
          <span className="live-dot"><i /> обновляется</span>
          <button
            className="preview-toggle"
            type="button"
            aria-expanded={expanded}
            aria-label={expanded ? "Свернуть живую карточку" : "Открыть живую карточку"}
            title={expanded ? "Свернуть карточку" : "Открыть карточку"}
            onClick={onToggle}
          >
            <Icon name="arrow" />
          </button>
        </div>
      </header>
      {expanded && (!card ? (
        <div className="empty-preview">
          <SanaMascot mood={mascotMood} />
          <span className="assistant-kicker"><i /> Sana рядом на каждом шаге</span>
          <h3>Здесь появится карточка</h3>
          <p>Расскажите AI о задаче и ответьте на уточняющие вопросы. Поля и рейтинг будут заполняться только вашими фактами.</p>
        </div>
      ) : (
        <div className="card-editor-wrap">
          <div className="card-form">
            <div className="field full">
              <label>Отрасль</label>
              <select value={card.industry || "online_school"} onChange={(e) => setCard({ ...card, industry: e.target.value })}>
                {Object.entries(INDUSTRIES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
            {FIELD_DEFS.map(([key, label, type]) => (
              <div className={`field ${["title", "context", "need", "users", "data_materials", "constraints", "expected_result", "success_criteria"].includes(key) ? "full" : ""}`} key={key}>
                <label>{label}</label>
                {type === "input" ? (
                  <input value={card[key] || ""} maxLength={4000} onChange={(e) => setCard({ ...card, [key]: e.target.value })} />
                ) : (
                  <textarea value={card[key] || ""} maxLength={4000} onChange={(e) => setCard({ ...card, [key]: e.target.value })} />
                )}
              </div>
            ))}
            <button className="text-button" type="button" onClick={applyProfile}>Подставить контакт из профиля</button>
          </div>
          <RatingPanel rating={card.rating} />
          <div className="publish-bar">
            <div><Icon name="check" /><span><strong>Публикация только вручную</strong><small>Проверьте факты перед подтверждением</small></span></div>
            <button className="primary-button" type="button" disabled={busy} onClick={onPublish}>{busy ? "Сохраняем…" : editing ? "Сохранить изменения" : "Подтвердить и опубликовать"}</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function ChatWorkspace({ notify, ownerTokens, setOwnerTokens, businessProfile, onPublished, editingTask, onEditingFinished }) {
  const savedDraft = readJson("sana-chat-draft", { text: "", industry: "online_school" });
  const [messages, setMessages] = useState(editingTask ? [
    { role: "ai", text: "Задача открыта для редактирования. Измените поля справа — рейтинг пересчитается автоматически." },
  ] : [
    { role: "ai", text: "Привет! Я Sana. Опишите бизнес-задачу своими словами — я найду пробелы и задам минимум три точных вопроса." },
  ]);
  const [composer, setComposer] = useState(editingTask ? "" : savedDraft.text || "");
  const [industry, setIndustry] = useState(editingTask?.industry || savedDraft.industry || "online_school");
  const [cardExpanded, setCardExpanded] = useState(true);
  const [questions, setQuestions] = useState([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [draft, setDraft] = useState("");
  const [phase, setPhase] = useState(editingTask ? "card" : "draft");
  const [card, setCard] = useState(editingTask ? { ...initialCard(), ...editingTask } : null);
  const [source, setSource] = useState(editingTask ? "saved" : "");
  const [busy, setBusy] = useState(false);
  const [idle, setIdle] = useState(false);
  const messagesRef = useRef(null);

  const cardFingerprint = card ? FIELD_DEFS.map(([key]) => card[key] || "").concat(card.industry || "").join("\u0001") : "";
  useEffect(() => {
    const container = messagesRef.current;
    if (container) container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);
  useEffect(() => {
    setIdle(false);
    if (busy) return undefined;
    const timer = window.setTimeout(() => setIdle(true), 18000);
    return () => window.clearTimeout(timer);
  }, [messages, composer, phase, busy]);
  useEffect(() => {
    if (phase === "draft") saveJson("sana-chat-draft", { text: composer, industry });
  }, [composer, industry, phase]);
  useEffect(() => {
    if (!card) return undefined;
    const timer = setTimeout(async () => {
      try {
        const result = await api("/api/rating", { method: "POST", body: { card } });
        setCard((current) => current ? { ...current, rating: result.rating } : current);
      } catch { /* Keep the last visible rating while typing. */ }
    }, 350);
    return () => clearTimeout(timer);
  }, [cardFingerprint]);

  const append = (...items) => setMessages((current) => [...current, ...items]);

  async function buildCard(nextAnswers) {
    setBusy(true);
    append({ role: "ai", text: "Спасибо. Собираю карточку только из того, что вы сообщили…", pending: true });
    try {
      const result = await api("/api/build-card", {
        method: "POST",
        body: {
          draft,
          industry,
          locale: "ru",
          answers: Object.entries(nextAnswers).map(([key, answer]) => ({ key, answer })),
        },
      });
      setCard({ ...initialCard(), ...result.card, industry });
      setSource(result.source);
      setPhase("card");
      setMessages((current) => [...current.filter((item) => !item.pending), {
        role: "ai", text: "Карточка готова. Проверьте её справа: неизвестные сведения оставлены пустыми, а рейтинг уже показывает, что можно усилить.",
      }]);
    } catch (error) {
      setMessages((current) => [...current.filter((item) => !item.pending), { role: "ai", text: error.message, error: true }]);
    } finally { setBusy(false); }
  }

  async function sendMessage(skip = false, suggestedAnswer = "") {
    const text = skip ? "" : (suggestedAnswer || composer).trim();
    if (!text && !skip) return;
    if (phase === "card") {
      append({ role: "user", text }, { role: "ai", text: "Карточка уже собрана. Измените нужное поле справа — рейтинг пересчитается автоматически." });
      setComposer("");
      return;
    }
    if (phase === "draft") {
      setDraft(text);
      try { localStorage.removeItem("sana-chat-draft"); } catch { /* Continue without persistence. */ }
      setComposer("");
      append({ role: "user", text });
      setBusy(true);
      try {
        const result = await api("/api/analyze", { method: "POST", body: { draft: text, industry, locale: "ru" } });
        setQuestions(result.questions || []);
        setSource(result.source);
        setPhase("questions");
        setQuestionIndex(0);
        append({ role: "ai", text: result.questions?.[0]?.question || "Что именно необходимо изменить?" });
      } catch (error) { append({ role: "ai", text: error.message, error: true }); }
      finally { setBusy(false); }
      return;
    }
    const current = questions[questionIndex];
    const nextAnswers = text ? { ...answers, [current.key]: text } : answers;
    setAnswers(nextAnswers);
    append({ role: "user", text: text || "Пока не знаю", muted: skip });
    setComposer("");
    if (questionIndex + 1 < questions.length) {
      const next = questionIndex + 1;
      setQuestionIndex(next);
      append({ role: "ai", text: questions[next].question });
    } else {
      await buildCard(nextAnswers);
    }
  }

  const currentSuggestions = phase === "questions"
    ? questions[questionIndex]?.suggestions || []
    : [];

  async function loadDemo() {
    try {
      const result = await api("/api/demo");
      const demoDraft = result.draft || result.text || "Нужно сократить время проверки домашних работ по Python";
      setComposer(demoDraft);
      setIndustry(result.industry || "online_school");
      notify("Демонстрационный черновик загружен");
    } catch { setComposer("Нужно сократить время проверки домашних работ по Python"); }
  }

  async function publish() {
    if (!card?.title?.trim()) return notify("Добавьте название задачи", true);
    setBusy(true);
    try {
      const result = editingTask
        ? await api(`/api/tasks/${encodeURIComponent(editingTask.id)}`, { method: "PUT", body: { card }, ownerToken: ownerTokens[editingTask.id] })
        : await api("/api/tasks", { method: "POST", body: { card } });
      if (!editingTask) {
        const nextTokens = { ...ownerTokens, [result.task.id]: result.owner_token };
        setOwnerTokens(nextTokens);
        saveJson("sana-owner-tokens", nextTokens);
      }
      notify(editingTask ? "Изменения сохранены, рейтинг пересчитан" : "Задача подтверждена и появилась в открытом каталоге");
      onEditingFinished?.();
      onPublished();
    } catch (error) { notify(error.message, true); }
    finally { setBusy(false); }
  }

  function reset() {
    setMessages([{ role: "ai", text: "Начнём заново. Опишите задачу одним сообщением." }]);
    setComposer(""); setQuestions([]); setAnswers({}); setQuestionIndex(0); setDraft(""); setCard(null); setPhase("draft"); setSource("");
    try { localStorage.removeItem("sana-chat-draft"); } catch { /* Ignore storage failures. */ }
    onEditingFinished?.();
  }

  const lastMessage = messages[messages.length - 1];
  const mascotMood = busy
    ? "thinking"
    : lastMessage?.error
      ? "worried"
      : phase === "card"
        ? "happy"
        : idle
          ? "sleeping"
          : composer.trim()
            ? "curious"
            : "ready";

  return (
    <main className={`workspace-shell ${cardExpanded ? "" : "card-collapsed"}`}>
      <section className="workspace-intro">
        <div><span className="eyebrow">SANA · AI-КОНСТРУКТОР</span><h1>От идеи — к понятной задаче</h1><p>Опишите цель. Sana задаст вопросы и поможет подготовить карточку для команды.</p></div>
        <SanaMascot mood={mascotMood} />
      </section>
      <div className="workflow-steps" aria-label="Этапы подготовки задачи">
        {[["draft", "Опишите задачу"], ["questions", "Ответьте Sana"], ["card", "Проверьте и опубликуйте"]].map(([step, label], index) => <div key={step} className={phase === step ? "current" : ""} aria-current={phase === step ? "step" : undefined}><span>{String(index + 1).padStart(2, "0")}</span>{label}</div>)}
      </div>
      <section className="chat-panel">
        <header className="panel-heading chat-heading">
          <div className="chat-title"><div className="agent-presence"><SanaMascot mood={mascotMood} compact /></div><div><span className="eyebrow">AI-КОНСТРУКТОР</span><h2>Диалог с Sana</h2></div></div>
          <div className="chat-actions">{phase === "questions" && <span className="source-badge">Вопрос {questionIndex + 1}/{questions.length}</span>}<span className={`source-badge ${source}`}>{source === "ai" ? "AI" : source === "fallback" ? "Резервный режим" : source === "saved" ? "Редактирование" : "онлайн"}</span><button className="icon-button" onClick={reset} title="Начать заново"><Icon name="refresh" /></button></div>
        </header>
        <div className="industry-row">
          <label>Тема задачи</label>
          <select value={industry} disabled={phase !== "draft"} onChange={(e) => setIndustry(e.target.value)}>
            {Object.entries(INDUSTRIES).filter(([key]) => key !== "education").map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
        <div className="messages" ref={messagesRef}>
          {messages.map((message, index) => (
            <div className={`message-row ${message.role}`} key={`${message.role}-${index}`}>
              {message.role === "ai" && <div className="ai-avatar"><SanaMascot mood={message.pending ? "thinking" : message.error ? "worried" : "ready"} compact /></div>}
              <div className={`message ${message.error ? "message-error" : ""} ${message.muted ? "muted" : ""}`}>{message.text}{message.pending && <span className="typing"><i/><i/><i/></span>}</div>
            </div>
          ))}
        </div>
        <div className="composer-wrap">
          {phase === "draft" && <button type="button" className="demo-chip" onClick={loadDemo}><Icon name="spark" /> Загрузить пример</button>}
          {phase === "questions" && currentSuggestions.map((suggestion, index) => (
            <button type="button" className="demo-chip" disabled={busy} key={`${questionIndex}-${index}`} onClick={() => sendMessage(false, suggestion)}>
              {index + 1}. {suggestion}
            </button>
          ))}
          <div className="composer">
            <textarea
              aria-label="Сообщение Sana"
              value={composer}
              disabled={busy}
              placeholder={phase === "draft" ? "Опишите задачу бизнеса…" : phase === "questions" ? "Ответьте своими словами…" : "Карточка готова — редактируйте справа"}
              onChange={(e) => setComposer(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
            />
            <button type="button" aria-label="Отправить сообщение" disabled={busy || !composer.trim()} onClick={() => sendMessage()}><Icon name="send" /></button>
          </div>
          <div className="composer-foot">
            <span>Enter — отправить · Shift+Enter — новая строка</span>
            {phase === "questions" && <button type="button" onClick={() => sendMessage(true)}>Не знаю, пропустить</button>}
          </div>
        </div>
      </section>
      <CardEditor card={card} setCard={setCard} onPublish={publish} busy={busy} businessProfile={businessProfile} mascotMood={mascotMood} expanded={cardExpanded} onToggle={() => setCardExpanded((current) => !current)} editing={Boolean(editingTask)} />
    </main>
  );
}

function ProposalForm({ task, selectedTeam, teamTokens, notify, onDone }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    if (!selectedTeam) return notify("Сначала создайте профиль команды", true);
    const body = Object.fromEntries(new FormData(event.currentTarget).entries());
    setBusy(true);
    try {
      await api(`/api/tasks/${encodeURIComponent(task.id)}/proposals`, { method: "POST", body: { ...body, team_id: selectedTeam }, teamToken: teamTokens[selectedTeam] });
      notify("Предложение отправлено бизнесу"); setOpen(false); onDone?.();
    } catch (error) { notify(error.message, true); }
    finally { setBusy(false); }
  }
  return <>
    <button className="primary-button small" onClick={() => setOpen(!open)}>{selectedTeam ? "Предложить решение" : "Сначала создайте команду"}</button>
    {open && selectedTeam && <form className="proposal-form" onSubmit={submit}>
      <textarea name="idea" placeholder="Идея решения" required maxLength="2000" />
      <textarea name="plan" placeholder="Короткий план работы" required maxLength="2000" />
      <div className="form-row"><input name="deadline" placeholder="Срок, например 3 недели" required /><input name="link" type="url" placeholder="https://prototype.example" required /></div>
      <button className="dark-button" disabled={busy}>{busy ? "Отправляем…" : "Отправить предложение"}</button>
    </form>}
  </>;
}

function Catalog({ role, selectedTeam, teamTokens, notify }) {
  const [tasks, setTasks] = useState([]);
  const [recommendations, setRecommendations] = useState({});
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ industry: "", level: "", sort: "rating" });
  const [expanded, setExpanded] = useState("");
  async function load() {
    setLoading(true);
    const params = new URLSearchParams({ sort: filters.sort });
    if (filters.industry) params.set("industry", filters.industry);
    if (filters.level) params.set("level", filters.level);
    try { const result = await api(`/api/tasks?${params}`); setTasks(result.tasks || []); }
    catch (error) { notify(error.message, true); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [filters.industry, filters.level, filters.sort]);
  useEffect(() => {
    if (role !== "student" || !selectedTeam) { setRecommendations({}); return; }
    api(`/api/recommendations?team_id=${encodeURIComponent(selectedTeam)}`)
      .then((result) => setRecommendations(result.reason || {}))
      .catch(() => setRecommendations({}));
  }, [role, selectedTeam]);
  const visibleTasks = role === "student" && Object.keys(recommendations).length
    ? [...tasks].sort((a, b) => Number(Boolean(recommendations[b.id])) - Number(Boolean(recommendations[a.id])))
    : tasks;
  return <main className="page-shell">
    <header className="page-hero"><div><span className="eyebrow">ОТКРЫТЫЙ КАТАЛОГ</span><h1>Задачи, готовые к работе</h1><p>Низкий рейтинг ничего не скрывает — любая команда может откликнуться.</p></div><button className="outline-button" onClick={load}><Icon name="refresh" /> Обновить</button></header>
    <div className="filter-bar">
      <select value={filters.industry} onChange={(e) => setFilters({ ...filters, industry: e.target.value })}><option value="">Все отрасли</option>{Object.entries(INDUSTRIES).map(([v,l]) => <option value={v} key={v}>{l}</option>)}</select>
      <select value={filters.level} onChange={(e) => setFilters({ ...filters, level: e.target.value })}><option value="">Любая готовность</option>{Object.entries(LEVELS).map(([v,[l]]) => <option value={v} key={v}>{l}</option>)}</select>
      <select value={filters.sort} onChange={(e) => setFilters({ ...filters, sort: e.target.value })}><option value="rating">Сначала высокий рейтинг</option><option value="date">Сначала новые</option></select>
      <span>{tasks.length} задач{role === "student" && Object.keys(recommendations).length ? " · рекомендации сверху" : ""}</span>
    </div>
    {loading ? <div className="loading-grid">Загружаем каталог…</div> : !tasks.length ? <Empty title="Пока нет опубликованных задач" text="Создайте первую задачу в AI-конструкторе." /> : (
      <div className="task-grid">{visibleTasks.map((task) => {
        const isOpen = expanded === task.id;
        return <article className={`task-card ${isOpen ? "expanded" : ""}`} key={task.id}>
          <div className="task-top"><span className="industry-pill">{recommendations[task.id] ? `Рекомендовано · ${recommendations[task.id].matched_profile_terms} совп.` : INDUSTRIES[task.industry] || task.industry}</span><ScoreRing compact rating={task.rating} /></div>
          <h3>{task.title}</h3><p>{task.need || task.context || "Описание уточняется"}</p>
          <div className="task-meta"><span style={{ color: LEVELS[task.rating?.level]?.[1] }}>● {LEVELS[task.rating?.level]?.[0]}</span><span>{new Date(task.created_at).toLocaleDateString("ru-RU")}</span></div>
          <button className="details-button" onClick={() => setExpanded(isOpen ? "" : task.id)}>Подробнее <Icon name="arrow" /></button>
          {isOpen && <div className="task-details">
            {FIELD_DEFS.filter(([key]) => key !== "title").map(([key,label]) => <div key={key}><strong>{label}</strong><span>{task[key] || "Не указано"}</span></div>)}
            <RatingPanel rating={task.rating} />
            {role === "student" && <ProposalForm task={task} selectedTeam={selectedTeam} teamTokens={teamTokens} notify={notify} />}
          </div>}
        </article>;
      })}</div>
    )}
  </main>;
}

function Empty({ title, text }) {
  return <div className="empty-page"><div><Icon name="spark" /></div><h3>{title}</h3><p>{text}</p></div>;
}

function BusinessOffers({ ownerTokens, notify, onEdit, teams }) {
  const [groups, setGroups] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  async function load() {
    setLoading(true);
    try {
      const [{ tasks }, progressBoard] = await Promise.all([api("/api/tasks?sort=date"), api("/api/progress")]);
      const owned = tasks.filter((task) => ownerTokens[task.id]);
      const loaded = await Promise.all(owned.map(async (task) => {
        const result = await api(`/api/tasks/${task.id}/proposals`, { ownerToken: ownerTokens[task.id] });
        const proposals = await Promise.all((result.proposals || []).map(async (proposal) => ({
          ...proposal,
          progress: (await api(`/api/proposals/${proposal.id}/progress`, { ownerToken: ownerTokens[task.id] })).progress || [],
        })));
        return { task, proposals };
      }));
      setGroups(loaded); setLeaderboard(progressBoard.teams || []);
    } catch (error) { notify(error.message, true); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [Object.keys(ownerTokens).join("|")]);
  async function decide(taskId, proposalId, decision) {
    try { await api(`/api/proposals/${proposalId}/decision`, { method: "POST", body: { decision }, ownerToken: ownerTokens[taskId] }); notify(decision === "accepted" ? "Команда выбрана" : "Предложение отклонено"); load(); }
    catch (error) { notify(error.message, true); }
  }
  async function decideProgress(taskId, progressId, decision) {
    try { await api(`/api/progress/${progressId}/decision`, { method: "POST", body: { decision }, ownerToken: ownerTokens[taskId] }); notify(decision === "confirmed" ? "Этап подтверждён: команде начислены баллы" : "Этап отклонён"); load(); }
    catch (error) { notify(error.message, true); }
  }
  if (loading) return <div className="loading-grid">Загружаем предложения…</div>;
  if (!groups.length) return <Empty title="У вас ещё нет опубликованных задач" text="Создайте задачу в AI-конструкторе — она появится здесь." />;
  return <>
    {!!leaderboard.length && <div className="leaderboard"><div><span className="eyebrow">ПРОГРЕСС КОМАНД</span><h3>Таблица подтверждённых результатов</h3></div>{leaderboard.slice(0,5).map((team,index) => <div className="leader-row" key={team.id}><b>{index + 1}</b><span>{team.name}</span><strong>{team.progress_points} баллов</strong></div>)}</div>}
    <div className="offer-groups">{groups.map(({ task, proposals }) => <section className="offer-group" key={task.id}>
      <header><div><span className="eyebrow">{INDUSTRIES[task.industry]}</span><h2>{task.title}</h2><button className="text-button" type="button" onClick={() => onEdit(task)}>Редактировать и пересчитать рейтинг</button></div><div className="offer-count">{proposals.length}<small>откликов</small></div></header>
      {!proposals.length ? <p className="soft-empty">Откликов пока нет — задача доступна всем командам.</p> : proposals.map((proposal) => <article className="offer-card" key={proposal.id}>
        <div className="offer-head"><strong>{teams.find((team) => team.id === proposal.team_id)?.name || `Команда ${proposal.team_id}`}</strong><span className={`status ${proposal.status}`}>{proposal.status === "new" ? "Новое" : proposal.status === "accepted" ? "Выбрано" : "Отклонено"}</span></div>
        <p><b>Идея:</b> {proposal.idea}</p><p><b>План:</b> {proposal.plan}</p><div className="offer-meta"><span>Срок: {proposal.deadline}</span><a href={proposal.link} target="_blank" rel="noreferrer">Прототип ↗</a></div>
        {proposal.status === "new" && <div className="button-row"><button className="primary-button small" onClick={() => decide(task.id, proposal.id, "accepted")}>Выбрать</button><button className="ghost-button" onClick={() => decide(task.id, proposal.id, "rejected")}>Отклонить</button></div>}
        {proposal.progress.map((entry) => <div className="progress-entry" key={entry.id}><div><b>Результат этапа</b><p>{entry.result}</p><a href={entry.evidence_link} target="_blank" rel="noreferrer">Открыть доказательство ↗</a></div><span className={`status ${entry.status}`}>{entry.status === "submitted" ? "К проверке" : entry.status === "confirmed" ? `+${entry.points} баллов` : "Отклонено"}</span>{entry.status === "submitted" && <div className="button-row"><button className="primary-button small" onClick={() => decideProgress(task.id, entry.id, "confirmed")}>Подтвердить</button><button className="ghost-button" onClick={() => decideProgress(task.id, entry.id, "rejected")}>Отклонить</button></div>}</div>)}
      </article>)}
    </section>)}</div>
  </>;
}

function TeamOffers({ selectedTeam, teamTokens, notify }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  async function load() {
    if (!selectedTeam) { setItems([]); setLoading(false); return; }
    setLoading(true);
    try {
      const { proposals } = await api(`/api/teams/${selectedTeam}/proposals`, { teamToken: teamTokens[selectedTeam] });
      const loaded = await Promise.all(proposals.map(async (proposal) => {
        const { task } = await api(`/api/tasks/${proposal.task_id}`);
        const progress = proposal.status === "accepted" ? (await api(`/api/proposals/${proposal.id}/progress`, { teamToken: teamTokens[selectedTeam] })).progress : [];
        return { proposal, task, progress };
      })); setItems(loaded);
    } catch (error) { notify(error.message, true); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [selectedTeam]);
  async function submitProgress(event, proposalId) {
    event.preventDefault();
    const form = event.currentTarget;
    try { await api(`/api/proposals/${proposalId}/progress`, { method: "POST", body: Object.fromEntries(new FormData(form).entries()), teamToken: teamTokens[selectedTeam] }); notify("Результат отправлен бизнесу"); form.reset(); load(); }
    catch (error) { notify(error.message, true); }
  }
  if (loading) return <div className="loading-grid">Загружаем предложения команды…</div>;
  if (!selectedTeam) return <Empty title="Сначала создайте профиль команды" text="После этого вы сможете откликаться на задачи и отслеживать решения бизнеса." />;
  if (!items.length) return <Empty title="Предложений пока нет" text="Откройте каталог и выберите интересную задачу." />;
  return <div className="offer-groups">{items.map(({ proposal, task, progress }) => <section className="offer-group" key={proposal.id}>
    <header><div><span className="eyebrow">{INDUSTRIES[task.industry]}</span><h2>{task.title}</h2></div><span className={`status ${proposal.status}`}>{proposal.status === "new" ? "На рассмотрении" : proposal.status === "accepted" ? "Выбрано" : "Отклонено"}</span></header>
    <p>{proposal.idea}</p>
    {proposal.status === "accepted" && <form className="progress-form" onSubmit={(e) => submitProgress(e, proposal.id)}><textarea name="result" placeholder="Какой фактический результат получен?" required /><input name="evidence_link" type="url" placeholder="Ссылка на доказательство" required /><button className="primary-button small">Отправить этап на проверку</button></form>}
    {progress.map((entry) => <div className="progress-entry" key={entry.id}><p>{entry.result}</p><span className={`status ${entry.status}`}>{entry.status === "submitted" ? "Ожидает проверки" : entry.status === "confirmed" ? `Подтверждено · +${entry.points}` : "Не подтверждено"}</span></div>)}
  </section>)}</div>;
}

function Offers({ role, ownerTokens, selectedTeam, teamTokens, notify, teams, onEdit }) {
  return <main className="page-shell"><header className="page-hero"><div><span className="eyebrow">{role === "business" ? "ПРОСТРАНСТВО БИЗНЕСА" : "МОЯ КОМАНДА"}</span><h1>{role === "business" ? "Предложения и решения" : "Наши отклики и прогресс"}</h1><p>{role === "business" ? "Сравнивайте идеи и выбирайте одну, несколько или ни одной команды." : "Следите за решением бизнеса и отправляйте подтверждённые результаты."}</p></div></header>{role === "business" ? <BusinessOffers ownerTokens={ownerTokens} notify={notify} onEdit={onEdit} teams={teams} /> : <TeamOffers selectedTeam={selectedTeam} teamTokens={teamTokens} notify={notify} />}</main>;
}

function Profile({ role, businessProfile, setBusinessProfile, teams, setTeams, selectedTeam, setSelectedTeam, teamTokens, setTeamTokens, ownerTokens, setOwnerTokens, notify }) {
  const [form, setForm] = useState(businessProfile);
  const [teamForm, setTeamForm] = useState({ name: "", interests: "", skills: "", technologies: "" });
  const [accessCode, setAccessCode] = useState("");
  function saveBusiness(event) {
    event.preventDefault(); setBusinessProfile(form); saveJson("sana-business-profile", form); notify("Профиль бизнеса сохранён");
  }
  async function copyAccess(kind, id, token) {
    const code = `${kind}:${id}:${token}`;
    try { await navigator.clipboard.writeText(code); notify("Код доступа скопирован"); }
    catch { setAccessCode(code); notify("Скопируйте код из поля вручную"); }
  }
  async function restoreAccess(event) {
    event.preventDefault();
    const match = accessCode.trim().match(/^(task|team):([^:]+):(.+)$/);
    if (!match) return notify("Неверный формат кода доступа", true);
    const [, kind, id, token] = match;
    try {
      if (kind === "task") {
        await api(`/api/tasks/${encodeURIComponent(id)}/proposals`, { ownerToken: token });
        const next = { ...ownerTokens, [id]: token }; setOwnerTokens(next); saveJson("sana-owner-tokens", next);
      } else {
        await api(`/api/teams/${encodeURIComponent(id)}/proposals`, { teamToken: token });
        const next = { ...teamTokens, [id]: token }; setTeamTokens(next); saveJson("sana-team-tokens", next); setSelectedTeam(id); localStorage.setItem("sana-selected-team", id);
      }
      setAccessCode(""); notify("Доступ восстановлен и проверен сервером");
    } catch (error) { notify(error.message, true); }
  }
  async function createTeam(event) {
    event.preventDefault();
    const body = { name: teamForm.name, interests: teamForm.interests.split(",").map(v=>v.trim()).filter(Boolean), skills: teamForm.skills.split(",").map(v=>v.trim()).filter(Boolean), technologies: teamForm.technologies.split(",").map(v=>v.trim()).filter(Boolean) };
    try {
      const result = await api("/api/teams", { method: "POST", body });
      const nextTokens = { ...teamTokens, [result.team.id]: result.team_token };
      setTeamTokens(nextTokens); saveJson("sana-team-tokens", nextTokens); setTeams([...teams, result.team]); setSelectedTeam(result.team.id); localStorage.setItem("sana-selected-team", result.team.id); notify("Профиль команды создан"); setTeamForm({ name: "", interests: "", skills: "", technologies: "" });
    } catch (error) { notify(error.message, true); }
  }
  const ownedTeams = teams.filter((team) => teamTokens[team.id]);
  return <main className="page-shell profile-page"><header className="page-hero"><div><span className="eyebrow">ПРОФИЛЬ</span><h1>{role === "business" ? "Представитель бизнеса" : "Студенческая команда"}</h1><p>Профиль помогает быстрее заполнять карточки и получать релевантные задачи.</p></div></header>
    {role === "business" ? <form className="profile-card" onSubmit={saveBusiness}>
      <div className="profile-avatar">{(form.name || "Б").slice(0,1).toUpperCase()}</div><div className="profile-fields"><label>Имя<input value={form.name || ""} onChange={(e)=>setForm({...form,name:e.target.value})} placeholder="Айдана" required /></label><label>Компания<input value={form.company || ""} onChange={(e)=>setForm({...form,company:e.target.value})} placeholder="Sana Education" /></label><label>Роль<input value={form.role || ""} onChange={(e)=>setForm({...form,role:e.target.value})} placeholder="Руководитель продукта" /></label><label>Email<input type="email" value={form.email || ""} onChange={(e)=>setForm({...form,email:e.target.value})} placeholder="name@company.kz" /></label><label className="full">О компании<textarea value={form.about || ""} onChange={(e)=>setForm({...form,about:e.target.value})} placeholder="Коротко расскажите о направлении бизнеса" /></label><button className="primary-button">Сохранить профиль</button></div>
    </form> : <div className="team-profile-grid">
      <form className="profile-card team-create" onSubmit={createTeam}><div className="profile-avatar"><Icon name="plus" /></div><div className="profile-fields"><h2>Новая команда</h2><label className="full">Название<input value={teamForm.name} onChange={(e)=>setTeamForm({...teamForm,name:e.target.value})} placeholder="Sana Lab" required /></label><label className="full">Интересы<input value={teamForm.interests} onChange={(e)=>setTeamForm({...teamForm,interests:e.target.value})} placeholder="Образование, аналитика" /></label><label>Навыки<input value={teamForm.skills} onChange={(e)=>setTeamForm({...teamForm,skills:e.target.value})} placeholder="Python, UX" /></label><label>Технологии<input value={teamForm.technologies} onChange={(e)=>setTeamForm({...teamForm,technologies:e.target.value})} placeholder="FastAPI, React" /></label><button className="primary-button">Создать команду</button></div></form>
      <section className="owned-teams"><span className="eyebrow">МОИ КОМАНДЫ</span><h2>Рабочий профиль</h2>{!ownedTeams.length ? <p>Создайте первую команду, чтобы отправлять предложения.</p> : ownedTeams.map((team)=><button className={`team-select-card ${selectedTeam===team.id?"active":""}`} key={team.id} onClick={()=>{setSelectedTeam(team.id);localStorage.setItem("sana-selected-team",team.id);}}><span>{team.name.slice(0,1)}</span><div><strong>{team.name}</strong><small>{[...(team.skills||[]),...(team.technologies||[])].join(" · ") || "Профиль команды"}</small></div>{selectedTeam===team.id&&<Icon name="check"/>}</button>)}</section>
    </div>}
    <section className="offer-group access-card">
      <div><span className="eyebrow">ДОСТУП С ДРУГОГО УСТРОЙСТВА</span><h2>Резервные коды</h2><p>Код даёт право управлять задачей или командой. Передавайте его только себе и участникам команды.</p></div>
      <div className="access-list">
        {Object.entries(ownerTokens).map(([id, token]) => <button className="ghost-button" type="button" key={`task-${id}`} onClick={() => copyAccess("task", id, token)}>Задача {id} · скопировать код</button>)}
        {Object.entries(teamTokens).map(([id, token]) => <button className="ghost-button" type="button" key={`team-${id}`} onClick={() => copyAccess("team", id, token)}>{teams.find((team) => team.id === id)?.name || `Команда ${id}`} · скопировать код</button>)}
        {!Object.keys(ownerTokens).length && !Object.keys(teamTokens).length && <span>Коды появятся после создания задачи или команды.</span>}
      </div>
      <form className="progress-form access-import" onSubmit={restoreAccess}><input value={accessCode} onChange={(event) => setAccessCode(event.target.value)} placeholder="task:t_001:код или team:team_001:код" required /><button className="outline-button">Восстановить доступ</button></form>
    </section>
  </main>;
}

export default function App() {
  const [view, setView] = useState("workspace");
  const [role, setRole] = useState("business");
  const [toast, setToast] = useState(null);
  const [ownerTokens, setOwnerTokens] = useState(() => readJson("sana-owner-tokens", {}));
  const [teamTokens, setTeamTokens] = useState(() => readJson("sana-team-tokens", {}));
  const [teams, setTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState(() => localStorage.getItem("sana-selected-team") || "");
  const [businessProfile, setBusinessProfile] = useState(() => readJson("sana-business-profile", { name: "", company: "", role: "", email: "", about: "" }));
  const [service, setService] = useState("checking");
  const [editingTask, setEditingTask] = useState(null);

  function notify(text, error = false) {
    setToast({ text, error }); window.clearTimeout(window.__sanaToast); window.__sanaToast = window.setTimeout(() => setToast(null), 3500);
  }
  useEffect(() => {
    api("/api/health").then(() => setService("online")).catch(() => setService("offline"));
    api("/api/teams").then((result) => setTeams(result.teams || [])).catch(() => {});
  }, []);
  useEffect(() => {
    if (role === "student" && view === "workspace") setView("catalog");
  }, [role]);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [view, role]);
  const activeTeam = useMemo(() => teams.find((team) => team.id === selectedTeam), [teams, selectedTeam]);
  const nav = [
    ...(role === "business" ? [["workspace", "chat", "AI-конструктор"]] : []),
    ["catalog", "catalog", "Каталог"], ["offers", "offers", role === "business" ? "Мои задачи" : "Мои отклики"], ["profile", "user", "Профиль"],
  ];
  function editTask(task) {
    setEditingTask(task);
    setView("workspace");
  }
  return <div className="app">
    <header className="topbar">
      <button className="brand" aria-label="SaNa — главная" onClick={() => setView(role === "business" ? "workspace" : "catalog")}><BrandGlyph /><span className="brand-caption">AI БІЛІМ АГЕНТІ</span></button>
      <nav>{nav.map(([id,icon,label]) => <button aria-label={label} aria-current={view===id?"page":undefined} className={view===id?"active":""} key={id} onClick={()=>setView(id)}><Icon name={icon}/><span>{label}</span></button>)}</nav>
      <div className="top-actions"><span className={`service ${service}`}><i />{service === "online" ? "Сервер работает" : service === "offline" ? "Нет связи" : "Проверяем"}</span><div className="role-switch"><button className={role==="business"?"active":""} onClick={()=>setRole("business")}>Бизнес</button><button className={role==="student"?"active":""} onClick={()=>setRole("student")}>Команда</button></div><button className="profile-mini" onClick={()=>setView("profile")}><span>{role === "business" ? (businessProfile.name || "Б").slice(0,1).toUpperCase() : (activeTeam?.name || "К").slice(0,1).toUpperCase()}</span><div><strong>{role === "business" ? businessProfile.name || "Ваш профиль" : activeTeam?.name || "Создать команду"}</strong><small>{role === "business" ? businessProfile.company || "Представитель бизнеса" : "Студенческая команда"}</small></div></button></div>
    </header>
    {view === "workspace" && role === "business" && <ChatWorkspace key={editingTask?.id || "new"} notify={notify} ownerTokens={ownerTokens} setOwnerTokens={setOwnerTokens} businessProfile={businessProfile} editingTask={editingTask} onEditingFinished={()=>setEditingTask(null)} onPublished={()=>setView("offers")} />}
    {view === "catalog" && <Catalog role={role} selectedTeam={selectedTeam} teamTokens={teamTokens} notify={notify} />}
    {view === "offers" && <Offers role={role} ownerTokens={ownerTokens} selectedTeam={selectedTeam} teamTokens={teamTokens} teams={teams} notify={notify} onEdit={editTask} />}
    {view === "profile" && <Profile role={role} businessProfile={businessProfile} setBusinessProfile={setBusinessProfile} teams={teams} setTeams={setTeams} selectedTeam={selectedTeam} setSelectedTeam={setSelectedTeam} teamTokens={teamTokens} setTeamTokens={setTeamTokens} ownerTokens={ownerTokens} setOwnerTokens={setOwnerTokens} notify={notify} />}
    <Toast toast={toast} />
  </div>;
}
