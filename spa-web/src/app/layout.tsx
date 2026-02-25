import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OKR Atlas SPA",
  description: "SPA migration shell for Atlas workflows via spa-bff.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

