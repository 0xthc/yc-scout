import { useState, useEffect, useCallback, useRef, useMemo } from "react";

const API = import.meta.env.VITE_API_URL || "";

// ── Design tokens ─────────────────────────────────────────────
const C = {
  bg: "#f8f8f6",
  surface: "#ffffff",
  border: "#e8e8e5",
  borderLight: "#f0f0ec",
  text: "#1a1a1a",
  textSub: "#666666",
  textMuted: "#aaaaaa",
  accent: "#1a1a1a",
  accentLight: "#f4f4f1",
  accentBorder: "#e0e0dc",
  green: "#2d6b2d",
  greenLight: "#eef5ee",
  amber: "#a06010",
  amberLight: "#fff8e8",
  red: "#a03030",
  redLight: "#fff0f0",
  blue: "#2050a0",
  blueLight: "#eef5ff",
  shadow: "0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03)",
  shadowMd: "0 4px 6px rgba(0,0,0,0.04), 0 2px 4px rgba(0,0,0,0.03)",
};

const SOURCE = {
  github: { color: "#1d4ed8", bg: "#eff6ff", label: "GH" },
  hn: { color: "#b45309", bg: "#fffbeb", label: "HN" },
  producthunt: { color: "#b91c1c", bg: "#fef2f2", label: "PH" },
};

const STATUS = {
  to_contact: { label: "To Contact", color: C.amber, bg: C.amberLight, border: "#fde68a" },
  watching: { label: "Watching", color: C.blue, bg: C.blueLight, border: "#bfdbfe" },
  contacted: { label: "Contacted", color: C.green, bg: C.greenLight, border: "#a7f3d0" },
  pass: { label: "Pass", color: C.textMuted, bg: C.bg, border: C.border },
};

const scoreColor = (s) => s >= 85 ? C.green : s >= 70 ? C.amber : s >= 50 ? C.blue : C.textMuted;
const scoreLabel = (s) => s >= 85 ? "Strong" : s >= 70 ? "Good" : s >= 50 ? "Monitor" : "Weak";

// dim key → [label, max points]
const DIMS = {
  founder_quality:    ["Pedigree",     35],
  execution_velocity: ["Velocity",     30],
  market_conviction:  ["Momentum",     25],
  deal_availability:  ["Availability", 10],
};

// ── Shared primitives ─────────────────────────────────────────

function Badge({ children, color = C.accent, bg = C.accentLight, border = C.accentBorder }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", padding: "2px 8px",
      borderRadius: 99, fontSize: 11, fontWeight: 600, lineHeight: 1.6,
      color, background: bg, border: `1px solid ${border}`,
    }}>{children}</span>
  );
}

function ScorePill({ score, size = "md" }) {
  const color = scoreColor(score);
  const pad = size === "sm" ? "2px 8px" : "3px 10px";
  const fs = size === "sm" ? 11 : 13;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: pad, borderRadius: 99, fontSize: fs, fontWeight: 700,
      color, background: `${color}12`, border: `1px solid ${color}30`,
      fontFamily: "ui-monospace, monospace",
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, display: "inline-block" }} />
      {score}
    </span>
  );
}

function ScoreBar({ label, value, max = 100 }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const color = scoreColor(Math.round(pct));
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: C.textSub }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: "ui-monospace, monospace" }}>
          {value}<span style={{ color: C.textMuted, fontWeight: 400 }}>/{max}</span>
        </span>
      </div>
      <div style={{ height: 5, background: C.borderLight, borderRadius: 4, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 4, transition: "width 0.5s ease" }} />
      </div>
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 12, boxShadow: C.shadow, ...style
    }}>{children}</div>
  );
}

function SectionTitle({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: "0.06em",
      textTransform: "uppercase", color: C.textMuted, marginBottom: 12,
    }}>{children}</div>
  );
}

function EmptyState({ title, sub }) {
  return (
    <div style={{ padding: 60, textAlign: "center" }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: C.accentLight, border: `1px solid ${C.accentBorder}`, margin: "0 auto 16px" }} />
      <div style={{ fontSize: 15, fontWeight: 600, color: C.text, marginBottom: 4 }}>{title}</div>
      <div style={{ fontSize: 13, color: C.textMuted }}>{sub}</div>
    </div>
  );
}

// ── Nav ───────────────────────────────────────────────────────

const VIEWS = ["raw", "field", "patterns", "breaks", "flow"];
const VIEW_LABELS = { raw: "Raw", field: "Field", patterns: "Patterns", breaks: "Breaks", flow: "Flow" };
const VIEW_ICONS = { raw: "", field: "", patterns: "", breaks: "", flow: "" };

function TopNav({ view, setView, stats }) {
  return (
    <header style={{
      background: C.surface, borderBottom: `1px solid ${C.border}`,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 18px", height: 48, flexShrink: 0,
    }}>
      {/* Logo + tabs */}
      <div style={{ display: "flex", alignItems: "center", height: "100%" }}>
        <div style={{ marginRight: 32 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: C.text, letterSpacing: "0.05em", textTransform: "uppercase" }}>Precognition</span>
          <span style={{ fontSize: 13, color: C.textMuted, fontWeight: 400 }}> · VC Intelligence</span>
        </div>

        {/* Nav tabs */}
        <nav style={{ display: "flex", height: "100%" }}>
          {VIEWS.map(v => (
            <button key={v} onClick={() => setView(v)} style={{
              padding: "0 16px", fontSize: 12, fontWeight: view === v ? 500 : 400,
              border: "none", borderBottom: view === v ? `2px solid ${C.text}` : "2px solid transparent",
              cursor: "pointer", background: "transparent", height: "100%",
              color: view === v ? C.text : C.textSub, letterSpacing: "0.02em",
            }}>
              {VIEW_LABELS[v]}
            </button>
          ))}
        </nav>
      </div>

      {/* Stats pills */}
      <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
        {[
          { label: "Tracked", val: stats.total },
          { label: "Strong Signal", val: stats.strong, color: C.green },
          { label: "To Contact", val: stats.toContact, color: C.amber },
        ].map(({ label, val, color }) => (
          <div key={label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: color || C.text, fontFamily: "ui-monospace, monospace" }}>{val}</div>
            <div style={{ fontSize: 10, color: C.textMuted, fontWeight: 500 }}>{label}</div>
          </div>
        ))}
      </div>
    </header>
  );
}

// ── THEMES VIEW ───────────────────────────────────────────────

function ThemeCard({ theme, onClick }) {
  const [hovered, setHovered] = useState(false);
  const vel = theme.weeklyVelocity || 0;
  const velPct = (vel * 100).toFixed(0);
  const velColor = vel > 0 ? C.green : vel < 0 ? C.red : C.textMuted;

  return (
    <Card
      style={{
        padding: 20,
        cursor: "pointer",
        transition: "box-shadow 0.15s, border-color 0.15s, background-color 0.15s",
        boxShadow: hovered ? C.shadowMd : C.shadow,
        borderColor: hovered ? "#bbb" : C.border,
        background: hovered ? "#fafaf8" : C.surface,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onClick(theme)}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div style={{ flex: 1, minWidth: 0, paddingRight: 12 }}>
          <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700, color: C.text }}>{theme.name}</h3>
          {theme.sector && (
            <div style={{ marginBottom: 6 }}>
              <Badge color="#666" bg="#f4f4f1" border="#e0e0dc">{theme.sector}</Badge>
            </div>
          )}
          <div style={{ fontSize: 12, color: C.textMuted }}>First detected {new Date(theme.firstDetected).toLocaleDateString()}</div>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div style={{ fontSize: 28, fontWeight: 800, color: scoreColor(theme.emergenceScore), fontFamily: "ui-monospace, monospace", lineHeight: 1 }}>{theme.emergenceScore}</div>
          <div style={{ fontSize: 10, color: C.textMuted, fontWeight: 500, marginTop: 2 }}>Emergence</div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 14, padding: "10px 0", borderTop: `1px solid ${C.borderLight}`, borderBottom: `1px solid ${C.borderLight}` }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: C.text, fontFamily: "ui-monospace, monospace" }}>{theme.builderCount}</div>
          <div style={{ fontSize: 10, color: C.textMuted }}>Builders</div>
        </div>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: velColor, fontFamily: "ui-monospace, monospace" }}>{vel > 0 ? "+" : ""}{velPct}%</div>
          <div style={{ fontSize: 10, color: C.textMuted }}>WoW growth</div>
        </div>
      </div>

      {theme.painSummary && (
        <div style={{ marginBottom: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: C.textSub }}>Pain: </span>
          <span style={{ fontSize: 12, color: C.textSub }}>{theme.painSummary}</span>
        </div>
      )}
      {theme.founderOrigin && (
        <div style={{ marginBottom: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: C.textSub }}>Origin: </span>
          <span style={{ fontSize: 12, color: C.textSub }}>{theme.founderOrigin}</span>
        </div>
      )}

      {theme.founders?.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {theme.founders.slice(0, 5).map(f => (
            <div key={f.id} title={f.name} style={{
              width: 26, height: 26, borderRadius: "50%", fontSize: 10, fontWeight: 700,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: C.accentLight, color: C.accent, border: `1px solid ${C.accentBorder}`,
            }}>
              {(f.name || "?")[0].toUpperCase()}
            </div>
          ))}
          {theme.founders.length > 5 && (
            <span style={{ fontSize: 11, color: C.textMuted, marginLeft: 4 }}>+{theme.founders.length - 5} more</span>
          )}
        </div>
      )}
      <div style={{ fontSize: 11, color: C.textMuted, textAlign: "right", marginTop: 10 }}>
        View founders →
      </div>
    </Card>
  );
}

function ThemesView() {
  const [themes, setThemes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedThemeId, setSelectedThemeId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [selectedLoading, setSelectedLoading] = useState(false);

  const cleanHandle = (handle = "") => handle.replace(/^@/, "");
  const truncate = (text = "", max = 50) => text.length > max ? `${text.slice(0, max - 1)}…` : text;
  const selectedThemeName = selected?.name || themes.find(t => t.id === selectedThemeId)?.name || "";
  const encodedThemeName = encodeURIComponent(selectedThemeName);

  useEffect(() => {
    fetch(`${API}/api/themes`).then(r => r.json()).then(data => {
      setThemes(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedThemeId) {
      setSelected(null);
      setSelectedLoading(false);
      return;
    }
    setSelectedLoading(true);
    fetch(`${API}/api/themes/${selectedThemeId}`)
      .then(r => r.json())
      .then(data => setSelected(data))
      .finally(() => setSelectedLoading(false));
  }, [selectedThemeId]);

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: C.textMuted }}>Loading themes…</div>;

  if (themes.length === 0) return (
    <EmptyState title="No themes detected yet"
      sub="Run the pipeline with 20+ founders to detect emerging clusters" />
  );

  if (selectedThemeId) return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      <div style={{ padding: "20px 24px", borderBottom: `1px solid ${C.border}` }}>
        <button
          onClick={() => setSelectedThemeId(null)}
          style={{ padding: "6px 12px", borderRadius: 8, border: `1px solid ${C.border}`, background: C.surface, color: C.textSub, cursor: "pointer", fontSize: 13, marginBottom: 12 }}
        >
          ← Patterns
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 30, fontWeight: 800, color: C.text }}>{selected?.name || selectedThemeName}</h2>
          {selected?.sector && <Badge color="#666" bg="#f4f4f1" border="#e0e0dc">{selected.sector}</Badge>}
          {selected && <ScorePill score={selected.emergenceScore} />}
          {selected && <Badge color={C.green} bg={C.greenLight} border="#a7f3d0">{selected.builderCount} builders</Badge>}
          {selected?.weeklyVelocity > 0 && (
            <span style={{ fontSize: 13, fontWeight: 600, color: C.green }}>
              ↑ {(selected.weeklyVelocity * 100).toFixed(0)}% this week
            </span>
          )}
        </div>
      </div>

      <div style={{ padding: 24 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16, marginBottom: 16 }}>
          <Card style={{ padding: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 10 }}>What this pattern represents</div>
            {selectedLoading && (
              <div style={{ fontSize: 13, color: C.textMuted, fontStyle: "italic" }}>Generating analysis...</div>
            )}
            {!selectedLoading && selected?.description && (
              <p style={{ margin: 0, fontSize: 13, color: C.textSub, lineHeight: 1.55 }}>{selected.description}</p>
            )}
            {!selectedLoading && !selected?.description && (
              <div style={{ fontSize: 13, color: C.textMuted }}>Analysis pending next pipeline run</div>
            )}
          </Card>

          <Card style={{ padding: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 10 }}>Explore this theme</div>
            {[
              { label: "Search TechCrunch", href: `https://techcrunch.com/search/${encodedThemeName}` },
              { label: "Search Google News", href: `https://news.google.com/search?q=${encodedThemeName}` },
              { label: "Search Crunchbase", href: `https://www.crunchbase.com/textsearch?q=${encodedThemeName}` },
            ].map(link => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noreferrer"
                style={{ display: "block", fontSize: 12, color: "#2050a0", marginBottom: 8, textDecoration: "none" }}
                onMouseEnter={e => { e.currentTarget.style.textDecoration = "underline"; }}
                onMouseLeave={e => { e.currentTarget.style.textDecoration = "none"; }}
              >
                {link.label} →
              </a>
            ))}
          </Card>
        </div>

        <div style={{ marginBottom: 10, fontSize: 16, fontWeight: 700, color: C.text }}>
          Founders in this cluster ({selected?.founders?.length || 0})
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
          {selected?.founders?.map(f => {
            const hnSignals = (f.signals || []).filter(s => s.type === "hn").slice(0, 2);
            return (
              <Card key={f.id} style={{ padding: 14 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, gap: 8 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.text, minWidth: 0 }}>
                    {f.name}{f.handle ? ` (${f.handle})` : ""}
                  </div>
                  <ScorePill score={f.score} size="sm" />
                </div>
                <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 8 }}>{f.company || f.domain || "Independent builder"}</div>
                <div
                  style={{
                    fontSize: 12,
                    color: C.textSub,
                    lineHeight: 1.5,
                    marginBottom: 10,
                    display: "-webkit-box",
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {f.bio}
                </div>
                <div style={{ marginBottom: hnSignals.length ? 8 : 0 }}>
                  {(f.sources || []).map(source => {
                    if (source === "github" && f.handle) {
                      return (
                        <a
                          key={`${f.id}-github`}
                          href={`https://github.com/${cleanHandle(f.handle)}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: 11, color: "#2050a0", textDecoration: "none", marginRight: 8 }}
                        >
                          GitHub →
                        </a>
                      );
                    }
                    if (source === "hn" && f.handle) {
                      return (
                        <a
                          key={`${f.id}-hn`}
                          href={`https://news.ycombinator.com/user?id=${cleanHandle(f.handle)}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: 11, color: "#2050a0", textDecoration: "none", marginRight: 8 }}
                        >
                          HN →
                        </a>
                      );
                    }
                    return null;
                  })}
                </div>
                {hnSignals.length > 0 && (
                  <div>
                    {hnSignals.map((signal, idx) => (
                      <a
                        key={`${f.id}-hn-signal-${idx}`}
                        href={signal.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ fontSize: 11, color: "#2050a0", textDecoration: "none", marginRight: 8 }}
                        title={signal.label}
                      >
                        {truncate(signal.label || "HN signal", 50)} →
                      </a>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );

  return (
    <div style={{ padding: 24, overflowY: "auto", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: C.text }}>Patterns</h2>
        <p style={{ margin: 0, fontSize: 13, color: C.textMuted }}>Clusters of unrelated founders independently building in the same direction</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 16 }}>
        {themes.map(t => <ThemeCard key={t.id} theme={t} onClick={(theme) => setSelectedThemeId(theme.id)} />)}
      </div>
    </div>
  );
}

// ── EMERGENCE VIEW ────────────────────────────────────────────

function EmergenceCard({ event }) {
  const isTheme = event.entityType === "theme";
  const typeLabels = {
    new_theme: { label: "New Theme", color: C.accent, bg: C.accentLight },
    theme_spike: { label: "Theme Spike", color: C.green, bg: C.greenLight },
    commit_spike: { label: "Commit Spike", color: C.blue, bg: C.blueLight },
    star_spike: { label: "Star Spike", color: C.amber, bg: C.amberLight },
    hn_spike: { label: "HN Spike", color: "#b45309", bg: "#fffbeb" },
  };
  const cfg = typeLabels[event.eventType] || { label: event.eventType, color: C.textSub, bg: C.bg };
  const since = Math.round((Date.now() - new Date(event.detectedAt)) / 3600000);

  return (
    <Card style={{ padding: 16, display: "flex", gap: 14, alignItems: "flex-start" }}>
      <div style={{
        width: 36, height: 36, borderRadius: 10, background: cfg.bg,
        border: `1px solid ${cfg.color}20`, flexShrink: 0,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
            {isTheme ? event.themeName : (event.company || event.founderName)}
          </span>
          <Badge color={cfg.color} bg={cfg.bg} border={`${cfg.color}30`}>{cfg.label}</Badge>
          {!isTheme && event.score && <ScorePill score={event.score} size="sm" />}
        </div>
        <p style={{ margin: "0 0 6px", fontSize: 13, color: C.textSub, lineHeight: 1.4 }}>{event.signal}</p>
        {event.deltaBefore != null && event.deltaAfter != null && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <span style={{ color: C.textMuted, fontFamily: "ui-monospace, monospace" }}>{Number(event.deltaBefore).toFixed(0)}</span>
            <span style={{ color: C.textMuted }}>→</span>
            <span style={{ color: scoreColor(75), fontWeight: 700, fontFamily: "ui-monospace, monospace" }}>{Number(event.deltaAfter).toFixed(0)}</span>
          </div>
        )}
      </div>
      <div style={{ fontSize: 11, color: C.textMuted, flexShrink: 0, paddingTop: 2 }}>
        {since < 1 ? "just now" : `${since}h ago`}
      </div>
    </Card>
  );
}

function EmergenceView() {
  const [data, setData] = useState({ newThemes: [], inflectionFounders: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/emergence`).then(r => r.json()).then(d => {
      setData(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: C.textMuted }}>Loading…</div>;

  const all = [...(data.newThemes || []), ...(data.inflectionFounders || [])]
    .sort((a, b) => new Date(b.detectedAt) - new Date(a.detectedAt));

  if (all.length === 0) return (
    <EmptyState title="No emergence events yet"
      sub="Events appear when founders cross velocity thresholds or new theme clusters are detected" />
  );

  return (
    <div style={{ padding: 24, overflowY: "auto", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: C.text }}>Breaks</h2>
        <p style={{ margin: 0, fontSize: 13, color: C.textMuted }}>What just crossed a threshold that wasn't on your radar yesterday</p>
      </div>
      <div style={{ display: "grid", gap: 10, maxWidth: 760 }}>
        {data.newThemes?.length > 0 && (
          <>
            <SectionTitle>New Theme Clusters ({data.newThemes.length})</SectionTitle>
            {data.newThemes.map(e => <EmergenceCard key={e.id} event={{ ...e, entityType: "theme" }} />)}
          </>
        )}
        {data.inflectionFounders?.length > 0 && (
          <>
            <SectionTitle style={{ marginTop: 20 }}>Inflection Founders ({data.inflectionFounders.length})</SectionTitle>
            {data.inflectionFounders.map(e => <EmergenceCard key={e.id} event={e} />)}
          </>
        )}
      </div>
    </div>
  );
}

// ── PULSE VIEW ────────────────────────────────────────────────

function PulseView() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/pulse`).then(r => r.json()).then(d => {
      setSignals(d);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: C.textMuted }}>Loading…</div>;

  if (signals.length === 0) return (
    <EmptyState title="No signals in the last 48 hours"
      sub="Signals appear as the pipeline scrapes GitHub, HN, and Product Hunt" />
  );

  // Group by date
  const grouped = {};
  signals.forEach(s => {
    const d = new Date(s.detectedAt).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(s);
  });

  return (
    <div style={{ padding: 24, overflowY: "auto", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: C.text }}>Raw</h2>
        <p style={{ margin: 0, fontSize: 13, color: C.textMuted }}>Unfiltered signal feed — last 48 hours, before scoring or clustering</p>
      </div>
      <div style={{ maxWidth: 720 }}>
        {Object.entries(grouped).map(([date, sigs]) => (
          <div key={date} style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>{date}</div>
            <Card>
              {sigs.map((s, i) => {
                const src = SOURCE[s.source] || { color: C.textSub, bg: C.bg, label: "?" };
                const time = new Date(s.detectedAt).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
                return (
                  <div key={s.id} style={{
                    display: "flex", gap: 12, padding: "12px 16px",
                    borderBottom: i < sigs.length - 1 ? `1px solid ${C.borderLight}` : "none",
                    alignItems: "flex-start",
                  }}>
                    <span style={{
                      flexShrink: 0, fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 5,
                      color: src.color, background: src.bg, border: `1px solid ${src.color}20`,
                    }}>{src.label}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: C.textSub, marginBottom: 2 }}>
                        <span style={{ fontWeight: 600, color: C.text }}>{s.company || s.founderName}</span>
                        {" · "}
                        <span>{s.founderHandle}</span>
                      </div>
                      <div style={{ fontSize: 13, color: C.text, lineHeight: 1.4 }}>{s.label}</div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                      {s.strong && <Badge color={C.amber} bg={C.amberLight} border="#fde68a">Key</Badge>}
                      <span style={{ fontSize: 11, color: C.textMuted, fontFamily: "ui-monospace, monospace" }}>{time}</span>
                    </div>
                  </div>
                );
              })}
            </Card>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── SCOUTING VIEW ─────────────────────────────────────────────

// ── Plain-English signal summary ──────────────────────────────
function whySurfaced(founder) {
  const parts = [];
  if (founder.incubator) parts.push(founder.incubator);
  const commits = founder.github_commits_90d || 0;
  const stars = founder.github_stars || 0;
  const hn = founder.hn_karma || 0;
  if (commits > 500) parts.push(`shipping fast — ${commits.toLocaleString()} commits/90d`);
  else if (commits > 100) parts.push(`active builder — ${commits.toLocaleString()} commits/90d`);
  if (stars > 1000) parts.push(`${(stars/1000).toFixed(1)}k GitHub stars`);
  else if (stars > 200) parts.push(`${stars} GitHub stars`);
  if (hn > 2000) parts.push(`strong HN presence`);
  if (founder.sources?.includes("producthunt")) parts.push("PH launch");
  if (parts.length === 0) parts.push("early signal");
  return parts.join(" · ");
}

const INCUBATOR_COLORS = {
  "YC":           { bg: "#FF6600", color: "#fff" },
  "a16z Speedrun":{ bg: "#000",    color: "#fff" },
  "HF0":          { bg: "#1a1a2e", color: "#e0e0ff" },
  "Techstars":    { bg: "#0b6e4f", color: "#fff" },
  "500 Global":   { bg: "#e63946", color: "#fff" },
  "Plug and Play":{ bg: "#005f99", color: "#fff" },
  "Pioneer":      { bg: "#6d28d9", color: "#fff" },
};

function IncubatorBadge({ label }) {
  if (!label) return null;
  const key = Object.keys(INCUBATOR_COLORS).find(k => label.startsWith(k)) || null;
  const style = key ? INCUBATOR_COLORS[key] : { bg: C.accentLight, color: C.accent };
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
      background: style.bg, color: style.color,
      flexShrink: 0, letterSpacing: "0.02em",
    }}>{label}</span>
  );
}

// ── Startup Card ────────────────────────────────────────────────────────────
function StartupCard({ founder: s, selected, onClick }) {
  const signals = whySurfaced(s);
  return (
    <div onClick={() => onClick(s)}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = C.bg; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = selected ? C.accentLight : "transparent"; }}
      style={{
        padding: "14px 18px", borderBottom: `1px solid ${C.borderLight}`,
        cursor: "pointer", background: selected ? C.accentLight : "transparent",
        transition: "background 0.1s",
      }}>

      {/* Company name + incubator badge + score */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: C.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {s.company || s.name}
        </span>
        <IncubatorBadge label={s.incubator} />
        <ScorePill score={s.score} size="sm" />
      </div>

      {/* Product description */}
      {s.bio && (
        <div style={{ fontSize: 12, color: C.textSub, lineHeight: 1.5, marginBottom: 6 }}>
          {s.bio}
        </div>
      )}

      {/* Founder / team line */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: signals ? 5 : 0 }}>
        {s.location && (
          <span style={{ fontSize: 11, color: C.textMuted }}>📍 {s.location}</span>
        )}
        {s.founded && (
          <span style={{ fontSize: 11, color: C.textMuted }}>Founded {s.founded}</span>
        )}
        {s.stage && s.stage !== "Unknown" && (
          <span style={{ fontSize: 10, fontWeight: 600, color: C.textSub, background: C.surface, border: `1px solid ${C.borderLight}`, borderRadius: 4, padding: "1px 6px" }}>
            {s.stage}
          </span>
        )}
      </div>

      {/* Why now */}
      {signals && (
        <div style={{ fontSize: 11, color: C.textMuted, fontStyle: "italic" }}>{signals}</div>
      )}
    </div>
  );
}

// ── Individual / Founder-to-Follow Card ─────────────────────────────────────
function IndividualCard({ founder: f, selected, onClick }) {
  const pedigree = f.scoreBreakdown?.founder_quality || 0;
  const velocity = f.scoreBreakdown?.execution_velocity || 0;

  const backgroundHints = [];
  const bio = (f.bio || "").toLowerCase();
  if (bio.includes("yc") || bio.includes("y combinator")) backgroundHints.push("YC");
  if (bio.includes("openai") || bio.includes("anthropic") || bio.includes("deepmind")) backgroundHints.push("AI lab");
  if (bio.includes("google") || bio.includes("meta") || bio.includes("stripe") || bio.includes("apple") || bio.includes("amazon")) backgroundHints.push("Big tech");
  if (bio.includes("phd") || bio.includes("ph.d")) backgroundHints.push("PhD");
  if (bio.includes("founder") || bio.includes("co-founder")) backgroundHints.push("Founder");

  return (
    <div onClick={() => onClick(f)}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = C.bg; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = selected ? C.accentLight : "transparent"; }}
      style={{
        padding: "12px 18px", borderBottom: `1px solid ${C.borderLight}`,
        cursor: "pointer", background: selected ? C.accentLight : "transparent",
        transition: "background 0.1s",
      }}>

      {/* Handle + score */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.text, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {f.name || f.handle}
          {f.handle && f.name && f.handle !== f.name && (
            <span style={{ fontWeight: 400, color: C.textMuted, marginLeft: 5 }}>@{f.handle}</span>
          )}
        </span>
        <ScorePill score={f.score} size="sm" />
      </div>

      {/* Bio */}
      {f.bio && (
        <div style={{ fontSize: 12, color: C.textSub, lineHeight: 1.4, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {f.bio}
        </div>
      )}

      {/* Background tags + velocity signal */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        {backgroundHints.map(h => (
          <span key={h} style={{ fontSize: 10, fontWeight: 600, color: C.accent, background: C.accentLight, border: `1px solid ${C.accentBorder}`, borderRadius: 4, padding: "1px 5px" }}>{h}</span>
        ))}
        {velocity >= 16 && (
          <span style={{ fontSize: 10, color: C.textMuted }}>
            {velocity >= 28 ? "Shipping fast" : velocity >= 22 ? "Active builder" : "Building"}
          </span>
        )}
      </div>
    </div>
  );
}

// Kept for detail panel compatibility (same data, just not used in list anymore)
function FounderRow({ founder, selected, onClick }) {
  return founder.entityType === "startup"
    ? <StartupCard founder={founder} selected={selected} onClick={onClick} />
    : <IndividualCard founder={founder} selected={selected} onClick={onClick} />;
}

function FounderDetail({ founder, onStatusChange, onNotesChange }) {
  const [notes, setNotes] = useState(founder?.notes || "");
  const [saving, setSaving] = useState(false);
  const notesRef = useRef(null);

  useEffect(() => { setNotes(founder?.notes || ""); }, [founder?.id]);

  if (!founder) return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 8 }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: C.accentLight, border: `1px solid ${C.accentBorder}` }} />
      <div style={{ fontSize: 14, color: C.textMuted }}>Select a founder to inspect</div>
    </div>
  );

  const statusOrder = Object.keys(STATUS);
  const nextStatus = statusOrder[(statusOrder.indexOf(founder.status) + 1) % statusOrder.length];
  const stCfg = STATUS[founder.status] || STATUS.to_contact;

  const saveNotes = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/founders/${founder.id}/notes`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes }),
      });
      onNotesChange(founder.id, notes);
    } finally { setSaving(false); }
  };

  return (
    <div style={{ height: "100%", overflowY: "auto", padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", gap: 16, marginBottom: 20, paddingBottom: 20, borderBottom: `1px solid ${C.border}` }}>
        <div style={{
          width: 48, height: 48, borderRadius: 12, background: `${scoreColor(founder.score)}15`,
          border: `2px solid ${scoreColor(founder.score)}30`, display: "flex",
          alignItems: "center", justifyContent: "center", fontSize: 18,
          fontWeight: 800, color: scoreColor(founder.score), flexShrink: 0,
        }}>
          {(founder.name || "?")[0].toUpperCase()}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3, flexWrap: "wrap" }}>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: C.text }}>{founder.company || founder.name}</h2>
            {founder.incubator && <IncubatorBadge label={founder.incubator} />}
            {founder.stage && <Badge>{founder.stage}</Badge>}
            <button onClick={() => onStatusChange(founder.id, nextStatus)} style={{
              padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600,
              cursor: "pointer", border: `1px solid ${stCfg.border}`,
              background: stCfg.bg, color: stCfg.color,
            }}>{stCfg.label}</button>
          </div>
          <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 6 }}>
            {[founder.name, founder.domain, founder.location].filter(Boolean).join(" · ")}
          </div>
          {founder.bio && (
            <p style={{ margin: "0 0 8px", fontSize: 14, color: C.text, fontWeight: 500, lineHeight: 1.5 }}>{founder.bio}</p>
          )}
          {/* Why surfaced */}
          <div style={{ fontSize: 12, color: C.textMuted, padding: "6px 10px", background: C.bg, borderRadius: 6, border: `1px solid ${C.borderLight}` }}>
            <span style={{ fontWeight: 600, color: C.textSub }}>Why surfaced: </span>{whySurfaced(founder)}
          </div>
        </div>
        <ScorePill score={founder.score} />
      </div>

      {/* Stats grid — plain English */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginBottom: 20 }}>
        {[
          {
            label: "Building speed",
            val: (founder.github_commits_90d || 0) > 0
              ? `${(founder.github_commits_90d || 0).toLocaleString()} commits / 90d`
              : "No GitHub activity",
            sub: (founder.github_commits_90d || 0) > 500 ? "Shipping very fast" : (founder.github_commits_90d || 0) > 100 ? "Actively building" : "Early stage",
            color: SOURCE.github.color,
          },
          {
            label: "Public traction",
            val: (founder.github_stars || 0) > 0
              ? `${(founder.github_stars || 0).toLocaleString()} GitHub stars`
              : "No public repos yet",
            sub: (founder.github_stars || 0) > 1000 ? "Strong visibility" : (founder.github_stars || 0) > 100 ? "Growing audience" : "Pre-visibility",
            color: SOURCE.github.color,
          },
          {
            label: "Community presence",
            val: (founder.hn_karma || 0) > 0
              ? `${(founder.hn_karma || 0).toLocaleString()} HN karma`
              : "Not on Hacker News",
            sub: (founder.hn_karma || 0) > 2000 ? "Thought leader" : (founder.hn_karma || 0) > 500 ? "Active voice" : "Low HN presence",
            color: SOURCE.hn.color,
          },
          {
            label: "Audience",
            val: (founder.followers || 0) >= 1000
              ? `${((founder.followers || 0) / 1000).toFixed(1)}k followers`
              : `${founder.followers || 0} followers`,
            sub: (founder.ph_upvotes || 0) > 0 ? `${founder.ph_upvotes} PH upvotes` : "No PH launch yet",
            color: C.accent,
          },
        ].map(({ label, val, sub, color }) => (
          <Card key={label} style={{ padding: "12px 14px" }}>
            <div style={{ fontSize: 10, color: C.textMuted, marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color, marginBottom: 2 }}>{val}</div>
            <div style={{ fontSize: 11, color: C.textMuted }}>{sub}</div>
          </Card>
        ))}
      </div>

      {/* Score breakdown — plain English */}
      <Card style={{ padding: 16, marginBottom: 16 }}>
        <SectionTitle>What drives this score</SectionTitle>
        {[
          { dim: "founder_quality", label: "Pedigree", max: 35, desc: "Background — YC alumni, top company, serial founder, PhD" },
          { dim: "execution_velocity", label: "Velocity", max: 30, desc: "Building speed — GitHub commits in the last 90 days" },
          { dim: "market_conviction", label: "Momentum", max: 25, desc: "Public traction — GitHub stars + Hacker News karma" },
          { dim: "deal_availability", label: "Availability", max: 10, desc: "Likely open to a conversation — no raised/Series A signals in bio" },
        ].map(({ dim, label, max, desc }) => (
          <div key={dim} style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: C.textSub }}>{label}</span>
              <span style={{ fontSize: 11, color: C.textMuted, fontFamily: "ui-monospace, monospace" }}>{founder.scoreBreakdown?.[dim] || 0}/{max}</span>
            </div>
            <div style={{ fontSize: 11, color: C.textMuted, marginBottom: 5 }}>{desc}</div>
            <ScoreBar label="" value={founder.scoreBreakdown?.[dim] || 0} max={max} />
          </div>
        ))}
      </Card>

      {/* Notes */}
      <Card style={{ padding: 16, marginBottom: 16 }}>
        <SectionTitle>Private Notes</SectionTitle>
        <textarea
          ref={notesRef}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Add notes about this founder…"
          rows={4}
          style={{
            width: "100%", boxSizing: "border-box", resize: "vertical",
            border: `1px solid ${C.border}`, borderRadius: 8, padding: "10px 12px",
            fontSize: 13, color: C.text, background: C.bg, fontFamily: "inherit",
            outline: "none", lineHeight: 1.5,
          }}
        />
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
          <button onClick={saveNotes} disabled={saving} style={{
            padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600,
            cursor: saving ? "default" : "pointer", border: "none",
            background: C.accent, color: "#fff", opacity: saving ? 0.7 : 1,
          }}>{saving ? "Saving…" : "Save Notes"}</button>
        </div>
      </Card>

      {/* Signals */}
      {founder.signals?.length > 0 && (
        <Card style={{ padding: 16, marginBottom: 16 }}>
          <SectionTitle>Recent Signals ({founder.signals.length})</SectionTitle>
          {founder.signals.map((s, i) => {
            const src = SOURCE[s.type] || SOURCE.github;
            return (
              <div key={i} style={{
                display: "flex", gap: 10, padding: "10px 0",
                borderBottom: i < founder.signals.length - 1 ? `1px solid ${C.borderLight}` : "none",
              }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: src.color, flexShrink: 0, marginTop: 5 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: s.strong ? C.text : C.textSub, lineHeight: 1.4 }}>{s.label}</div>
                  <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2, fontFamily: "ui-monospace, monospace" }}>{s.date}</div>
                </div>
                {s.strong && <Badge color={C.amber} bg={C.amberLight} border="#fde68a">Key</Badge>}
              </div>
            );
          })}
        </Card>
      )}

      {/* Enrichment */}
      {(founder.twitter_handle || founder.linkedin_summary || founder.is_serial_founder) && (
        <Card style={{ padding: 16, marginBottom: 16 }}>
          <SectionTitle>Enrichment</SectionTitle>
          {founder.twitter_handle && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.text }}>{founder.twitter_handle}</div>
                <div style={{ fontSize: 11, color: C.textMuted }}>Twitter / X</div>
              </div>
              <div style={{ textAlign: "right" }}>
                {founder.twitter_followers > 0 && (
                  <div style={{ fontSize: 15, fontWeight: 700, color: C.blue, fontFamily: "ui-monospace, monospace" }}>
                    {founder.twitter_followers >= 1000 ? `${(founder.twitter_followers / 1000).toFixed(1)}k` : founder.twitter_followers}
                    <span style={{ fontSize: 10, fontWeight: 400, color: C.textMuted }}> followers</span>
                  </div>
                )}
                {founder.twitter_engagement_rate > 0 && (
                  <div style={{ fontSize: 11, color: C.textMuted }}>{founder.twitter_engagement_rate} avg engagement</div>
                )}
              </div>
            </div>
          )}
          {founder.linkedin_summary && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: C.textSub, marginBottom: 3 }}>LinkedIn Summary</div>
              <p style={{ margin: 0, fontSize: 12, color: C.textSub, lineHeight: 1.5 }}>{founder.linkedin_summary}</p>
            </div>
          )}
          {founder.is_serial_founder && (
            <Badge color={C.accent} bg={C.accentLight} border={C.accentBorder}>Serial Founder</Badge>
          )}
          {founder.enriched_at && (
            <div style={{ fontSize: 10, color: C.textMuted, marginTop: 8 }}>
              Enriched {new Date(founder.enriched_at).toLocaleDateString()}
            </div>
          )}
        </Card>
      )}

      {/* Tags */}
      {founder.tags?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
          {founder.tags.map(t => (
            <span key={t} style={{ fontSize: 11, padding: "3px 10px", borderRadius: 99, background: C.bg, border: `1px solid ${C.border}`, color: C.textSub }}>#{t}</span>
          ))}
        </div>
      )}

      {/* CTA */}
      <div style={{ display: "flex", gap: 10 }}>
        <button style={{
          flex: 1, padding: 12, borderRadius: 10, border: "none",
          background: C.accent, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer",
        }}>Reach Out</button>
        <button style={{
          padding: "12px 16px", borderRadius: 10, border: `1px solid ${C.border}`,
          background: C.surface, color: C.textSub, fontSize: 13, cursor: "pointer",
        }}>Save</button>
      </div>
    </div>
  );
}

const PAGE_SIZE = 50;

// ── Archetype classification ──────────────────────────────────

const ARCHETYPES = [
  {
    key: "incubators",
    label: "Incubators",
    desc: "YC · Techstars · 500 Global · a16z Speedrun · HF0 · Plug and Play · Pioneer",
    color: "#FF6600",
    bg: "#fff3eb",
    border: "#ffd0b0",
    match: f => !!f.incubator,
  },
  {
    key: "act_now",
    label: "Rising Stars",
    desc: "Score ≥ 65 · high signal · not yet contacted",
    color: C.green,
    bg: C.greenLight,
    border: "#a7f3d0",
    match: f => f.score >= 65 && !["pass", "contacted"].includes(f.status) && !f.incubator,
  },
  {
    key: "serial",
    label: "Serial Founders",
    desc: "Prior company detected",
    color: C.accent,
    bg: C.accentLight,
    border: C.accentBorder,
    match: f => f.is_serial_founder && !f.incubator,
  },
  {
    key: "stealth",
    label: "Stealth Builders",
    desc: "High commits · low public profile",
    color: C.blue,
    bg: C.blueLight,
    border: "#bfdbfe",
    match: f => f.github_commits_90d >= 100 && f.github_stars < 400 && (f.followers || 0) < 1000,
  },
  {
    key: "domain_writer",
    label: "Domain Writers",
    desc: "HN-first · high conviction",
    color: C.amber,
    bg: C.amberLight,
    border: "#fde68a",
    match: f => f.hn_karma >= 1000 && f.github_stars < 300,
  },
  {
    key: "tracking",
    label: "Tracking",
    desc: "Everything else worth watching",
    color: C.textSub,
    bg: C.bg,
    border: C.border,
    match: () => true, // catch-all — applied only if no other bucket matched
  },
];

function classifyFounder(f) {
  const matched = ARCHETYPES.slice(0, -1).filter(a => a.match(f));
  return matched.length > 0 ? matched.map(a => a.key) : ["tracking"];
}

function ArchetypeSection({ archetype, founders, selected, onSelect, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  const { label, desc, color, bg, border } = archetype;
  if (founders.length === 0) return null;
  return (
    <div style={{ borderBottom: `1px solid ${C.borderLight}` }}>
      {/* Section header */}
      <button onClick={() => setOpen(o => !o)} style={{
        width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 16px", background: bg, border: "none", cursor: "pointer",
        borderBottom: open ? `1px solid ${border}` : "none",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color }}>{label}</span>
          <span style={{
            fontSize: 10, fontWeight: 700, color, background: `${color}18`,
            border: `1px solid ${border}`, borderRadius: 99, padding: "1px 7px",
            fontFamily: "ui-monospace, monospace",
          }}>{founders.length}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 10, color: C.textMuted }}>{desc}</span>
          <span style={{ fontSize: 10, color: C.textMuted, fontFamily: "ui-monospace, monospace" }}>{open ? "−" : "+"}</span>
        </div>
      </button>
      {/* Founders */}
      {open && founders.map(f => (
        <FounderRow key={f.id} founder={f} selected={selected?.id === f.id} onClick={onSelect} />
      ))}
    </div>
  );
}

function FieldLegend({ total, filtered, scoutLabel }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderBottom: `1px solid ${C.borderLight}` }}>
      {/* Count row + toggle */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          padding: "6px 20px", fontSize: 11, color: C.textMuted,
          display: "flex", justifyContent: "space-between", alignItems: "center",
          cursor: "pointer", userSelect: "none",
        }}>
        <span>
          {filtered !== null
            ? <><strong style={{ color: C.text }}>{filtered}</strong> matching {scoutLabel} · {total} total</>
            : <>{total} companies tracked</>
          }
        </span>
        <span style={{ fontSize: 10, color: C.textMuted, fontWeight: 600 }}>
          {open ? "Hide legend ▲" : "Data sources ▼"}
        </span>
      </div>

      {open && (
        <div style={{ padding: "10px 20px 14px", background: C.bg, fontSize: 11, color: C.textSub, lineHeight: 1.7 }}>
          {/* Data sources */}
          <div style={{ fontWeight: 700, color: C.textMuted, marginBottom: 6, textTransform: "uppercase", fontSize: 10, letterSpacing: "0.05em" }}>Data Sources</div>
          {[
            { label: "GitHub", dot: SOURCE.github.color, desc: "Commit activity, stars, repositories, bio" },
            { label: "Hacker News", dot: SOURCE.hn.color, desc: "Karma, top posts, Show HN launches" },
            { label: "Product Hunt", dot: SOURCE.producthunt.color, desc: "Launch upvotes, featured products" },
            { label: "YC API", dot: "#FF6600", desc: "W26, S25, W25 batch companies — official YC directory" },
            { label: "Accelerator seeds", dot: "#6d28d9", desc: "Curated lists: Techstars, 500 Global, PnP, HF0, a16z Speedrun, Pioneer" },
            { label: "HN watcher", dot: "#888", desc: "Auto-detects new Launch HN posts mentioning any accelerator" },
          ].map(({ label, dot, desc }) => (
            <div key={label} style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 4 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: dot, flexShrink: 0, marginTop: 4 }} />
              <span><span style={{ fontWeight: 600, color: C.textSub }}>{label}</span> — {desc}</span>
            </div>
          ))}

          {/* Incubator badges */}
          <div style={{ fontWeight: 700, color: C.textMuted, margin: "10px 0 6px", textTransform: "uppercase", fontSize: 10, letterSpacing: "0.05em" }}>Incubator Badges</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {Object.entries(INCUBATOR_COLORS).map(([name, style]) => (
              <span key={name} style={{
                fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                background: style.bg, color: style.color,
              }}>{name}</span>
            ))}
          </div>

          {/* Score */}
          <div style={{ fontWeight: 700, color: C.textMuted, margin: "10px 0 6px", textTransform: "uppercase", fontSize: 10, letterSpacing: "0.05em" }}>Score (0–100)</div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {[
              { label: "Pedigree", max: "35 pts", desc: "YC / FAANG / serial founder / PhD" },
              { label: "Velocity", max: "30 pts", desc: "GitHub commits in 90 days" },
              { label: "Momentum", max: "25 pts", desc: "GitHub stars + HN karma" },
              { label: "Availability", max: "10 pts", desc: "No funding announced in bio" },
            ].map(({ label, max, desc }) => (
              <div key={label} style={{ fontSize: 10, background: C.surface, borderRadius: 6, padding: "5px 8px", border: `1px solid ${C.borderLight}` }}>
                <span style={{ fontWeight: 700, color: C.textSub }}>{label}</span>
                <span style={{ color: C.textMuted }}> {max} — {desc}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 8, color: C.textMuted, fontStyle: "italic" }}>
            Pipeline runs hourly. YC companies seeded from public API. Other accelerators updated from curated list + HN launches.
          </div>
        </div>
      )}
    </div>
  );
}

// ── Scout Modes ─────────────────────────────────────────────────────────────
const sb = f => f.scoreBreakdown || {};

const SCOUT_MODES = [
  {
    key: "all",
    label: "All",
    shortDesc: "Default composite score",
    color: C.textMuted,
    bg: C.surface,
    sort: f => f.score || 0,
    filter: () => true,
  },
  {
    key: "conviction",
    label: "Conviction",
    shortDesc: "AI infra · dev tools · velocity + pedigree",
    color: "#fff",
    bg: "#111",
    sort: f => (sb(f).execution_velocity || 0) * 0.5 + (sb(f).founder_quality || 0) * 0.5,
    filter: f => {
      const bio = (f.bio || "").toLowerCase();
      const tags = (f.tags || []).join(" ").toLowerCase();
      const combo = bio + " " + tags;
      return ["ai", "llm", "model", "developer tools", "infra", "infrastructure", "ml", "agent"].some(k => combo.includes(k));
    },
  },
  {
    key: "first_round",
    label: "First Round",
    shortDesc: "High pedigree · stealth · not yet raised",
    color: "#fff",
    bg: "#b91c1c",
    sort: f => (sb(f).founder_quality || 0) * 0.7 + (sb(f).deal_availability || 0) * 3,
    filter: f => (sb(f).deal_availability || 0) >= 5,
  },
  {
    key: "hustle_fund",
    label: "Hustle Fund",
    shortDesc: "Velocity only · no pedigree needed · scrappy",
    color: "#fff",
    bg: "#ea580c",
    sort: f => sb(f).execution_velocity || 0,
    filter: () => true,
  },
  {
    key: "precursor",
    label: "Precursor",
    shortDesc: "Absolute earliest · pre-product · stealth",
    color: "#fff",
    bg: "#0284c7",
    sort: f => (sb(f).deal_availability || 0) * 6 + (sb(f).execution_velocity || 0) * 0.4,
    filter: f => !f.incubator && (sb(f).deal_availability || 0) >= 5,
  },
  {
    key: "spc",
    label: "SPC",
    shortDesc: "Exploring founder · high pedigree · no company yet",
    color: "#fff",
    bg: "#7c3aed",
    sort: f => sb(f).founder_quality || 0,
    filter: f => !f.incubator && (sb(f).founder_quality || 0) >= 10,
  },
];

function SectionHeader({ label, count, subtitle, collapsible, defaultOpen, onToggle }) {
  return (
    <div
      onClick={collapsible ? onToggle : undefined}
      style={{
        padding: "10px 18px 8px",
        background: C.surface,
        borderBottom: `1px solid ${C.border}`,
        borderTop: `1px solid ${C.border}`,
        cursor: collapsible ? "pointer" : "default",
        userSelect: "none",
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: C.text, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {label}
        </span>
        <span style={{ fontSize: 11, color: C.textMuted, background: C.bg, border: `1px solid ${C.borderLight}`, borderRadius: 10, padding: "0px 7px", fontWeight: 600 }}>
          {count}
        </span>
        {collapsible && (
          <span style={{ fontSize: 10, color: C.textMuted, marginLeft: "auto" }}>
            {defaultOpen ? "▲ Hide" : "▼ Show"}
          </span>
        )}
      </div>
      {subtitle && (
        <div style={{ fontSize: 10, color: C.textMuted, marginTop: 2, fontStyle: "italic" }}>{subtitle}</div>
      )}
    </div>
  );
}

function ScoutingView() {
  const [founders, setFounders] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [debSearch, setDebSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [scoutModeKey, setScoutModeKey] = useState("all");
  const [showIndividuals, setShowIndividuals] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const listRef = useRef(null);

  const scoutMode = SCOUT_MODES.find(m => m.key === scoutModeKey) || SCOUT_MODES[0];

  // Startups: entityType=startup OR incubator set (fallback while API redeploys)
  const visibleStartups = useMemo(() => {
    return [...founders]
      .filter(f => f.entityType === "startup" || (!f.entityType && !!f.incubator))
      .filter(scoutMode.filter)
      .sort((a, b) => scoutMode.sort(b) - scoutMode.sort(a));
  }, [founders, scoutMode]);

  // Individuals: no incubator, entityType !== startup
  const visibleIndividuals = useMemo(() => {
    return [...founders]
      .filter(f => f.entityType !== "startup" && !f.incubator)
      .filter(scoutMode.filter)
      .sort((a, b) => scoutMode.sort(b) - scoutMode.sort(a));
  }, [founders, scoutMode]);

  // Legacy: needed for FieldLegend filtered count
  const applyScout = useCallback((list) => {
    return [...list].filter(scoutMode.filter).sort((a, b) => scoutMode.sort(b) - scoutMode.sort(a));
  }, [scoutMode]);

  useEffect(() => {
    const t = setTimeout(() => setDebSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Fetch full detail (all signals) when a founder is expanded
  useEffect(() => {
    if (!selected?.id) return;
    let cancelled = false;
    setLoadingDetail(true);
    fetch(`${API}/api/founders/${selected.id}`)
      .then(r => r.json())
      .then(full => {
        if (!cancelled) {
          setSelected(full);
          setFounders(prev => prev.map(f => f.id === full.id ? { ...f, signals: full.signals } : f));
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoadingDetail(false); });
    return () => { cancelled = true; };
  }, [selected?.id]);

  // Always fetch everything upfront — client-side split into startups / individuals
  const buildUrl = useCallback(() => {
    const p = new URLSearchParams({ limit: 2000, offset: 0, sort: "score", order: "desc" });
    if (debSearch) p.set("search", debSearch);
    if (filterStatus !== "all") p.set("status", filterStatus);
    return `${API}/api/founders?${p}`;
  }, [debSearch, filterStatus]);

  const fetchFounders = useCallback(async (reset = false) => {
    if (reset) setLoading(true);
    const url = buildUrl(0);
    const cacheKey = `founders_cache:${url}`;
    const TTL = 5 * 60 * 1000; // 5 minutes
    try {
      // Try sessionStorage cache first
      try {
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
          const { data, ts } = JSON.parse(cached);
          if (Date.now() - ts < TTL) {
            setFounders(data.founders || []);
            setTotal(data.total || 0);
            setLoading(false);
            return;
          }
        }
      } catch (_) { /* ignore storage errors */ }

      const res = await fetch(url);
      const data = await res.json();
      setFounders(data.founders || []);
      setTotal(data.total || 0);

      // Store in cache
      try { sessionStorage.setItem(cacheKey, JSON.stringify({ data, ts: Date.now() })); }
      catch (_) { /* ignore quota errors */ }
    } finally { setLoading(false); }
  }, [buildUrl]);

  useEffect(() => { fetchFounders(true); }, [debSearch, filterStatus]);

  const handleStatus = async (id, st) => {
    setFounders(prev => prev.map(f => f.id === id ? { ...f, status: st } : f));
    setSelected(prev => prev?.id === id ? { ...prev, status: st } : prev);
    await fetch(`${API}/api/founders/${id}/status`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: st }),
    });
  };

  const handleNotes = (id, notes) => {
    setFounders(prev => prev.map(f => f.id === id ? { ...f, notes } : f));
    setSelected(prev => prev?.id === id ? { ...prev, notes } : prev);
  };

  // Group founders into archetype buckets
  return (
    <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
      {/* List panel */}
      <div style={{ width: 380, flexShrink: 0, display: "flex", flexDirection: "column", borderRight: `1px solid ${C.border}` }}>
        {/* Toolbar */}
        <div style={{ padding: "10px 16px", borderBottom: `1px solid ${C.border}`, display: "flex", flexDirection: "column", gap: 8 }}>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search founders, companies…"
            style={{
              width: "100%", boxSizing: "border-box", padding: "8px 12px",
              border: `1px solid ${C.border}`, borderRadius: 8,
              background: C.bg, fontSize: 13, color: C.text, outline: "none",
            }} />
          {/* Scout mode selector */}
          <div>
            <div style={{ fontSize: 10, color: C.textMuted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 5 }}>Scout for</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
              {SCOUT_MODES.map(m => {
                const active = scoutModeKey === m.key;
                return (
                  <button key={m.key} onClick={() => setScoutModeKey(m.key)} title={m.shortDesc} style={{
                    padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600,
                    cursor: "pointer", border: active ? "none" : `1px solid ${C.border}`,
                    background: active ? m.bg : C.surface,
                    color: active ? m.color : C.textSub,
                    transition: "all 0.15s",
                  }}>{m.label}</button>
                );
              })}
            </div>
            {scoutModeKey !== "all" && (
              <div style={{ marginTop: 5, fontSize: 10, color: C.textMuted, fontStyle: "italic" }}>
                {scoutMode.shortDesc}
              </div>
            )}
          </div>

          {/* Status filter row */}
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {["all", ...Object.keys(STATUS)].map(s => {
              const cfg = STATUS[s];
              const active = filterStatus === s;
              return (
                <button key={s} onClick={() => setFilterStatus(s)} style={{
                  padding: "3px 8px", borderRadius: 6, fontSize: 10, fontWeight: 500,
                  cursor: "pointer", border: `1px solid ${active ? (cfg?.border || C.accentBorder) : C.border}`,
                  background: active ? (cfg?.bg || C.accentLight) : C.surface,
                  color: active ? (cfg?.color || C.accent) : C.textSub,
                }}>{s === "all" ? "All" : cfg.label}</button>
              );
            })}
          </div>
        </div>

        {/* Count summary */}
        <FieldLegend
          total={total}
          filtered={scoutModeKey !== "all" ? visibleStartups.length : null}
          scoutLabel={scoutModeKey !== "all" ? scoutMode.label : null}
        />

        {/* Two-section list */}
        <div ref={listRef} style={{ flex: 1, overflowY: "auto" }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: C.textMuted, fontSize: 13 }}>Loading…</div>
          ) : (
            <>
              {/* ── Startups section ── */}
              <SectionHeader label="Startups" count={visibleStartups.length} />
              {visibleStartups.length === 0 ? (
                <div style={{ padding: "16px 18px", fontSize: 12, color: C.textMuted, fontStyle: "italic" }}>
                  No startups match current filters. Pipeline runs hourly — check back later or switch to All signals.
                </div>
              ) : (
                visibleStartups.map(f => (
                  <StartupCard key={f.id} founder={f} selected={selected?.id === f.id} onClick={setSelected} />
                ))
              )}

              {/* ── Founders to follow section ── */}
              <SectionHeader
                label="Founders to follow"
                count={visibleIndividuals.length}
                collapsible
                subtitle="Pre-company signals — people worth watching before they launch"
                defaultOpen={showIndividuals}
                onToggle={() => setShowIndividuals(v => !v)}
              />
              {showIndividuals && visibleIndividuals.map(f => (
                <IndividualCard key={f.id} founder={f} selected={selected?.id === f.id} onClick={setSelected} />
              ))}
            </>
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        <FounderDetail founder={selected} onStatusChange={handleStatus} onNotesChange={handleNotes} />
      </div>
    </div>
  );
}

// ── Market View (Pulse) ───────────────────────────────────────

function FlowSectorCard({ sector, selected, onClick }) {
  const maxMomentum = 120;
  const pct = Math.min(100, (sector.momentum / maxMomentum) * 100);
  const heat = sector.events > 5 ? "high" : sector.events > 1 ? "mid" : "low";
  const heatColor = heat === "high" ? C.green : heat === "mid" ? C.accent : C.textMuted;
  const heatLabel = heat === "high" ? "Active" : heat === "mid" ? "Building" : "Quiet";
  return (
    <div onClick={() => onClick(sector)}
      style={{
        background: selected ? C.accentLight : C.surface,
        border: `1px solid ${selected ? C.accentBorder : C.border}`,
        borderRadius: 10, padding: "14px 16px",
        display: "flex", flexDirection: "column", gap: 6,
        cursor: "pointer", transition: "all 0.15s",
      }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.borderColor = C.accentBorder; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.borderColor = C.border; }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: C.text, lineHeight: 1.3 }}>{sector.sector}</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: heatColor, background: heat === "high" ? C.greenLight : heat === "mid" ? C.accentLight : C.bg, border: `1px solid ${heat === "high" ? "#a7f3d0" : heat === "mid" ? C.accentBorder : C.borderLight}`, borderRadius: 10, padding: "2px 8px", whiteSpace: "nowrap" }}>{heatLabel}</span>
      </div>
      {/* Momentum bar */}
      <div style={{ height: 3, background: C.borderLight, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: heatColor, borderRadius: 2, transition: "width 0.6s ease" }} />
      </div>
      <div style={{ display: "flex", gap: 12, fontSize: 11, color: C.textMuted }}>
        <span><strong style={{ color: C.textSub }}>{sector.founders}</strong> companies</span>
        <span><strong style={{ color: C.textSub }}>{sector.themes}</strong> clusters</span>
        {sector.events > 0 && <span><strong style={{ color: heatColor }}>{sector.events}</strong> breaks this week</span>}
      </div>
      {sector.topThemes.length > 0 && (
        <div style={{ fontSize: 10, color: C.textMuted, fontStyle: "italic", lineHeight: 1.5 }}>
          {sector.topThemes.slice(0, 2).join(" · ")}
        </div>
      )}
    </div>
  );
}

function FlowFundingItem({ item }) {
  const sectorColors = {
    "AI / ML": { bg: "#f0fdf4", color: "#166534", border: "#bbf7d0" },
    "Dev Tools": { bg: C.accentLight, color: C.accent, border: C.accentBorder },
    "Fintech": { bg: "#fef3c7", color: "#92400e", border: "#fde68a" },
    "Consumer": { bg: "#fdf4ff", color: "#7e22ce", border: "#f3e8ff" },
    "Health": { bg: "#fff1f2", color: "#9f1239", border: "#fecdd3" },
    "Climate": { bg: "#f0fdf4", color: "#14532d", border: "#bbf7d0" },
    "Enterprise SaaS": { bg: "#eff6ff", color: "#1e40af", border: "#bfdbfe" },
    "Robotics": { bg: "#fff7ed", color: "#9a3412", border: "#fed7aa" },
    "Other": { bg: C.bg, color: C.textMuted, border: C.borderLight },
  };
  const sc = sectorColors[item.sector] || sectorColors["Other"];
  return (
    <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", display: "block" }}>
      <div style={{
        padding: "12px 0", borderBottom: `1px solid ${C.borderLight}`,
      }}
        onMouseEnter={e => e.currentTarget.style.opacity = "0.8"}
        onMouseLeave={e => e.currentTarget.style.opacity = "1"}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: sc.bg, color: sc.color, border: `1px solid ${sc.border}`, flexShrink: 0, marginTop: 1 }}>{item.sector}</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.text, lineHeight: 1.4 }}>{item.title}</span>
        </div>
        <div style={{ fontSize: 10, color: C.textMuted, paddingLeft: 2 }}>{item.source} · {item.publishedAt ? new Date(item.publishedAt).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : ""}</div>
      </div>
    </a>
  );
}

function EuWatchPanel({ euLog, euInput, setEuInput, onAdd, onRemove }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 24, border: `1px solid ${C.borderLight}`, borderRadius: 10, overflow: "hidden" }}>
      <div onClick={() => setOpen(o => !o)} style={{
        padding: "10px 16px", display: "flex", justifyContent: "space-between", alignItems: "center",
        cursor: "pointer", userSelect: "none", background: C.surface,
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          EU Pattern Watch {euLog.length > 0 && <span style={{ fontWeight: 400, color: C.textMuted }}>({euLog.length})</span>}
        </span>
        <span style={{ fontSize: 10, color: C.textMuted }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "14px 16px", background: C.bg }}>
          <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 10 }}>
            Log EU trends that typically precede US by 12–36 months.
          </div>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input value={euInput} onChange={e => setEuInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && onAdd()}
              placeholder="e.g. Secondhand fashion gaining traction in Germany — est. 18 months to US"
              style={{ flex: 1, padding: "8px 12px", border: `1px solid ${C.border}`, borderRadius: 7, background: C.surface, fontSize: 12, color: C.text, outline: "none" }} />
            <button onClick={onAdd} style={{ padding: "8px 14px", borderRadius: 7, fontSize: 12, fontWeight: 600, background: C.accent, color: "#fff", border: "none", cursor: "pointer" }}>Log</button>
          </div>
          {euLog.length === 0
            ? <div style={{ fontSize: 12, color: C.textMuted, fontStyle: "italic" }}>Nothing logged yet.</div>
            : euLog.map(entry => (
              <div key={entry.id} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 0", borderTop: `1px solid ${C.borderLight}` }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: C.text }}>{entry.text}</div>
                  <div style={{ fontSize: 10, color: C.textMuted, marginTop: 2 }}>{entry.date}</div>
                </div>
                <button onClick={() => onRemove(entry.id)} style={{ background: "none", border: "none", color: C.textMuted, cursor: "pointer", fontSize: 14, padding: 0 }}>×</button>
              </div>
            ))
          }
        </div>
      )}
    </div>
  );
}

function SectorDetail({ sector, themes, onClose }) {
  const clusters = (themes || []).filter(t => (t.sector || "Other") === sector.sector);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{sector.sector}</div>
          <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2 }}>
            {clusters.length} clusters · {sector.founders} companies
            {sector.events > 0 && ` · ${sector.events} breaks this week`}
          </div>
        </div>
        <button onClick={onClose} style={{ background: "none", border: `1px solid ${C.border}`, borderRadius: 6, padding: "4px 10px", fontSize: 11, color: C.textMuted, cursor: "pointer" }}>
          Back to funding
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {clusters.length === 0 && (
          <div style={{ fontSize: 12, color: C.textMuted, fontStyle: "italic", padding: 12 }}>No clusters found for this sector.</div>
        )}
        {clusters.map(c => (
          <div key={c.id} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "13px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text, flex: 1 }}>{c.name}</span>
              <span style={{ fontSize: 11, color: C.textMuted, background: C.bg, border: `1px solid ${C.borderLight}`, borderRadius: 10, padding: "1px 8px" }}>
                {c.builderCount} companies
              </span>
            </div>
            {c.description && (
              <div style={{ fontSize: 12, color: C.textSub, lineHeight: 1.5, marginBottom: 8 }}>{c.description}</div>
            )}
            {c.founders?.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {c.founders.slice(0, 5).map(f => (
                  <span key={f.id} style={{ fontSize: 11, color: C.textSub, background: C.bg, border: `1px solid ${C.borderLight}`, borderRadius: 6, padding: "2px 8px" }}>
                    {f.company || f.name}
                  </span>
                ))}
                {c.founders.length > 5 && (
                  <span style={{ fontSize: 11, color: C.textMuted }}>+{c.founders.length - 5} more</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MarketView() {
  const [data, setData] = useState(null);
  const [themes, setThemes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSector, setSelectedSector] = useState(null);
  const [euLog, setEuLog] = useState(() => {
    try { return JSON.parse(localStorage.getItem("eu_signals") || "[]"); } catch { return []; }
  });
  const [euInput, setEuInput] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/flow`).then(r => r.json()),
      fetch(`${API}/api/themes`).then(r => r.json()),
    ]).then(([flowData, themesData]) => {
      setData(flowData);
      setThemes(Array.isArray(themesData) ? themesData : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const addEuSignal = () => {
    if (!euInput.trim()) return;
    const entry = { text: euInput.trim(), date: new Date().toISOString().slice(0, 10), id: Date.now() };
    const updated = [entry, ...euLog];
    setEuLog(updated);
    localStorage.setItem("eu_signals", JSON.stringify(updated));
    setEuInput("");
  };

  const removeEuSignal = (id) => {
    const updated = euLog.filter(e => e.id !== id);
    setEuLog(updated);
    localStorage.setItem("eu_signals", JSON.stringify(updated));
  };

  if (loading) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: C.textMuted, fontSize: 13 }}>Loading market signals…</div>
  );

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: C.text, marginBottom: 4 }}>Flow</div>
          <div style={{ fontSize: 13, color: C.textMuted }}>Sector momentum · Recent funding · EU pattern watch</div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 24, alignItems: "start" }}>

          {/* LEFT — Sector heat */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
              Sector Heat <span style={{ fontSize: 10, fontWeight: 400, fontStyle: "italic" }}>— click to explore clusters</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {(data?.sectors || []).map(s => (
                <FlowSectorCard
                  key={s.sector}
                  sector={s}
                  selected={selectedSector?.sector === s.sector}
                  onClick={s => setSelectedSector(prev => prev?.sector === s.sector ? null : s)}
                />
              ))}
              {(!data?.sectors || data.sectors.length === 0) && (
                <div style={{ fontSize: 12, color: C.textMuted, fontStyle: "italic" }}>No sector data yet — run the pipeline to generate clusters.</div>
              )}
            </div>
          </div>

          {/* RIGHT — Sector detail OR Funding pulse + inflections */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {selectedSector ? (
            <SectorDetail
              sector={selectedSector}
              themes={themes}
              onClose={() => setSelectedSector(null)}
            />
          ) : (
            <>
            {/* Funding news */}
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>Recent Funding</div>
              <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "0 16px" }}>
                {(data?.funding || []).map((item, i) => <FlowFundingItem key={i} item={item} />)}
                {(!data?.funding || data.funding.length === 0) && (
                  <div style={{ padding: "20px 0", fontSize: 12, color: C.textMuted, fontStyle: "italic" }}>No funding news loaded — RSS may be unavailable.</div>
                )}
              </div>
            </div>

            {/* Inflections */}
            {data?.inflections?.length > 0 && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>Breaks This Week</div>
                <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden" }}>
                  {data.inflections.slice(0, 8).map((inf, i) => (
                    <div key={i} style={{ padding: "10px 16px", borderBottom: i < Math.min(7, data.inflections.length - 1) ? `1px solid ${C.borderLight}` : "none", display: "flex", gap: 10, alignItems: "flex-start" }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, color: C.text, fontWeight: 600, marginBottom: 2 }}>{inf.company || inf.founderName}</div>
                        <div style={{ fontSize: 11, color: C.textMuted }}>{inf.signal?.replace(/^[A-Z][a-z]+ [a-z]+ /,"")?.slice(0, 100)}</div>
                      </div>
                      <span style={{ fontSize: 10, color: C.textMuted, whiteSpace: "nowrap", marginTop: 2 }}>{inf.detectedAt?.slice(0,10)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            </>
          )}
          </div>
        </div>

        {/* EU Pattern Watch — compact, collapsible */}
        <EuWatchPanel euLog={euLog} euInput={euInput} setEuInput={setEuInput} onAdd={addEuSignal} onRemove={removeEuSignal} />

      </div>
    </div>
  );
}

// ── Root App ──────────────────────────────────────────────────

export default function App() {
  const [view, setView] = useState("field");
  const [stats, setStats] = useState({ total: 0, strong: 0, toContact: 0, avgScore: 0 });

  useEffect(() => {
    if (!API) return;
    fetch(`${API}/api/stats`).then(r => r.json()).then(setStats).catch(() => {});
  }, []);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}>
      <TopNav view={view} setView={setView} stats={stats} />
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {view === "raw" && <PulseView />}
        {view === "field" && <ScoutingView />}
        {view === "patterns" && <ThemesView />}
        {view === "breaks" && <EmergenceView />}
        {view === "flow" && <MarketView />}
      </div>
    </div>
  );
}
