import type {Metadata} from "next";
import "./globals.css";
import {Nav} from "@/components/shared/nav";
import {I18nProvider} from "@/lib/i18n";

export const metadata: Metadata = {
  title: "smsbridge",
  description: "Compliant SMS verification API for developers and QA teams"
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("smsbridge-theme");var d=t?t==="dark":window.matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d);}catch(e){}`
          }}
        />
        <I18nProvider>
          <Nav>{children}</Nav>
        </I18nProvider>
      </body>
    </html>
  );
}
