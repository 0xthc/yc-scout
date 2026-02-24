import { useState, useEffect, useCallback, useRef } from "react";

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

const DIMS = {
  founder_quality: "Founder Quality",
  execution_velocity: "Execution",
  market_conviction: "Conviction",
  early_traction: "Traction",
  deal_availability: "Availability",
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

function ScoreBar({ label, value }) {
  const color = scoreColor(value);
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: C.textSub }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: "ui-monospace, monospace" }}>{value}</span>
      </div>
      <div style={{ height: 4, background: C.borderLight, borderRadius: 4, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${value}%`, background: color, borderRadius: 4, transition: "width 0.5s ease" }} />
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

const VIEWS = ["raw", "field", "patterns", "breaks"];
const VIEW_LABELS = { raw: "Raw", field: "Field", patterns: "Patterns", breaks: "Breaks" };
const VIEW_ICONS = { raw: "", field: "", patterns: "", breaks: "" };

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

function FounderRow({ founder, selected, onClick }) {
  const sc = SOURCE[founder.sources?.[0]] || SOURCE.github;
  return (
    <div onClick={() => onClick(founder)} style={{
      display: "flex", alignItems: "center", gap: 14, padding: "12px 20px",
      borderBottom: `1px solid ${C.borderLight}`, cursor: "pointer",
      background: selected ? C.accentLight : "transparent", transition: "background 0.1s",
    }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = C.bg; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = "transparent"; }}>

      <div style={{
        width: 36, height: 36, borderRadius: "50%", background: `${scoreColor(founder.score)}18`,
        border: `1.5px solid ${scoreColor(founder.score)}40`, display: "flex",
        alignItems: "center", justifyContent: "center", fontSize: 13,
        fontWeight: 700, color: scoreColor(founder.score), flexShrink: 0,
      }}>
        {(founder.name || "?")[0].toUpperCase()}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: C.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {founder.company || founder.name}
          </span>
          {founder.stage && (
            <span style={{ fontSize: 10, color: C.accent, background: C.accentLight, padding: "1px 6px", borderRadius: 4, flexShrink: 0 }}>
              {founder.stage}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: C.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {founder.name} · {founder.domain} · {founder.location}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 4, color: sc.color, background: sc.bg }}>{sc.label}</span>
        <ScorePill score={founder.score} size="sm" />
      </div>
    </div>
  );
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
            {founder.stage && <Badge>{founder.stage}</Badge>}
            <button onClick={() => onStatusChange(founder.id, nextStatus)} style={{
              padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600,
              cursor: "pointer", border: `1px solid ${stCfg.border}`,
              background: stCfg.bg, color: stCfg.color,
            }}>{stCfg.label}</button>
          </div>
          <div style={{ fontSize: 12, color: C.textMuted }}>{founder.name} · {founder.domain} · {founder.location}</div>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: C.textSub, lineHeight: 1.5 }}>{founder.bio}</p>
        </div>
        <ScorePill score={founder.score} />
      </div>

      {/* Stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 20 }}>
        {[
          { label: "GH Stars", val: (founder.github_stars || 0).toLocaleString(), color: SOURCE.github.color },
          { label: "Commits/90d", val: (founder.github_commits_90d || 0).toLocaleString(), color: SOURCE.github.color },
          { label: "HN Karma", val: (founder.hn_karma || 0).toLocaleString(), color: SOURCE.hn.color },
          { label: "HN Top", val: `${founder.hn_top_score || 0} pts`, color: SOURCE.hn.color },
          { label: "PH Upvotes", val: (founder.ph_upvotes || 0).toLocaleString(), color: SOURCE.producthunt.color },
          { label: "Followers", val: founder.followers >= 1000 ? `${(founder.followers / 1000).toFixed(1)}k` : String(founder.followers || 0), color: C.accent },
        ].map(({ label, val, color }) => (
          <Card key={label} style={{ padding: "10px 14px" }}>
            <div style={{ fontSize: 10, color: C.textMuted, marginBottom: 3 }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color, fontFamily: "ui-monospace, monospace" }}>{val}</div>
          </Card>
        ))}
      </div>

      {/* Score breakdown */}
      <Card style={{ padding: 16, marginBottom: 16 }}>
        <SectionTitle>Score Breakdown</SectionTitle>
        {Object.entries(DIMS).map(([dim, label]) => (
          <ScoreBar key={dim} label={label} value={founder.scoreBreakdown?.[dim] || 0} />
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
    key: "act_now",
    label: "Act Now",
    desc: "Score ≥ 85 · not yet contacted",
    color: C.green,
    bg: C.greenLight,
    border: "#a7f3d0",
    match: f => f.score >= 85 && !["pass", "contacted"].includes(f.status),
  },
  {
    key: "serial",
    label: "Serial Founders",
    desc: "Prior company detected",
    color: C.accent,
    bg: C.accentLight,
    border: C.accentBorder,
    match: f => f.is_serial_founder,
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
    desc: "Everything else",
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

function ScoutingView() {
  const [founders, setFounders] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [debSearch, setDebSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [viewMode, setViewMode] = useState("grouped"); // "grouped" | "list"
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    const t = setTimeout(() => setDebSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Grouped mode fetches all at once; list mode paginates
  const buildUrl = useCallback((offset = 0) => {
    const limit = viewMode === "grouped" ? 2000 : PAGE_SIZE;
    const p = new URLSearchParams({ limit, offset });
    if (debSearch) p.set("search", debSearch);
    if (filterStatus !== "all") p.set("status", filterStatus);
    return `${API}/api/founders?${p}`;
  }, [debSearch, filterStatus, viewMode]);

  const fetchFounders = useCallback(async (reset = false) => {
    if (reset) setLoading(true);
    try {
      const res = await fetch(buildUrl(0));
      const data = await res.json();
      setFounders(data.founders || []);
      setTotal(data.total || 0);
    } finally { setLoading(false); }
  }, [buildUrl]);

  useEffect(() => { fetchFounders(true); }, [debSearch, filterStatus, viewMode]);

  const loadMore = useCallback(async () => {
    if (viewMode === "grouped" || loadingMore || founders.length >= total) return;
    setLoadingMore(true);
    try {
      const res = await fetch(buildUrl(founders.length));
      const data = await res.json();
      setFounders(prev => [...prev, ...(data.founders || [])]);
    } finally { setLoadingMore(false); }
  }, [founders.length, total, loadingMore, buildUrl, viewMode]);

  useEffect(() => {
    const el = listRef.current;
    if (!el || viewMode === "grouped") return;
    const fn = () => { if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) loadMore(); };
    el.addEventListener("scroll", fn);
    return () => el.removeEventListener("scroll", fn);
  }, [loadMore, viewMode]);

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
  const grouped = useCallback(() => {
    const buckets = Object.fromEntries(ARCHETYPES.map(a => [a.key, []]));
    founders.forEach(f => {
      const keys = classifyFounder(f);
      keys.forEach(k => buckets[k].push(f));
    });
    return buckets;
  }, [founders]);

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
          {/* Mode toggle + status filters */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            {/* View mode toggle */}
            <div style={{ display: "flex", background: C.bg, borderRadius: 7, border: `1px solid ${C.border}`, padding: 2, gap: 2 }}>
              {[["grouped", "Archetypes"], ["list", "List"]].map(([mode, lbl]) => (
                <button key={mode} onClick={() => setViewMode(mode)} style={{
                  padding: "3px 10px", borderRadius: 5, fontSize: 11, fontWeight: 600,
                  cursor: "pointer", border: "none", transition: "all 0.15s",
                  background: viewMode === mode ? C.surface : "transparent",
                  color: viewMode === mode ? C.text : C.textMuted,
                  boxShadow: viewMode === mode ? C.shadow : "none",
                }}>{lbl}</button>
              ))}
            </div>
            {/* Status filters (list mode only) */}
            {viewMode === "list" && (
              <div style={{ display: "flex", gap: 4 }}>
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
            )}
          </div>
        </div>

        {/* Count */}
        <div style={{ padding: "6px 20px", fontSize: 11, color: C.textMuted, borderBottom: `1px solid ${C.borderLight}` }}>
          {total} founders
        </div>

        {/* List / Grouped */}
        <div ref={listRef} style={{ flex: 1, overflowY: "auto" }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: C.textMuted, fontSize: 13 }}>Loading founders…</div>
          ) : founders.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: C.textMuted, fontSize: 13 }}>No founders match filters</div>
          ) : viewMode === "grouped" ? (
            // ── Archetype buckets ──
            (() => {
              const buckets = grouped();
              return ARCHETYPES.map((arch, i) => (
                <ArchetypeSection
                  key={arch.key}
                  archetype={arch}
                  founders={buckets[arch.key]}
                  selected={selected}
                  onSelect={setSelected}
                  defaultOpen={i < 3}
                />
              ));
            })()
          ) : (
            // ── Flat list ──
            <>
              {founders.map(f => (
                <FounderRow key={f.id} founder={f} selected={selected?.id === f.id} onClick={setSelected} />
              ))}
              {loadingMore && <div style={{ padding: 12, textAlign: "center", color: C.textMuted, fontSize: 12 }}>Loading more…</div>}
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

function MarketView() {
  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12, padding: 40, textAlign: "center" }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: C.text, letterSpacing: "0.02em" }}>Pulse</div>
      <div style={{ fontSize: 13, color: C.textMuted, maxWidth: 480, lineHeight: 1.6 }}>
        Coming soon — fund portfolio signals, investment flow, sector heat maps. Track where capital is moving before it's public.
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
      </div>
    </div>
  );
}
