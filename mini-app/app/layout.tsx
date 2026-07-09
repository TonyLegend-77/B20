import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "B20 Pulse",
  description: "Live on-chain token tracking and risk scoring on Base",
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
