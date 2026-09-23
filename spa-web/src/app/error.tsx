"use client";

type AppErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

/** Parent boundary: this wraps route-group layouts, including `(shell)/layout.tsx`. */
export default function AppError({ error, reset }: AppErrorProps) {
  return (
    <main className="page-shell">
      <section className="panel" role="alert" style={{ padding: "1rem" }}>
        <p className="kicker">Atlas SPA</p>
        <h1 style={{ margin: "0.2rem 0" }}>Workspace could not load</h1>
        <p style={{ color: "var(--ink-soft)" }}>
          Something interrupted this page. Try loading it again.
          {error.digest ? <span> Reference: {error.digest}</span> : null}
        </p>
        <button className="primary-button" type="button" onClick={reset}>
          Try again
        </button>
      </section>
    </main>
  );
}
