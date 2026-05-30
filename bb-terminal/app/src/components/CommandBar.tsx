import { useEffect, useRef, useState } from "react";
import { parseCommand, FUNCTIONS } from "@/lib/functions";
import { useWorkspace } from "@/store/workspaceStore";
import { cn } from "@/lib/cn";

export function CommandBar() {
  const [input, setInput] = useState("");
  const [suggestIdx, setSuggestIdx] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { openTab, activeSymbol } = useWorkspace();

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Suggestions based on current token
  const tokens = input.trim().toUpperCase().split(/\s+/).filter(Boolean);
  const last = tokens[tokens.length - 1] ?? "";
  const suggestions =
    tokens.length === 0
      ? []
      : FUNCTIONS.filter((f) => f.code.startsWith(last)).slice(0, 5);

  function run() {
    const raw = input.trim();
    if (!raw) return;
    const parsed = parseCommand(raw, activeSymbol);
    if (!parsed) {
      setErr("UNKNOWN COMMAND — TRY: HELP");
      return;
    }
    openTab(parsed.code, parsed.symbol);
    setHistory((h) => [raw.toUpperCase(), ...h].slice(0, 20));
    setHistIdx(null);
    setInput("");
    setErr(null);
  }

  return (
    <div className="flex items-center h-10 bg-term-panel border-b border-term-border px-3 gap-4">
      <div className="flex items-center gap-2 select-none">
        <span className="w-1.5 h-1.5 bg-term-amber shadow-[0_0_6px_rgba(255,140,0,0.9)]" />
        <span className="text-term-amber font-bold tracking-[0.3em] text-[11px]">BBTERMINAL</span>
      </div>

      <div className="flex items-center gap-2 flex-1 relative">
        <span className="text-term-amberDim text-[11px] uppercase tracking-widest">CMD</span>
        <span className="text-term-amber">{">"}</span>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); setErr(null); setSuggestIdx(0); }}
          onKeyDown={(e) => {
            if (e.key === "Enter") run();
            else if (e.key === "ArrowUp") {
              e.preventDefault();
              if (history.length === 0) return;
              const next = histIdx == null ? 0 : Math.min(history.length - 1, histIdx + 1);
              setHistIdx(next); setInput(history[next]);
            } else if (e.key === "ArrowDown") {
              e.preventDefault();
              if (histIdx == null) return;
              const next = histIdx - 1;
              if (next < 0) { setHistIdx(null); setInput(""); }
              else { setHistIdx(next); setInput(history[next]); }
            } else if (e.key === "Tab" && suggestions.length > 0) {
              e.preventDefault();
              const rest = tokens.slice(0, -1);
              setInput([...rest, suggestions[suggestIdx].code].join(" ") + " ");
            }
          }}
          placeholder="TRY:  AAPL   |   TSLA INTEL   |   CC   |   WEI   |   MOV   |   HELP"
          spellCheck={false}
          autoCapitalize="characters"
          className="flex-1 bg-transparent uppercase text-term-amberBright placeholder:text-term-muted focus:outline-none text-[13px] tracking-wider"
        />
        <span className="text-term-amber text-[11px] font-bold px-2 py-0.5 border border-term-amberDim hover:bg-term-amberSubtle cursor-pointer select-none" onClick={run}>
          &lt;GO&gt;
        </span>

        {suggestions.length > 0 && (
          <div className="absolute top-full left-24 mt-1 z-50 bg-term-panel border border-term-border shadow-panel min-w-[360px]">
            {suggestions.map((f, i) => (
              <div
                key={f.code}
                onMouseEnter={() => setSuggestIdx(i)}
                onClick={() => { setInput(f.code + " "); inputRef.current?.focus(); }}
                className={cn(
                  "flex items-baseline gap-3 px-3 py-1.5 text-[12px] cursor-pointer",
                  i === suggestIdx && "bg-term-amberSubtle"
                )}
              >
                <span className="text-term-amber font-bold w-14">{f.code}</span>
                <span className="text-term-heading flex-1">{f.name}</span>
                <span className="sub-header">{f.group}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 text-[10px] uppercase tracking-[0.18em] text-term-muted">
        {err && <span className="text-term-red">{err}</span>}
        <span>CTX</span>
        <span className="text-term-amber font-bold">{activeSymbol ?? "—"}</span>
        <span className="text-term-muted">·</span>
        <span>↑↓ history   ⇥ autocomplete</span>
      </div>
    </div>
  );
}
