import { Plus, Clock, Target, Pause, Download, Upload } from 'lucide-react';
import { useTimer } from '../hooks/useTimer';
import { useCurrentTime } from '../hooks/useTimer';
import { formatTime } from '../utils/formatTime';
import { useOKRStore } from '../store/useOKRStore';

interface LayoutProps {
    children: React.ReactNode;
    onAddRoot: () => void;
    onExport: () => void;
    onImport: (file: File) => void;
}

export function Layout({ children, onAddRoot, onExport, onImport }: LayoutProps) {
    const activeTimer = useTimer();
    const currentTime = useCurrentTime(activeTimer?.id || '');
    const setActiveTaskModalNodeId = useOKRStore(state => state.setActiveTaskModalNodeId);

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            onImport(file);
        }
        // Reset value to allow selecting same file again
        event.target.value = '';
    };

    return (
        <div className="min-h-screen">
            {/* Header */}
            <header className="sticky top-0 z-30 glass border-b border-white/10">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 shadow-lg">
                                <Target className="w-6 h-6 text-white" />
                            </div>
                            <div>
                                <h1 className="text-2xl font-bold gradient-text">
                                    OKR Tracker
                                </h1>
                                <p className="text-sm text-slate-400">
                                    Personal Goal Management System
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            <button
                                onClick={onExport}
                                className="btn-secondary flex items-center gap-2"
                                title="Export Backup"
                            >
                                <Download className="w-5 h-5" />
                                <span className="hidden sm:inline">Export</span>
                            </button>
                            
                            <label className="btn-secondary flex items-center gap-2 cursor-pointer" title="Import Backup">
                                <Upload className="w-5 h-5" />
                                <span className="hidden sm:inline">Import</span>
                                <input
                                    type="file"
                                    accept=".json"
                                    onChange={handleFileChange}
                                    className="hidden"
                                />
                            </label>

                            <button
                                onClick={onAddRoot}
                                className="btn-primary flex items-center gap-2"
                            >
                                <Plus className="w-5 h-5" />
                                <span className="hidden sm:inline">Add Goal</span>
                            </button>
                        </div>
                    </div>
                </div>
            </header>

            {/* Active Timer Indicator */}
            {activeTimer && (
                <div className="fixed top-20 left-1/2 -translate-x-1/2 z-40">
                        <div className="node-card bg-gradient-to-br from-green-500/20 to-emerald-500/20 border-green-500/30 min-w-[280px]">
                            <div className="flex items-start gap-3">
                                <div className="relative mt-1">
                                    <Clock className="w-5 h-5 text-green-400" />
                                    <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full animate-ping" />
                                    <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full" />
                                </div>
                                <div className="flex-1">
                                    <div className="text-xs text-green-400 font-medium mb-1">
                                        Timer Running
                                    </div>
                                    <div className="text-sm font-semibold text-white truncate mb-2">
                                        {activeTimer.title}
                                    </div>

                                    {/* Task Time (current session) */}
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-xs text-slate-400">Task Time:</span>
                                        <span className="text-sm font-bold text-green-400">
                                            {formatTime(currentTime)}
                                        </span>
                                    </div>

                                    {/* Total Time (all children) */}
                                    <div className="flex justify-between items-center">
                                        <span className="text-xs text-slate-400">Total Time:</span>
                                        <span className="text-xs font-semibold text-slate-300">
                                            {formatTime((activeTimer.timeSpent || 0) + currentTime)}
                                        </span>
                                    </div>
                                </div>

                                {/* Pause Button */}
                                <button
                                    onClick={() => setActiveTaskModalNodeId(activeTimer.id)}
                                    className="p-2 rounded-lg bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 hover:text-yellow-300 transition-colors"
                                    title="Pause timer"
                                >
                                    <Pause className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    </div>
                )}

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {children}
            </main>

            {/* Footer */}
            <footer className="mt-16 border-t border-white/10 glass">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    <div className="text-center text-sm text-slate-400">
                        <p>Track your goals, strategies, objectives, key results, and initiatives</p>
                        <p className="mt-1">Built with React, TypeScript, Zustand, and Tailwind CSS</p>
                    </div>
                </div>
            </footer>
        </div>
    );
}
