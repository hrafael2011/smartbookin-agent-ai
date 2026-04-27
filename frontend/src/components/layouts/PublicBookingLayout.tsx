import { Outlet } from 'react-router-dom';
import { Store } from 'lucide-react';

export default function PublicBookingLayout() {
    return (
        <div className="min-h-screen bg-muted/30 flex flex-col">
            {/* Minimal Header */}
            <header className="flex items-center justify-center h-16 bg-white/50 backdrop-blur-sm border-b border-border/40 sticky top-0 z-10 supports-[backdrop-filter]:bg-white/50">
                <div className="flex items-center space-x-2">
                    <div className="p-1.5 bg-primary/10 rounded-md">
                        <Store className="w-5 h-5 text-primary" />
                    </div>
                    <span className="text-lg font-bold text-foreground">SmartBooking</span>
                </div>
            </header>

            {/* Centered Content */}
            <main className="flex-1 flex flex-col items-center p-4 sm:p-8 animate-fade-in delay-100">
                <div className="w-full max-w-lg md:max-w-2xl lg:max-w-4xl">
                    <Outlet />
                </div>
            </main>

            {/* Simple Footer */}
            <footer className="py-6 text-center text-sm text-muted-foreground">
                <p>© {new Date().getFullYear()} SmartBooking Platform</p>
            </footer>
        </div>
    );
}
