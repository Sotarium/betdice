import { notFound } from "next/navigation";
import { getUserByUsername, avatarUrl } from "@/lib/users";
import ProfileClient from "./ProfileClient";

export default function UserProfilePage({
  params,
}: {
  params: { username: string };
}) {
  // Skip reserved paths
  if (["users", "api", "_next", "favicon.ico"].includes(params.username)) {
    notFound();
  }

  const user = getUserByUsername(params.username);
  if (!user) notFound();

  const avatar = avatarUrl(user.discordId, user.avatar, 256);

  return <ProfileClient user={user} avatar={avatar} />;
}
