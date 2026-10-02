export default function Home() {
  return (
    <main style={{
      minHeight: "100vh",
      background: "#1e1f22",
      color: "#dbdee1",
      fontFamily: "system-ui, sans-serif",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      textAlign: "center",
    }}>
      <div>
        <h1 style={{ fontSize: 22, marginBottom: 8 }}>Betdice API</h1>
        <p style={{ color: "#949ba4", fontSize: 14, maxWidth: 360 }}>
          Provably fair seed generation &amp; Plisio webhooks for the Discord bot.
          No games are hosted on this site.
        </p>
        <p style={{ color: "#949ba4", fontSize: 13, marginTop: 16 }}>
          Endpoints: <code>/api/fair/seed</code> · <code>/api/fair/roll</code> · <code>/api/plisio/callback</code>
        </p>
      </div>
    </main>
  );
}