import Link from "next/link";
import { getAllUsers, avatarUrl } from "@/lib/users";

export default function UsersPage() {
  const users = getAllUsers();

  return (
    <div className="users-page">
      <h1 style={{ fontSize: 14, fontWeight: 500, color: "#717084", marginBottom: 28 }}>
        /users
      </h1>

      {users.length === 0 ? (
        <p style={{ color: "#454357", fontSize: 14 }}>No users with activity yet.</p>
      ) : (
        <div className="users-grid">
          {users.map((u) => (
            <Link key={u.discordId} href={`/${u.username}`} className="user-card">
              <div className="user-card-avatar">
                <img src={avatarUrl(u.discordId, u.avatar)} alt={u.username} />
              </div>
              <div className="user-card-name">{u.username}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
