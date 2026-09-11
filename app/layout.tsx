import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Kernel Inbox', description: 'Your local Linux kernel mailing list reader.' };
export default function RootLayout({children}: {children: React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
