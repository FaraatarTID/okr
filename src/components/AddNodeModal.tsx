import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import type { NodeType } from '../types';
import { useOKRStore } from '../store/useOKRStore';
import { cn } from '../utils/cn';

interface AddNodeModalProps {
    isOpen: boolean;
    onClose: () => void;
    parentId: string | null;
}

const getChildType = (parentType: NodeType | null): NodeType => {
    if (!parentType) return 'goal';

    const typeHierarchy: Record<NodeType, NodeType> = {
        goal: 'strategy',
        strategy: 'objective',
        objective: 'key_result',
        key_result: 'initiative',
        initiative: 'task',
        task: 'task',
    };

    return typeHierarchy[parentType];
};

const typeLabels: Record<NodeType, string> = {
    goal: '2-Year Goal',
    strategy: 'Strategy',
    objective: 'Quarterly Objective',
    key_result: 'Key Result',
    initiative: 'Initiative',
    task: 'Task',
};

export function AddNodeModal({ isOpen, onClose, parentId }: AddNodeModalProps) {
    const { nodes, addNode } = useOKRStore();
    const parentNode = parentId ? nodes[parentId] : null;
    const nodeType = getChildType(parentNode?.type || null);

    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');

    // Reset form when modal opens
    useEffect(() => {
        if (isOpen) {
            setTitle('');
            setDescription('');
        }
    }, [isOpen]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        if (!title.trim()) return;

        addNode(parentId, nodeType, {
            title: title.trim(),
            description: description.trim() || undefined,
        });

        setTitle('');
        setDescription('');
        onClose();
    };

    if (!isOpen) return null;

    return createPortal(
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
        }}>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    backgroundColor: 'rgba(0, 0, 0, 0.6)',
                    backdropFilter: 'blur(4px)'
                }}
            />

            {/* Modal Content */}
            <div className="relative z-10 node-card w-full mx-4" style={{ maxWidth: '28rem' }}>
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold gradient-text">
                        Add {typeLabels[nodeType]}
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg glass-hover text-slate-400 hover:text-slate-200"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                            Title *
                        </label>
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder={`Enter ${typeLabels[nodeType].toLowerCase()} title...`}
                            className="w-full px-4 py-3 rounded-lg glass border border-slate-600 focus:border-blue-500 focus:outline-none transition-colors"
                            style={{ color: 'white' }}
                            autoFocus
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                            Description
                        </label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Add details, context, or notes..."
                            rows={4}
                            className="w-full px-4 py-3 rounded-lg glass border border-slate-600 focus:border-blue-500 focus:outline-none transition-colors resize-none"
                            style={{ color: 'white' }}
                        />
                    </div>

                    {parentNode && (
                        <div className="text-sm text-slate-400">
                            Will be added under: <span className="text-slate-200 font-medium">{parentNode.title}</span>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-3 pt-4">
                        <button
                            type="submit"
                            disabled={!title.trim()}
                            className={cn(
                                'btn-primary flex-1',
                                !title.trim() && 'opacity-50 cursor-not-allowed'
                            )}
                        >
                            Create
                        </button>
                        <button
                            type="button"
                            onClick={onClose}
                            className="btn-secondary"
                        >
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>,
        document.body
    );
}
