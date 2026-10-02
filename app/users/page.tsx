import Link from "next/link";
import { getAllUsers } from "@/lib/users";

export default function UsersPage() {
  const users = getAllUsers();

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#0d0e12",
        color: "#e4e4e7",
        fontFamily: "system-ui, -apple-system, sans-serif",
        padding: "40px 24px",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, marginBottom: 28, color: "#a1a1aa" }}>
          /users
        </h1>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 16,
          }}
        >
          {users.map((u) => (
            <Link
              key={u.username}
              href={`/${u.username}`}
              style={{
                background: "#16171d",
                borderRadius: 12,
                padding: "20px 16px",
                textAlign: "center",
                textDecoration: "none",
                color: "#e4e4e7",
                border: "1px solid #1f2028",
                transition: "border-color 0.15s",
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: "50%",
                  background: "#1f2028",
                  margin: "0 auto 12px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 24,
                }}
              >
                👁
              </div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{u.username}</div>
            </Link>
          ))}

          {users.length === 0 && (
            <p style={{ color: "#71717a", gridColumn: "1 / -1" }}>
              No users with activity yet.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
