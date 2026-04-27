import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import Sidebar from '@/components/Sidebar';
import { Outlet } from 'react-router-dom';

export default function DashboardLayout() {
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    return (
        <div className="flex h-screen bg-background">
            {/* Mobile Sidebar Overlay */}
            {isSidebarOpen && (
                <div
                    className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm lg:hidden"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            {/* Sidebar - Desktop & Mobile */}
            <div className={`
        fixed inset-y-0 left-0 z-50 w-64 transform bg-card border-r border-border transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:inset-auto
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
                <Sidebar onItemClick={() => setIsSidebarOpen(false)} />
            </div>

            {/* Main Content */}
            <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
                {/* Mobile Header */}
                <header className="flex items-center justify-between px-4 py-2 border-b border-border lg:hidden bg-card/50 backdrop-blur-lg sticky top-0 z-30">
                    <div className="flex items-center">
                        <span className="text-lg font-bold text-primary">SmartBooking</span>
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                    >
                        {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                    </Button>
                </header>

                {/* Content Area */}
                <main className="flex-1 overflow-y-auto p-4 md:p-8 bg-muted/20">
                    <div className="mx-auto max-w-6xl animate-fade-in">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
}
