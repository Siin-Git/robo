import type { Metadata } from "next";
import "../styles/globals.css";
import { Providers } from "@/lib/query-client";

export const metadata: Metadata = {
  title: "Robo Advisor",
  description: "Forward-test paper trading dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
