import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Betdice",
  description: "Provably fair dice games",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}