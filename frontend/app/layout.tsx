import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PDF RAG | Ask your documents",
  description: "Grounded answers from your indexed PDFs.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
