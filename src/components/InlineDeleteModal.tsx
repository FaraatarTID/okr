import { AlertTriangle, X } from 'lucide-react';
import { cn } from '../utils/cn';

interface InlineDeleteModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    nodeTitle: string;
    hasChildren: boolean;
}

export function InlineDeleteModal({
    isOpen,
    onClose,
    onConfirm,
    nodeTitle,
    hasChildren,
}: InlineDeleteModalProps) {
    if (!isOpen) return null;

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            zIndex: 99999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem'
        }}>
            <div
                onClick={onClose}
                style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)' }}
            />

            <div
                className="relative w-full max-w-md overflow-hidden rounded-2xl shadow-2xl"
                style={{
                    backgroundColor: '#0f172a',
                    borderColor: '#1e293b',
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    zIndex: 100000,
                    maxWidth: '450px',
                    width: '90%',
                    margin: '0 auto'
                }}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-slate-800" style={{ borderBottomColor: '#1e293b' }}>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <AlertTriangle className="w-6 h-6 text-red-500" />
                        Confirm Deletion
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
                        title="Close"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6">
                    <p className="text-slate-300 mb-4">
                        Are you sure you want to delete <span className="font-semibold text-white">"{nodeTitle}"</span>?
                    </p>

                    {hasChildren && (
                        <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-200 text-sm">
                            <p className="font-semibold mb-1">Warning: This node has children.</p>
                            <p>Deleting this node will also delete all its sub-goals, objectives, and initiatives. This action cannot be undone.</p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-800 bg-slate-900/50" style={{ borderTopColor: '#1e293b', backgroundColor: 'rgba(15, 23, 42, 0.5)' }}>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-lg text-slate-300 hover:text-white hover:bg-white/5 transition-colors font-medium"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={() => {
                            onConfirm();
                            onClose();
                        }}
                        className={cn(
                            "px-4 py-2 rounded-lg font-medium text-white shadow-lg transition-all",
                            "bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500"
                        )}
                    >
                        Delete Forever
                    </button>
                </div>
            </div>
        </div>
    );
}
