import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { LoginGate } from "./components/LoginGate";

const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: "Stock Tracker Admin",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <LoginGate>{children}</LoginGate>
        <Toaster />
      </body>
    </html>
  );
}