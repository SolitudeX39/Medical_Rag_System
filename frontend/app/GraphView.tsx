"use client";

import { PointerEvent, useEffect, useId, useMemo, useRef, useState } from "react";

export type GraphNode = {
  name: string;
  thai?: string;
  kind?: string;
  definition?: string;
};

export type GraphLink = {
  from: string;
  to: string;
  type?: string;
  label?: string;
  detail?: string;
};

export type GraphOverview = {
  nodes: GraphNode[];
  links: GraphLink[];
  skipped?: boolean;
};

type SimNode = GraphNode & {
  x: number;
  y: number;
  vx: number;
  vy: number;
};

type Point = { x: number; y: number };

const KIND_COLORS: Record<string, string> = {
  disease: "#ff4d6d",
  concept: "#3ee0ff",
  prefix: "#c084fc",
  suffix: "#a78bfa",
  symptom: "#fbbf24",
  sign: "#fb923c",
  procedure: "#34d399",
  abbreviation: "#818cf8",
};

function kindColor(kind?: string) {
  return KIND_COLORS[kind || ""] || "#8a6a4a";
}

function kindLabel(kind?: string) {
  const labels: Record<string, string> = {
    disease: "โรค",
    concept: "แนวคิด",
    prefix: "อุปสรรค",
    suffix: "ปัจจัย",
    symptom: "อาการ",
    sign: "อาการแสดง",
    procedure: "หัตถการ",
    abbreviation: "คำย่อ",
  };
  return labels[kind || ""] || kind || "ศัพท์";
}

function shortName(name: string) {
  return name.length > 18 ? `${name.slice(0, 16)}…` : name;
}

function runLayout(nodes: GraphNode[], links: GraphLink[], width: number, height: number): SimNode[] {
  const cx = width / 2;
  const cy = height / 2;
  const sim: SimNode[] = nodes.map((node, index) => {
    const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
    const radius = Math.min(width, height) * 0.34;
    return {
      ...node,
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: 0,
      vy: 0,
    };
  });
  const byName = new Map(sim.map((node) => [node.name, node]));
  const edges = links
    .map((link) => {
      const a = byName.get(link.from);
      const b = byName.get(link.to);
      return a && b && a !== b ? { a, b } : null;
    })
    .filter((item): item is { a: SimNode; b: SimNode } => item !== null);

  const n = Math.max(sim.length, 1);
  const repulsion = 1800 + n * 28;
  const rest = Math.max(70, Math.min(130, 520 / Math.sqrt(n)));

  for (let step = 0; step < 160; step += 1) {
    for (let i = 0; i < sim.length; i += 1) {
      for (let j = i + 1; j < sim.length; j += 1) {
        const a = sim[i];
        const b = sim[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let dist = Math.hypot(dx, dy) || 0.01;
        const force = repulsion / (dist * dist);
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        a.vx += dx;
        a.vy += dy;
        b.vx -= dx;
        b.vy -= dy;
      }
    }
    for (const { a, b } of edges) {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const pull = (dist - rest) * 0.035;
      const fx = (dx / dist) * pull;
      const fy = (dy / dist) * pull;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }
    for (const node of sim) {
      node.vx += (cx - node.x) * 0.012;
      node.vy += (cy - node.y) * 0.012;
      node.vx *= 0.78;
      node.vy *= 0.78;
      node.x += node.vx;
      node.y += node.vy;
      node.x = Math.max(36, Math.min(width - 36, node.x));
      node.y = Math.max(28, Math.min(height - 28, node.y));
    }
  }
  return sim;
}

export function factsToGraph(
  facts: Array<{
    name: string;
    thai?: string;
    kind?: string;
    definition?: string;
    relation?: string;
    related_name?: string;
    related_thai?: string;
    related_definition?: string;
    relation_detail?: string;
  }>,
): GraphOverview {
  const nodes = new Map<string, GraphNode>();
  const links: GraphLink[] = [];
  for (const fact of facts) {
    nodes.set(fact.name, {
      name: fact.name,
      thai: fact.thai,
      kind: fact.kind,
      definition: fact.definition,
    });
    if (!fact.related_name) continue;
    if (!nodes.has(fact.related_name)) {
      nodes.set(fact.related_name, {
        name: fact.related_name,
        thai: fact.related_thai,
        definition: fact.related_definition,
      });
    }
    const match = fact.relation?.match(/-\[(.+)\]->/);
    const outgoing = !fact.relation || fact.relation.startsWith(fact.name);
    links.push({
      from: outgoing ? fact.name : fact.related_name,
      to: outgoing ? fact.related_name : fact.name,
      label: match?.[1] || "เกี่ยวข้อง",
      detail: fact.relation_detail || "",
    });
  }
  return { nodes: [...nodes.values()], links };
}

export default function GraphView({
  graph,
  compact = false,
  highlight = [],
}: {
  graph: GraphOverview;
  compact?: boolean;
  highlight?: string[];
}) {
  const graphId = useMemo(() => {
    const nodeKey = (graph.nodes ?? [])
      .filter((node) => node?.name)
      .map((node) => node.name)
      .join("|");
    const linkKey = (graph.links ?? [])
      .filter((link) => link?.from && link?.to)
      .map((link) => `${link.from}->${link.to}:${link.label || link.type || ""}`)
      .join("|");
    return `${nodeKey}::${linkKey}`;
  }, [graph.nodes, graph.links]);

  const nodes = useMemo(() => {
    const seen = new Set<string>();
    return (graph.nodes ?? []).filter((node) => {
      if (!node?.name || seen.has(node.name)) return false;
      seen.add(node.name);
      return true;
    });
  }, [graphId]);

  const links = useMemo(
    () => (graph.links ?? []).filter((link) => link?.from && link?.to && link.from !== link.to),
    [graphId],
  );

  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 640, height: compact ? 260 : 520 });
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const dragRef = useRef<{ name: string; dx: number; dy: number } | null>(null);
  const graphIdRef = useRef(graphId);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => {
      const next = {
        width: Math.max(320, el.clientWidth),
        height: Math.max(compact ? 220 : 420, el.clientHeight),
      };
      setSize((prev) =>
        prev.width === next.width && prev.height === next.height ? prev : next,
      );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, [compact]);

  useEffect(() => {
    const laid = runLayout(nodes, links, size.width, size.height);
    setPositions(Object.fromEntries(laid.map((node) => [node.name, { x: node.x, y: node.y }])));
    if (graphIdRef.current !== graphId) {
      graphIdRef.current = graphId;
      setSelected(null);
    }
  }, [graphId, size.width, size.height, nodes, links]);

  const degree = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of nodes) counts.set(node.name, 0);
    for (const link of links) {
      counts.set(link.from, (counts.get(link.from) || 0) + 1);
      counts.set(link.to, (counts.get(link.to) || 0) + 1);
    }
    return counts;
  }, [nodes, links]);

  const neighbors = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const node of nodes) map.set(node.name, new Set());
    for (const link of links) {
      map.get(link.from)?.add(link.to);
      map.get(link.to)?.add(link.from);
    }
    return map;
  }, [nodes, links]);

  const selectedNode = nodes.find((node) => node.name === selected);
  const selectedLinks = useMemo(() => {
    if (!selected) return [];
    const byName = new Map(nodes.map((node) => [node.name, node]));
    return links
      .filter((link) => link.from === selected || link.to === selected)
      .map((link) => {
        const outgoing = link.from === selected;
        const otherName = outgoing ? link.to : link.from;
        const other = byName.get(otherName);
        return {
          direction: outgoing ? "ออก" : "เข้า",
          otherName,
          otherThai: other?.thai || "",
          otherDefinition: other?.definition || "",
          label: link.label || link.type || "เกี่ยวข้อง",
          detail: link.detail || "",
        };
      });
  }, [links, nodes, selected]);
  const active = selected || hover;
  const focusSet = useMemo(() => {
    if (!active) return new Set(highlight);
    return new Set([active, ...(neighbors.get(active) || [])]);
  }, [active, neighbors, highlight]);

  function pointOf(name: string): Point {
    return positions[name] || { x: size.width / 2, y: size.height / 2 };
  }

  function svgPoint(event: PointerEvent<Element>): Point {
    const svg = wrapRef.current?.querySelector("svg");
    if (svg) {
      const point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const mapped = point.matrixTransform(svg.getScreenCTM()?.inverse());
      return { x: mapped.x, y: mapped.y };
    }
    const rect = wrapRef.current?.getBoundingClientRect();
    return { x: event.clientX - (rect?.left || 0), y: event.clientY - (rect?.top || 0) };
  }

  function onPointerDown(event: PointerEvent<Element>, name: string) {
    event.preventDefault();
    event.stopPropagation();
    const cursor = svgPoint(event);
    const point = pointOf(name);
    dragRef.current = {
      name,
      dx: cursor.x - point.x,
      dy: cursor.y - point.y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    setSelected(name);
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!dragRef.current) return;
    const cursor = svgPoint(event);
    const x = Math.max(28, Math.min(size.width - 28, cursor.x - dragRef.current.dx));
    const y = Math.max(22, Math.min(size.height - 22, cursor.y - dragRef.current.dy));
    const name = dragRef.current.name;
    setPositions((prev) => ({ ...prev, [name]: { x, y } }));
  }

  function onPointerUp() {
    dragRef.current = null;
  }

  const kinds = [...new Set(nodes.map((node) => node.kind).filter(Boolean))] as string[];
  const uid = useId().replace(/:/g, "");
  const glowId = `neo-glow-${uid}`;
  const gridId = `neo-grid-${uid}`;
  const arrowId = `neo-arrow-${uid}`;
  const arrowHotId = `neo-arrow-hot-${uid}`;

  return (
    <div className="flex h-full min-h-0 flex-col text-[#d7e6ff]">
      {!compact && (
        <div className="mb-3 flex items-center gap-3">
          <input
            value={query}
            onChange={(event) => {
              const value = event.target.value;
              setQuery(value);
              const match = nodes.find((node) => {
                const q = value.trim().toLowerCase();
                return (
                  node.name.toLowerCase() === q ||
                  node.name.toLowerCase().includes(q) ||
                  (node.thai || "").toLowerCase().includes(q)
                );
              });
              if (value.trim() && match) setSelected(match.name);
            }}
            placeholder="ค้นหาโหนด เช่น Hypertension"
            className="w-full rounded-xl border border-cyan-300/20 bg-[#0b1220]/80 px-3 py-2 text-sm text-cyan-50 outline-none placeholder:text-slate-500 focus:border-cyan-300/70"
          />
        </div>
      )}
      <div
        ref={wrapRef}
        className={`relative min-h-0 overflow-hidden rounded-2xl border border-cyan-300/15 bg-[#050814] shadow-[inset_0_0_80px_rgba(34,211,238,0.08)] ${
          compact ? "h-64" : "flex-1"
        }`}
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(56,189,248,0.16),transparent_36%),radial-gradient(circle_at_80%_90%,rgba(168,85,247,0.14),transparent_40%)]" />
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${size.width} ${size.height}`}
          className="relative z-[1] block h-full w-full touch-none"
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
          onClick={(event) => {
            if (event.target === event.currentTarget) setSelected(null);
          }}
        >
          <defs>
            <pattern id={gridId} width="28" height="28" patternUnits="userSpaceOnUse">
              <circle cx="1.2" cy="1.2" r="1" fill="rgba(148,163,184,0.18)" />
            </pattern>
            <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3.2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <marker id={arrowId} markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">
              <path d="M0,1 L8,4 L0,7 Z" fill="#67e8f9" />
            </marker>
            <marker id={arrowHotId} markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto">
              <path d="M0,1 L8,4 L0,7 Z" fill="#f0abfc" />
            </marker>
          </defs>
          <rect width={size.width} height={size.height} fill={`url(#${gridId})`} />
          {links.map((link, index) => {
            const a = pointOf(link.from);
            const b = pointOf(link.to);
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const dist = Math.hypot(dx, dy) || 1;
            const start = {
              x: a.x + (dx / dist) * 22,
              y: a.y + (dy / dist) * 22,
            };
            const end = {
              x: b.x - (dx / dist) * 22,
              y: b.y - (dy / dist) * 22,
            };
            const hot =
              !active ||
              link.from === active ||
              link.to === active ||
              (highlight.includes(link.from) && highlight.includes(link.to));
            const live = Boolean(hot && active);
            return (
              <g key={`${link.from}-${link.to}-${index}`} opacity={hot ? 1 : 0.12}>
                <line
                  x1={start.x}
                  y1={start.y}
                  x2={end.x}
                  y2={end.y}
                  stroke={live ? "#f0abfc" : "#22d3ee"}
                  strokeWidth={live ? 2.2 : 1.1}
                  strokeDasharray={live ? "6 6" : "2 8"}
                  markerEnd={live ? `url(#${arrowHotId})` : `url(#${arrowId})`}
                  className={`pointer-events-none ${live ? "neo-edge-hot" : ""}`}
                  filter={`url(#${glowId})`}
                />
                {hot && (active || compact) && (
                  <text
                    x={(start.x + end.x) / 2}
                    y={(start.y + end.y) / 2 - 8}
                    textAnchor="middle"
                    className="pointer-events-none fill-cyan-100"
                    fontSize={compact ? 9 : 10}
                  >
                    {link.label || link.type}
                  </text>
                )}
              </g>
            );
          })}
          {nodes.map((node) => {
            const point = pointOf(node.name);
            const hot = !active || focusSet.has(node.name);
            const isSel = selected === node.name;
            const color = kindColor(node.kind);
            const r = 8 + Math.min(6, (degree.get(node.name) || 0) * 1.4);
            return (
              <g
                key={node.name}
                transform={`translate(${point.x}, ${point.y})`}
                opacity={hot ? 1 : 0.16}
                className="cursor-pointer"
                onMouseEnter={() => setHover(node.name)}
                onMouseLeave={() => setHover(null)}
                onPointerDown={(event) => onPointerDown(event, node.name)}
                onClick={(event) => {
                  event.stopPropagation();
                  setSelected(node.name);
                }}
              >
                <rect x={-40} y={-r - 12} width={80} height={r + 32} fill="transparent" />
                {isSel && (
                  <circle r={r + 10} fill="none" stroke={color} strokeWidth="1.2" className="neo-ring" />
                )}
                <circle r={r + 5} fill={color} opacity="0.16" filter={`url(#${glowId})`} />
                <circle
                  r={isSel ? r + 2 : r}
                  fill="#061018"
                  stroke={color}
                  strokeWidth={isSel ? 2.6 : 1.8}
                  filter={`url(#${glowId})`}
                />
                <circle r={3.2} fill={color} />
                <text
                  y={r + 16}
                  textAnchor="middle"
                  fill={isSel ? "#ffffff" : "#c4d4f0"}
                  fontSize={compact ? 10 : 11}
                  fontWeight={isSel ? 700 : 500}
                >
                  {shortName(node.name)}
                </text>
              </g>
            );
          })}
        </svg>
        {!compact && (
          <p className="pointer-events-none absolute left-3 top-3 text-[10px] tracking-[0.22em] text-cyan-200/70">
            GRAPH LIVE · ลากหรือกดโหนด
          </p>
        )}
        {!compact && selectedNode && (
          <div className="absolute inset-x-3 bottom-3 max-h-[46%] overflow-y-auto rounded-2xl border border-cyan-200/20 bg-[#070d1a]/94 px-4 py-3 shadow-[0_0_40px_rgba(34,211,238,0.12)] backdrop-blur">
            <p className="text-[10px] tracking-[0.2em] text-cyan-300/80">{kindLabel(selectedNode.kind)}</p>
            <p className="mt-1 font-semibold text-white">{selectedNode.name}</p>
            {selectedNode.thai && <p className="text-sm text-slate-300">{selectedNode.thai}</p>}
            {selectedNode.definition && (
              <p className="mt-2 text-sm leading-relaxed text-slate-200">{selectedNode.definition}</p>
            )}
            {selectedLinks.length > 0 && (
              <div className="mt-3 border-t border-white/10 pt-2">
                <p className="text-[10px] tracking-[0.18em] text-cyan-300/70">ความสัมพันธ์</p>
                <ul className="mt-2 space-y-2">
                  {selectedLinks.map((link, index) => (
                    <li key={`${link.direction}-${link.otherName}-${link.label}-${index}`} className="text-sm leading-relaxed text-slate-300">
                      <p>
                        <span className="text-cyan-200">{link.direction}</span>
                        {" · "}
                        {link.label}
                        {" → "}
                        <span className="text-white">{link.otherName}</span>
                        {link.otherThai ? ` (${link.otherThai})` : ""}
                      </p>
                      {link.detail && <p className="mt-0.5 text-slate-400">{link.detail}</p>}
                      {link.otherDefinition && (
                        <p className="mt-0.5 text-slate-500">{link.otherDefinition}</p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {!compact && (
        <div className="mt-3 flex flex-wrap gap-2">
          {kinds.map((kind) => (
            <span
              key={kind}
              className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-slate-300"
            >
              <span className="h-2 w-2 rounded-full" style={{ background: kindColor(kind), boxShadow: `0 0 8px ${kindColor(kind)}` }} />
              {kindLabel(kind)}
            </span>
          ))}
        </div>
      )}
      {!compact && !selectedNode && (
        <p className="mt-2 text-[11px] tracking-wide text-slate-400">
          {nodes.length} NODES · {links.length} LINKS
        </p>
      )}
    </div>
  );
}
