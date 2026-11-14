import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="page-header-action">{action}</div>}
    </header>
  );
}

export function PlainConclusion({
  children,
  note = "根据历史数据生成，仅帮助理解，不构成买卖建议。",
  label = "先说结论",
}: {
  children: ReactNode;
  note?: string | null;
  label?: string;
}) {
  return (
    <section className="plain-conclusion" aria-labelledby="plain-conclusion-title">
      <h2 id="plain-conclusion-title">{label}</h2>
      <div className="plain-conclusion-copy">{children}</div>
      {note && <p className="data-note">{note}</p>}
    </section>
  );
}

export type MetricTone = "up" | "down" | "neutral";

export function MetricStrip({
  items,
  label = "核心指标",
}: {
  items: { label: string; value: ReactNode; note?: string; tone?: MetricTone }[];
  label?: string;
}) {
  return (
    <section className="metric-strip-wrap" aria-label={label}>
      <div className="metric-strip">
        {items.map((item) => (
          <div className="metric-strip-item" key={item.label}>
            <span>{item.label}</span>
            <strong className={item.tone ? `text-${item.tone === "up" ? "positive" : item.tone === "down" ? "negative" : "muted-foreground"}` : undefined}>
              {item.value}
            </strong>
            {item.note && <small>{item.note}</small>}
          </div>
        ))}
      </div>
    </section>
  );
}

export function ResearchSection({
  id,
  title,
  description,
  action,
  children,
}: {
  id?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="research-section scroll-mt-32">
      <div className="research-section-heading">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {action && <div className="research-section-action">{action}</div>}
      </div>
      {children}
    </section>
  );
}

export function KeyValueList({
  items,
  columns = 1,
}: {
  items: { label: string; value: ReactNode; note?: string }[];
  columns?: 1 | 2;
}) {
  return (
    <dl className={`key-value-list ${columns === 2 ? "key-value-list-two" : ""}`}>
      {items.map((item) => (
        <div className="key-value-row" key={item.label}>
          <dt>
            {item.label}
            {item.note && <small>{item.note}</small>}
          </dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function UnderlineNav({
  items,
  label,
}: {
  items: { href: string; label: string }[];
  label: string;
}) {
  return (
    <nav className="underline-nav" aria-label={label}>
      {items.map((item) => (
        <a key={item.href} href={item.href}>
          {item.label}
        </a>
      ))}
    </nav>
  );
}

export function SegmentedControl<T extends string | number>({
  items,
  value,
  onChange,
  label,
  disabled = false,
}: {
  items: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div className="segmented-control" role="group" aria-label={label}>
      {items.map((item) => (
        <button
          type="button"
          key={item.value}
          aria-pressed={value === item.value}
          disabled={disabled}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function DataState({
  kind,
  title,
  description,
  action,
}: {
  kind: "loading" | "empty" | "error";
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="data-state" role={kind === "error" ? "alert" : "status"}>
      <strong>{title}</strong>
      {description && <p>{description}</p>}
      {action && <div>{action}</div>}
    </div>
  );
}

export function SourceNote({ children }: { children: ReactNode }) {
  return <p className="source-note">{children}</p>;
}

export function toneFor(value: number | null | undefined): MetricTone {
  if (value == null || !Number.isFinite(value)) return "neutral";
  return value >= 0 ? "up" : "down";
}
