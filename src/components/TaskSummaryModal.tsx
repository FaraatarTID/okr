import { useState, useEffect } from 'react';


import { X, Clock } from 'lucide-react';

interface TaskSummaryModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (summary: string) => void;
    onStopWithoutLog: () => void;
    sessionTime: number; // in minutes
}

export function TaskSummaryModal({ isOpen, onClose, onSubmit, onStopWithoutLog, sessionTime }: TaskSummaryModalProps) {
    const [summary, setSummary] = useState('');

    useEffect(() => {
        if (isOpen) {
            console.log('TaskSummaryModal: Mounted in DOM');
        }
    }, [isOpen]);

    const formatTime = (minutes: number) => {
        const hours = Math.floor(minutes / 60);
        const mins = Math.floor(minutes % 60);
        return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}`;
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!summary.trim()) return;
        onSubmit(summary.trim());
        setSummary('');
    };

    const handleStopWithoutLog = () => {
        setSummary('');
        onStopWithoutLog();
    };

    const handleResume = () => {
        setSummary('');
        onClose();
    };

    if (!isOpen) return null;

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={handleResume}
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9998]"
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.6)',
                    zIndex: 9998,
                    display: 'block',
                }}
            />

            {/* Modal */}
            <div
                className="fixed inset-0 flex items-center justify-center z-[9999] p-4"
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 9999,
                    padding: '1rem',
                }}
            >
                <div
                    className="node-card w-full max-w-lg bg-slate-900/90"
                    style={{
                        backgroundColor: 'rgb(15, 23, 42)',
                        maxWidth: '32rem',
                        width: '100%',
                        padding: '1.5rem',
                        borderRadius: '0.75rem',
                        border: '3px solid red',
                    }}
                >
                    {/* Header */}
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h2 className="text-2xl font-bold gradient-text">
                                Task Completed
                            </h2>
                            <div className="flex items-center gap-2 mt-2 text-slate-400">
                                <Clock className="w-4 h-4" />
                                <span>Session time: {formatTime(sessionTime)}</span>
                            </div>
                        </div>
                        <button
                            onClick={handleResume}
                            className="p-2 rounded-lg glass-hover text-slate-400 hover:text-slate-200"
                            title="Close modal"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Form */}
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                What did you accomplish? *
                            </label>
                            <textarea
                                value={summary}
                                onChange={(e) => setSummary(e.target.value)}
                                placeholder="Describe the task you completed..."
                                rows={4}
                                className="w-full px-4 py-3 rounded-lg glass border border-slate-600 focus:border-blue-500 focus:outline-none transition-colors resize-none"
                                style={{ color: 'white' }}
                                autoFocus
                            />
                        </div>

                        {/* Actions */}
                        <div className="flex gap-3 pt-4">
                            <button
                                type="submit"
                                disabled={!summary.trim()}
                                className="btn-primary flex-1"
                                style={{ color: 'white' }}
                            >
                                Save Task
                            </button>
                            <button
                                type="button"
                                onClick={handleStopWithoutLog}
                                className="btn-secondary"
                                style={{ color: 'white' }}
                            >
                                Stop Timer
                            </button>
                            <button
                                type="button"
                                onClick={handleResume}
                                className="btn-secondary"
                                style={{ color: 'white' }}
                            >
                                Resume
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </>
    );
}
