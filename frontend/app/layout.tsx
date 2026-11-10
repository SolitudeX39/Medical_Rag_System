import type { Metadata } from "next";
import { IBM_Plex_Sans_Thai } from "next/font/google";
import AuthGate from "./AuthGate";
import "./globals.css";

const plexThai = IBM_Plex_Sans_Thai({
  weight: ["400", "500", "600", "700"],
  subsets: ["thai", "latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Medical Clinic AI",
  description: "คัดกรองผู้ป่วยเข้าแผนก และพอร์ทัลคนไข้สำหรับประวัติ ผลตรวจ และคำแนะนำ",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="th" className={`${plexThai.variable} h-full antialiased`} suppressHydrationWarning>
      <body className={`${plexThai.className} min-h-full`}>
        <AuthGate>{children}</AuthGate>
      </body>
    </html>
  );
}
