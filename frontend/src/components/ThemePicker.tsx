import { useEffect, useId, useRef, useState } from "react";
import { themes, useTheme } from "../lib/theme";

export function ThemePicker() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const current = themes.find(option => option.id === theme)!;

  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);

  function close() {
    setOpen(false);
    trigger.current?.focus();
  }

  return <div ref={root} className="relative" onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
  }}>
    <button ref={trigger} type="button" aria-label="Temayı değiştir" title={`Tema: ${current.name}`}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? menuId : undefined}
      className="flex h-9 w-9 items-center justify-center rounded-full border border-line bg-card-subtle text-primary transition-colors hover:border-primary/40"
      onClick={() => setOpen(value => !value)} onKeyDown={event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setOpen(true); }
      }}>
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 0 0 18Z" fill="currentColor" stroke="none" /></svg>
    </button>
    {open && <div id={menuId} role="menu" aria-label="Renk teması" className="absolute right-0 top-full z-50 mt-2 w-64 max-w-[calc(100vw-2rem)] space-y-1 rounded-2xl border border-line bg-card p-2 text-ink shadow-xl"
      onKeyDown={event => {
        if (event.key === "Escape") { event.preventDefault(); close(); }
        if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
          event.preventDefault();
          const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button[role="menuitemradio"]'));
          const index = items.indexOf(document.activeElement as HTMLButtonElement);
          const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
          items[next]?.focus();
        }
      }}>
      <p className="px-3 py-2 text-xs font-semibold text-muted">Renk teması</p>
      {themes.map(option => <button key={option.id} type="button" role="menuitemradio" aria-checked={theme === option.id}
        tabIndex={theme === option.id ? 0 : -1}
        className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-card-subtle ${theme === option.id ? "bg-card-subtle font-semibold" : ""}`}
        onClick={() => { setTheme(option.id); close(); }}>
        <span aria-hidden="true" className="flex h-7 w-7 shrink-0 overflow-hidden rounded-full border border-line" style={{ backgroundColor: option.background }}><span className="ml-auto w-1/2" style={{ backgroundColor: option.accent }} /></span>
        <span className="flex-1">{option.name}</span><span aria-hidden="true" className="text-primary">{theme === option.id ? "✓" : ""}</span>
      </button>)}
    </div>}
  </div>;
}
