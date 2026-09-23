"use client";

type ShellErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

/** Catches page/child-segment failures; the parent `app/error.tsx` catches this layout. */
export default function ShellError({ error, reset }: ShellErrorProps) {
  return (
    <main className="page-shell">
      <section className="panel" role="alert" style={{ padding: "1rem" }}>
        <p className="kicker">Atlas SPA</p>
        <h1 style={{ margin: "0.2rem 0" }}>This workspace view could not load</h1>
        <p style={{ color: "var(--ink-soft)" }}>
          Try the current route again.
          {error.digest ? <span> Reference: {error.digest}</span> : null}
        </p>
        <button className="primary-button" type="button" onClick={reset}>
          Try again
        </button>
      </section>
    </main>
  );
}
