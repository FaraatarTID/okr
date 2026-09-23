export default function ShellLoading() {
  return (
    <main className="page-shell">
      <section className="panel" role="status" aria-live="polite" style={{ padding: "1rem" }}>
        <p className="kicker">Atlas SPA</p>
        <p style={{ margin: "0.2rem 0 0", color: "var(--ink-soft)" }}>
          Loading workspace…
        </p>
      </section>
    </main>
  );
}
