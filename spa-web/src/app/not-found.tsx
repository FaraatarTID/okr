export default function NotFound() {
  return (
    <main className="page-shell">
      <section className="panel" style={{ padding: "1rem" }}>
        <p className="kicker">Atlas SPA</p>
        <h1 style={{ margin: "0.2rem 0" }}>Page not found</h1>
        <p style={{ color: "var(--ink-soft)" }}>That workspace route does not exist.</p>
        <a className="primary-button" href="/">
          Go to workspace
        </a>
      </section>
    </main>
  );
}
