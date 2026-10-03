import { notFound } from "next/navigation";
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

  return <ProfileClient username={params.username} />;
}
