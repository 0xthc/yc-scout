import { useState, useEffect, useCallback, useRef } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "";

const SOURCE_COLORS = {
  github: { bg: "#1a1a2e", accent: "#58a6ff", label: "GH" },
  hn: { bg: "#2d1a00", accent: "#ff6600", label: "HN" },
  producthunt: { bg: "#2d1117", accent: "#da552f", label: "PH" },
};

const STATUS_CONFIG = {
  to_contact: { label: "To Contact", color: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  watching: { label: "Watching", color: "#60a5fa", bg: "rgba(96,165,250,0.12)" },
  contacted: { label: "Contacted", color: "#34d399", bg: "rgba(52,211,153,0.12)" },
  pass: { label: "Pass", color: "#6b7280", bg: "rgba(107,114,128,0.12)" },
};

const SCORE_LABEL = (s) => s >= 90 ? "STRONG" : s >= 80 ? "GOOD" : s >= 70 ? "MONITOR" : "WEAK";
const SCORE_COLOR = (s) => s >= 90 ? "#34d399" : s >= 80 ? "#f59e0b" : s >= 70 ? "#60a5fa" : "#6b7280";

function ScoreRing({ score, size = 52 }) {
  const r = (size / 2) - 5;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = SCORE_COLOR(score);
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1e1e2e" strokeWidth="4" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4"
        strokeDasharray={`${fill} ${circ}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)" }} />
      <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central"
        style={{
          transform: "rotate(90deg)", transformOrigin: `${size / 2}px ${size / 2}px`,
          fill: color, fontSize: size < 40 ? "10px" : "13px", fontWeight: 700, fontFamily: "'DM Mono', monospace"
        }}>
        {score}
      </text>
    </svg>
  );
}

function ScoreBar({ label, value }) {
  const color = SCORE_COLOR(value);
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 10, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.08em", fontFamily: "DM Mono, monospace" }}>{label}</span>
        <span style={{ fontSize: 10, color, fontFamily: "DM Mono, monospace", fontWeight: 700 }}>{value}</span>
      </div>
      <div style={{ height: 3, background: "#1e1e2e", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${value}%`, background: color, borderRadius: 2, transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

function SourceBadge({ source }) {
  const cfg = SOURCE_COLORS[source];
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, fontFamily: "DM Mono, monospace", letterSpacing: "0.1em",
      padding: "2px 6px", borderRadius: 3, background: cfg.bg, color: cfg.accent,
      border: `1px solid ${cfg.accent}22`
    }}>{cfg.label}</span>
  );
}

function SignalDot({ type }) {
  const cfg = SOURCE_COLORS[type];
  return <span style={{ width: 7, height: 7, borderRadius: "50%", background: cfg.accent, display: "inline-block", flexShrink: 0, marginTop: 4 }} />;
}

function Avatar({ initials, score }) {
  const color = SCORE_COLOR(score);
  return (
    <div style={{
      width: 42, height: 42, borderRadius: "50%", background: `${color}18`,
      border: `1.5px solid ${color}44`, display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 13, fontWeight: 700, color, fontFamily: "DM Mono, monospace", flexShrink: 0
    }}>{initials}</div>
  );
}

function StatusBadge({ status, onClick }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <button onClick={onClick} style={{
      fontSize: 10, fontWeight: 600, fontFamily: "DM Mono, monospace", letterSpacing: "0.08em",
      padding: "3px 8px", borderRadius: 4, background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}33`, cursor: "pointer", transition: "all 0.2s"
    }}>{cfg.label}</button>
  );
}

function FounderCard({ founder, onClick, selected }) {
  return (
    <div onClick={() => onClick(founder)} style={{
      padding: "14px 16px", borderBottom: "1px solid #13131f",
      background: selected ? "#0f0f1a" : "transparent",
      borderLeft: selected ? "2px solid #7c3aed" : "2px solid transparent",
      cursor: "pointer", transition: "all 0.15s",
    }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = "#0a0a14"; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = "transparent"; }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <Avatar initials={founder.avatar} score={founder.score} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 2 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0", fontFamily: "Syne, sans-serif" }}>{founder.name}</span>
              <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "DM Mono, monospace" }}>{founder.handle}</span>
            </div>
            <ScoreRing score={founder.score} size={36} />
          </div>
          <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 6, lineHeight: 1.4, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{founder.bio}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            {founder.sources.map(s => <SourceBadge key={s} source={s} />)}
            <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "DM Mono, monospace" }}>·</span>
            <span style={{ fontSize: 10, color: "#7c3aed", fontFamily: "DM Mono, monospace" }}>{founder.domain}</span>
            <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "DM Mono, monospace" }}>·</span>
            <span style={{ fontSize: 10, color: "#4b5563" }}>{founder.location}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailPanel({ founder, onStatusChange }) {
  if (!founder) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#2d2d44", fontSize: 13, fontFamily: "DM Mono, monospace" }}>
      &larr; SELECT A FOUNDER TO INSPECT
    </div>
  );

  const statuses = Object.keys(STATUS_CONFIG);
  const nextStatus = statuses[(statuses.indexOf(founder.status) + 1) % statuses.length];

  return (
    <div style={{ height: "100%", overflowY: "auto", padding: "24px 24px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24, paddingBottom: 20, borderBottom: "1px solid #13131f" }}>
        <Avatar initials={founder.avatar} score={founder.score} />
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: "#e2e8f0", fontFamily: "Syne, sans-serif" }}>{founder.name}</h2>
            <StatusBadge status={founder.status} onClick={() => onStatusChange(founder.id, nextStatus)} />
          </div>
          <div style={{ fontSize: 11, color: "#6b7280", fontFamily: "DM Mono, monospace", marginBottom: 6 }}>{founder.handle} · {founder.location}</div>
          <p style={{ margin: 0, fontSize: 12, color: "#9ca3af", lineHeight: 1.6 }}>{founder.bio}</p>
        </div>
        <div style={{ textAlign: "center" }}>
          <ScoreRing score={founder.score} size={60} />
          <div style={{ fontSize: 9, color: SCORE_COLOR(founder.score), fontFamily: "DM Mono, monospace", fontWeight: 700, marginTop: 3, letterSpacing: "0.1em" }}>{SCORE_LABEL(founder.score)}</div>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 20 }}>
        {[
          { label: "GH Stars", value: founder.github_stars.toLocaleString() },
          { label: "HN Karma", value: founder.hn_karma.toLocaleString() },
          { label: "Followers", value: (founder.followers / 1000).toFixed(1) + "k" },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: "#08080f", border: "1px solid #13131f", borderRadius: 8, padding: "10px 12px" }}>
            <div style={{ fontSize: 9, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.1em", fontFamily: "DM Mono, monospace", marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#e2e8f0", fontFamily: "DM Mono, monospace" }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Score breakdown */}
      <div style={{ background: "#08080f", border: "1px solid #13131f", borderRadius: 8, padding: "14px 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.12em", fontFamily: "DM Mono, monospace", marginBottom: 12 }}>Score Breakdown</div>
        {Object.entries(founder.scoreBreakdown).map(([k, v]) => (
          <ScoreBar key={k} label={k} value={v} />
        ))}
      </div>

      {/* Signals */}
      <div style={{ background: "#08080f", border: "1px solid #13131f", borderRadius: 8, padding: "14px 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 9, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.12em", fontFamily: "DM Mono, monospace", marginBottom: 12 }}>Recent Signals</div>
        {founder.signals.map((sig, i) => (
          <div key={i} style={{ display: "flex", gap: 10, marginBottom: i < founder.signals.length - 1 ? 10 : 0, paddingBottom: i < founder.signals.length - 1 ? 10 : 0, borderBottom: i < founder.signals.length - 1 ? "1px solid #0e0e18" : "none" }}>
            <SignalDot type={sig.type} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: sig.strong ? "#e2e8f0" : "#9ca3af", lineHeight: 1.4 }}>{sig.label}</div>
              <div style={{ fontSize: 10, color: "#4b5563", fontFamily: "DM Mono, monospace", marginTop: 2 }}>{sig.date}</div>
            </div>
            {sig.strong && <span style={{ fontSize: 9, color: "#f59e0b", fontFamily: "DM Mono, monospace", fontWeight: 700, padding: "2px 5px", background: "rgba(245,158,11,0.1)", borderRadius: 3, height: "fit-content" }}>KEY</span>}
          </div>
        ))}
      </div>

      {/* Meta */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div style={{ background: "#08080f", border: "1px solid #13131f", borderRadius: 8, padding: "12px 14px" }}>
          <div style={{ fontSize: 9, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.1em", fontFamily: "DM Mono, monospace", marginBottom: 8 }}>Company</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0", fontFamily: "Syne, sans-serif", marginBottom: 4 }}>{founder.company}</div>
          <div style={{ fontSize: 11, color: "#7c3aed" }}>{founder.stage}</div>
          <div style={{ fontSize: 10, color: "#4b5563", marginTop: 4, fontFamily: "DM Mono, monospace" }}>Founded {founder.founded}</div>
        </div>
        <div style={{ background: "#08080f", border: "1px solid #13131f", borderRadius: 8, padding: "12px 14px" }}>
          <div style={{ fontSize: 9, color: "#4b5563", textTransform: "uppercase", letterSpacing: "0.1em", fontFamily: "DM Mono, monospace", marginBottom: 8 }}>Network</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: founder.yc_alumni_connections > 0 ? "#34d399" : "#4b5563", fontFamily: "DM Mono, monospace" }}>{founder.yc_alumni_connections}</div>
          <div style={{ fontSize: 10, color: "#6b7280" }}>YC alumni connections</div>
        </div>
      </div>

      {/* Tags */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 14 }}>
        {founder.tags.map(t => (
          <span key={t} style={{ fontSize: 10, padding: "3px 8px", borderRadius: 4, background: "#0d0d1a", border: "1px solid #1e1e2e", color: "#6b7280", fontFamily: "DM Mono, monospace" }}>#{t}</span>
        ))}
      </div>

      {/* CTA */}
      <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
        <button style={{
          flex: 1, padding: "10px", background: "linear-gradient(135deg, #7c3aed, #5b21b6)",
          border: "none", borderRadius: 8, color: "#fff", fontSize: 12, fontWeight: 700,
          fontFamily: "DM Mono, monospace", cursor: "pointer", letterSpacing: "0.05em"
        }}>REACH OUT</button>
        <button style={{
          padding: "10px 14px", background: "#08080f", border: "1px solid #1e1e2e",
          borderRadius: 8, color: "#9ca3af", fontSize: 12, cursor: "pointer"
        }}>&#9733;</button>
      </div>
    </div>
  );
}

const PAGE_SIZE = 50;

export default function App() {
  const [founders, setFounders] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(null);
  const [filterSource, setFilterSource] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [sortBy, setSortBy] = useState("score");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [live, setLive] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const listRef = useRef(null);

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const buildUrl = useCallback((offset = 0) => {
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset });
    if (debouncedSearch) params.set("search", debouncedSearch);
    if (filterSource !== "all") params.set("source", filterSource);
    if (filterStatus !== "all") params.set("status", filterStatus);
    if (sortBy === "stars") params.set("sort", "stars");
    return `${API_BASE}/api/founders?${params}`;
  }, [debouncedSearch, filterSource, filterStatus, sortBy]);

  // Fetch first page (on filter/search/sort change)
  const fetchFounders = useCallback(async (isInitial = false) => {
    if (!API_BASE) {
      setLoading(false);
      setError("No API URL configured. Set VITE_API_URL to connect.");
      return;
    }
    if (isInitial) setLoading(true);
    try {
      const res = await fetch(buildUrl(0));
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      const data = await res.json();
      setFounders(data.founders || []);
      setTotal(data.total || 0);
      setLive(true);
      setLastSync(new Date());
      setError(null);
    } catch (err) {
      if (isInitial) setError(`Failed to load founders: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [buildUrl]);

  // Load next page (infinite scroll)
  const loadMore = useCallback(async () => {
    if (loadingMore || founders.length >= total) return;
    setLoadingMore(true);
    try {
      const res = await fetch(buildUrl(founders.length));
      if (!res.ok) return;
      const data = await res.json();
      const next = data.founders || [];
      if (next.length > 0) {
        setFounders(prev => [...prev, ...next]);
      }
    } catch { /* ignore */ } finally {
      setLoadingMore(false);
    }
  }, [buildUrl, founders.length, total, loadingMore]);

  // Initial load
  useEffect(() => {
    setTimeout(() => setLoaded(true), 100);
    fetchFounders(true);
  }, []);

  // Re-fetch when filters/search/sort change (reset to page 1)
  useEffect(() => {
    if (!loaded) return;
    if (listRef.current) listRef.current.scrollTop = 0;
    fetchFounders(false);
  }, [debouncedSearch, filterSource, filterStatus, sortBy]);

  // Background refresh every 60s
  useEffect(() => {
    if (!API_BASE) return;
    const interval = setInterval(() => fetchFounders(false), 60000);
    return () => clearInterval(interval);
  }, [fetchFounders]);

  // Infinite scroll: load more when near bottom of list panel
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const onScroll = () => {
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) {
        loadMore();
      }
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, [loadMore]);

  const hasMore = founders.length < total;

  const handleStatusChange = async (id, newStatus) => {
    setFounders(prev => prev.map(f => f.id === id ? { ...f, status: newStatus } : f));
    setSelected(prev => prev?.id === id ? { ...prev, status: newStatus } : prev);
    if (API_BASE) {
      try {
        await fetch(`${API_BASE}/api/founders/${id}/status`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        });
      } catch { /* optimistic update — ignore network errors */ }
    }
  };

  const stats = {
    total: total || founders.length,
    strong: founders.filter(f => f.score >= 90).length,
    toContact: founders.filter(f => f.status === "to_contact").length,
    avgScore: founders.length ? Math.round(founders.reduce((s, f) => s + f.score, 0) / founders.length) : 0,
  };

  return (
    <div style={{
      height: "100vh", background: "#06060e", color: "#e2e8f0",
      fontFamily: "system-ui, sans-serif", display: "flex", flexDirection: "column",
      opacity: loaded ? 1 : 0, transition: "opacity 0.4s ease",
    }}>
      {/* Header */}
      <header style={{
        padding: "0 24px", height: 52, borderBottom: "1px solid #0e0e1a",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "#06060e", flexShrink: 0
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 20, height: 20, background: "linear-gradient(135deg, #7c3aed, #2563eb)", borderRadius: 5 }} />
            <span style={{ fontSize: 14, fontWeight: 900, fontFamily: "Syne, sans-serif", letterSpacing: "-0.01em", color: "#e2e8f0" }}>SCOUT</span>
            <span style={{ fontSize: 9, color: "#4b5563", fontFamily: "DM Mono, monospace", letterSpacing: "0.15em", paddingTop: 1 }}>YC INTELLIGENCE</span>
          </div>

          <div style={{ width: 1, height: 20, background: "#13131f" }} />

          {/* Stats pills */}
          {[
            { label: "Tracked", val: stats.total },
            { label: "Strong Signal", val: stats.strong, color: "#34d399" },
            { label: "To Contact", val: stats.toContact, color: "#f59e0b" },
            { label: "Avg Score", val: stats.avgScore, color: "#7c3aed" },
          ].map(({ label, val, color }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: color || "#e2e8f0", fontFamily: "DM Mono, monospace" }}>{val}</span>
              <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "DM Mono, monospace" }}>{label}</span>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: loading ? "#6b7280" : live ? "#34d399" : "#ef4444", boxShadow: `0 0 6px ${loading ? "#6b7280" : live ? "#34d399" : "#ef4444"}` }} />
          <span style={{ fontSize: 10, color: loading ? "#6b7280" : live ? "#34d399" : "#ef4444", fontFamily: "DM Mono, monospace" }}>{loading ? "LOADING" : live ? "LIVE" : "OFFLINE"}</span>
        </div>
      </header>

      {/* Toolbar */}
      <div style={{
        padding: "10px 16px", borderBottom: "1px solid #0e0e1a",
        display: "flex", alignItems: "center", gap: 10, background: "#07070f", flexShrink: 0
      }}>
        {/* Search */}
        <div style={{ position: "relative", flex: 1, maxWidth: 260 }}>
          <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "#4b5563", fontSize: 12 }}>&#x2315;</span>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search founders, companies..."
            style={{
              width: "100%", padding: "7px 12px 7px 28px", background: "#0a0a14",
              border: "1px solid #13131f", borderRadius: 6, color: "#e2e8f0",
              fontSize: 12, outline: "none", fontFamily: "DM Mono, monospace", boxSizing: "border-box"
            }} />
        </div>

        {/* Source filter */}
        <div style={{ display: "flex", gap: 4 }}>
          {["all", "github", "hn", "producthunt"].map(src => {
            const active = filterSource === src;
            const label = src === "all" ? "All Sources" : SOURCE_COLORS[src].label;
            const color = src !== "all" ? SOURCE_COLORS[src].accent : "#7c3aed";
            return (
              <button key={src} onClick={() => setFilterSource(src)} style={{
                padding: "5px 10px", borderRadius: 5, fontSize: 10, fontFamily: "DM Mono, monospace", fontWeight: 700,
                cursor: "pointer", letterSpacing: "0.08em", transition: "all 0.15s",
                background: active ? `${color}18` : "#0a0a14",
                border: active ? `1px solid ${color}55` : "1px solid #13131f",
                color: active ? color : "#4b5563"
              }}>{label}</button>
            );
          })}
        </div>

        <div style={{ width: 1, height: 20, background: "#13131f" }} />

        {/* Status filter */}
        <div style={{ display: "flex", gap: 4 }}>
          {["all", ...Object.keys(STATUS_CONFIG)].map(s => {
            const active = filterStatus === s;
            const cfg = s !== "all" ? STATUS_CONFIG[s] : null;
            return (
              <button key={s} onClick={() => setFilterStatus(s)} style={{
                padding: "5px 9px", borderRadius: 5, fontSize: 10, fontFamily: "DM Mono, monospace", fontWeight: 600,
                cursor: "pointer", transition: "all 0.15s",
                background: active ? (cfg ? cfg.bg : "rgba(124,58,237,0.12)") : "#0a0a14",
                border: active ? `1px solid ${cfg ? cfg.color : "#7c3aed"}44` : "1px solid #13131f",
                color: active ? (cfg ? cfg.color : "#7c3aed") : "#4b5563"
              }}>{s === "all" ? "All" : STATUS_CONFIG[s].label}</button>
            );
          })}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "DM Mono, monospace", alignSelf: "center" }}>Sort:</span>
          {["score", "stars"].map(s => (
            <button key={s} onClick={() => setSortBy(s)} style={{
              padding: "5px 9px", borderRadius: 5, fontSize: 10, fontFamily: "DM Mono, monospace",
              cursor: "pointer", background: sortBy === s ? "rgba(124,58,237,0.15)" : "#0a0a14",
              border: sortBy === s ? "1px solid #7c3aed55" : "1px solid #13131f",
              color: sortBy === s ? "#7c3aed" : "#4b5563"
            }}>{s === "score" ? "Score" : "GH Stars"}</button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* List panel */}
        <div ref={listRef} style={{ width: 380, flexShrink: 0, borderRight: "1px solid #0e0e1a", overflowY: "auto" }}>
          {loading ? (
            <div style={{ padding: 60, textAlign: "center" }}>
              <div style={{ width: 28, height: 28, border: "3px solid #1e1e2e", borderTop: "3px solid #7c3aed", borderRadius: "50%", margin: "0 auto 16px", animation: "spin 0.8s linear infinite" }} />
              <div style={{ color: "#4b5563", fontSize: 12, fontFamily: "DM Mono, monospace" }}>LOADING FOUNDERS...</div>
              <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
          ) : error ? (
            <div style={{ padding: 40, textAlign: "center" }}>
              <div style={{ color: "#ef4444", fontSize: 12, fontFamily: "DM Mono, monospace", marginBottom: 12 }}>{error}</div>
              <button onClick={() => fetchFounders(true)} style={{
                padding: "8px 16px", background: "#1e1e2e", border: "1px solid #2d2d44", borderRadius: 6,
                color: "#9ca3af", fontSize: 11, fontFamily: "DM Mono, monospace", cursor: "pointer"
              }}>RETRY</button>
            </div>
          ) : founders.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "#2d2d44", fontSize: 12, fontFamily: "DM Mono, monospace" }}>
              {(debouncedSearch || filterSource !== "all" || filterStatus !== "all") ? "NO FOUNDERS MATCH FILTERS" : "NO FOUNDERS YET — RUN THE PIPELINE"}
            </div>
          ) : (
            <>
              {founders.map(f => (
                <FounderCard key={f.id} founder={f} onClick={setSelected} selected={selected?.id === f.id} />
              ))}
              {loadingMore && (
                <div style={{ padding: 16, textAlign: "center" }}>
                  <div style={{ width: 20, height: 20, border: "2px solid #1e1e2e", borderTop: "2px solid #7c3aed", borderRadius: "50%", margin: "0 auto", animation: "spin 0.8s linear infinite" }} />
                </div>
              )}
              {hasMore && !loadingMore && (
                <div style={{ padding: 12, textAlign: "center" }}>
                  <span style={{ fontSize: 10, color: "#4b5563", fontFamily: "DM Mono, monospace" }}>
                    {founders.length} of {total} founders
                  </span>
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail panel */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          <DetailPanel founder={selected} onStatusChange={handleStatusChange} />
        </div>
      </div>

      {/* Footer */}
      <div style={{
        height: 28, borderTop: "1px solid #0e0e1a", background: "#05050c",
        display: "flex", alignItems: "center", padding: "0 16px", gap: 16
      }}>
        {["HN", "GitHub", "Product Hunt"].map((s, i) => (
          <span key={s} style={{ fontSize: 9, color: "#2d2d44", fontFamily: "DM Mono, monospace" }}>
            <span style={{ color: Object.values(SOURCE_COLORS)[i].accent }}>{s}</span> · {lastSync ? `Synced ${Math.round((Date.now() - lastSync) / 60000)}m ago` : "No sync yet"}
          </span>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 9, color: "#2d2d44", fontFamily: "DM Mono, monospace" }}>
          {founders.length}{total > founders.length ? ` of ${total}` : ""} founders · {loading ? "Loading..." : live ? "Turso" : "Not connected"}
        </span>
      </div>
    </div>
  );
}
