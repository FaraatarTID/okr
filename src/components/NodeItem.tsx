import {
    Target,
    Zap,
    TrendingUp,
    CheckCircle2,
    Lightbulb,
    ChevronDown,
    ChevronRight,
    Clock,
    Play,
    Pause,
    Plus,
    Trash2,
    Star,
    ListTodo
} from 'lucide-react';
import { cn } from '../utils/cn';
import type { Node } from '../types';
import { useOKRStore } from '../store/useOKRStore';
import { formatTime } from '../utils/formatTime';
import { useCurrentTime } from '../hooks/useTimer';
import { useState } from 'react';

const nodeConfig = {
    goal: { icon: Target, label: 'Goal', color: 'from-pink-500 to-rose-500' },
    strategy: { icon: Zap, label: 'Strategy', color: 'from-purple-500 to-indigo-500' },
    objective: { icon: TrendingUp, label: 'Objective', color: 'from-blue-500 to-cyan-500' },
    key_result: { icon: CheckCircle2, label: 'Key Result', color: 'from-green-500 to-emerald-500' },
    initiative: { icon: Lightbulb, label: 'Initiative', color: 'from-yellow-500 to-orange-500' },
    task: { icon: ListTodo, label: 'Task', color: 'from-slate-500 to-gray-500' },
};

interface NodeItemProps {
    node: Node;
    onAddChild: (parentId: string) => void;
    onDelete: (node: Node) => void;
}

export function NodeItem({ node, onAddChild, onDelete }: NodeItemProps) {
    const [isEditingTitle, setIsEditingTitle] = useState(false);
    const [editTitle, setEditTitle] = useState(node.title);
    const [isEditingDescription, setIsEditingDescription] = useState(false);
    const [editDescription, setEditDescription] = useState(node.description || '');

    const updateNode = useOKRStore(state => state.updateNode);
    const toggleExpand = useOKRStore(state => state.toggleExpand);
    const startTimer = useOKRStore(state => state.startTimer);
    const setActiveTaskModalNodeId = useOKRStore(state => state.setActiveTaskModalNodeId);
    const nodes = useOKRStore(state => state.nodes);

    const config = nodeConfig[node.type];
    const Icon = config.icon;
    const hasChildren = node.children.length > 0;
    const isTimerRunning = !!node.timerStartedAt;
    const currentTime = useCurrentTime(node.id);

    const handleTitleSave = () => {
        updateNode(node.id, { title: editTitle.trim() || 'Untitled' });
        setIsEditingTitle(false);
    };

    const handleDescriptionSave = () => {
        updateNode(node.id, { description: editDescription.trim() || undefined });
        setIsEditingDescription(false);
    };

    const handleTimerToggle = () => {
        if (isTimerRunning) {
            setActiveTaskModalNodeId(node.id);
        } else {
            startTimer(node.id);
        }
    };

    return (
        <div className="group">
            <div className={cn(
                'node-card glass-hover relative overflow-hidden',
                node.type === 'goal' && 'border-l-4 border-pink-500',
                node.type === 'strategy' && 'border-l-4 border-purple-500',
                node.type === 'objective' && 'border-l-4 border-blue-500',
                node.type === 'key_result' && 'border-l-4 border-green-500',
                node.type === 'initiative' && 'border-l-4 border-yellow-500',
            )}>
                {/* Background gradient */}
                <div className={cn(
                    'absolute inset-0 opacity-5 bg-gradient-to-br',
                    config.color
                )} />

                <div className="relative">
                    {/* Header */}
                    <div className="flex items-start gap-3">
                        {/* Expand/Collapse */}
                        {hasChildren && (
                            <button
                                onClick={() => toggleExpand(node.id)}
                                className="mt-1 text-slate-400 hover:text-slate-200 transition-colors"
                            >
                                {node.isExpanded ? (
                                    <ChevronDown className="w-5 h-5" />
                                ) : (
                                    <ChevronRight className="w-5 h-5" />
                                )}
                            </button>
                        )}

                        {/* Icon */}
                        <div className={cn(
                            'mt-1 p-2 rounded-lg bg-gradient-to-br',
                            config.color,
                            'shadow-lg'
                        )}>
                            <Icon className="w-5 h-5 text-white" />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                            {/* Type label */}
                            <div className="text-xs text-slate-400 mb-1">{config.label}</div>

                            {/* Title */}
                            {isEditingTitle ? (
                                <input
                                    type="text"
                                    value={editTitle}
                                    onChange={(e) => setEditTitle(e.target.value)}
                                    onBlur={handleTitleSave}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') handleTitleSave();
                                        if (e.key === 'Escape') {
                                            setEditTitle(node.title);
                                            setIsEditingTitle(false);
                                        }
                                    }}
                                    className="w-full bg-slate-800/50 border border-slate-600 rounded px-2 py-1 text-lg font-semibold focus:outline-none focus:border-blue-500"
                                    autoFocus
                                />
                            ) : (
                                <h3
                                    className={cn(
                                        'font-semibold cursor-pointer hover:text-blue-400 transition-colors',
                                        node.type === 'goal' && 'text-2xl',
                                        node.type === 'strategy' && 'text-xl',
                                        node.type === 'objective' && 'text-lg',
                                        node.type === 'key_result' && 'text-base',
                                        node.type === 'initiative' && 'text-base',
                                    )}
                                    onClick={() => setIsEditingTitle(true)}
                                >
                                    {node.title}
                                </h3>
                            )}

                            {/* Description */}
                            {isEditingDescription ? (
                                <textarea
                                    value={editDescription}
                                    onChange={(e) => setEditDescription(e.target.value)}
                                    onBlur={handleDescriptionSave}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Escape') {
                                            setEditDescription(node.description || '');
                                            setIsEditingDescription(false);
                                        }
                                        // Ctrl+Enter or Cmd+Enter to save
                                        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                                            e.preventDefault();
                                            handleDescriptionSave();
                                        }
                                        // Allow Enter for new lines without any modifier
                                    }}
                                    className="w-full bg-slate-800/50 border border-slate-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-blue-500 resize-none mt-1"
                                    rows={3}
                                    autoFocus
                                    placeholder="Add description... (Ctrl+Enter to save, Esc to cancel)"
                                />
                            ) : (
                                <p
                                    className="text-sm text-slate-400 mt-1 cursor-pointer hover:text-slate-300 transition-colors"
                                    onClick={() => {
                                        setEditDescription(node.description || '');
                                        setIsEditingDescription(true);
                                    }}
                                >
                                    {node.description || 'Click to add description...'}
                                </p>
                            )}

                            {/* Star rating for key results only */}
                            {node.type === 'key_result' && (
                                <div className="mt-3">
                                    <div className="text-xs text-slate-400 mb-2">
                                        Rating ({node.rating || 0}/5)
                                    </div>
                                    <div className="flex items-center gap-1">
                                        {[1, 2, 3, 4, 5].map((star) => {
                                            const isActive = (node.rating || 0) >= star;
                                            return (
                                                <button
                                                    key={star}
                                                    onClick={() => updateNode(node.id, { rating: star })}
                                                    className="transition-all hover:scale-110"
                                                    aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
                                                >
                                                    <Star
                                                        className="w-6 h-6 transition-colors"
                                                        style={{
                                                            fill: isActive ? '#facc15' : 'none',
                                                            stroke: isActive ? '#facc15' : '#475569',
                                                            strokeWidth: 2
                                                        }}
                                                    />
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* Time tracking */}
                            {(node.type === 'initiative' || node.type === 'task') && (
                                <div className="mt-2 space-y-1">
                                    {node.type === 'initiative' && (
                                        <>
                                            {/* Initiative: Show Total Time (Own + Sum of Children) */}
                                            <div className="flex items-center gap-2 text-sm">
                                                <Clock className="w-4 h-4 text-slate-400" />
                                                <span className="text-slate-300">
                                                    Total Time: {formatTime(
                                                        (node.timeSpent || 0) +
                                                        node.children.reduce((acc, childId) => {
                                                            const child = nodes[childId];
                                                            return acc + (child?.timeSpent || 0);
                                                        }, 0)
                                                    )}
                                                </span>
                                            </div>

                                            {/* Initiative: Show Session Time if running */}
                                            {isTimerRunning && currentTime > 0 && (
                                                <div className="flex items-center gap-2 text-sm text-green-400">
                                                    <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                                                    <span>Session Time: {formatTime(currentTime)}</span>
                                                </div>
                                            )}
                                        </>
                                    )}

                                    {node.type === 'task' && (
                                        /* Task: Show Total Time (Historical + Current Session) */
                                        <div className="flex items-center gap-2 text-sm text-slate-300">
                                            <Clock className="w-4 h-4 text-slate-400" />
                                            <span>
                                                Time: {formatTime((node.timeSpent || 0) + (isTimerRunning ? currentTime : 0))}
                                            </span>
                                            {isTimerRunning && (
                                                <span className="text-xs text-green-400 ml-1">
                                                    (+{formatTime(currentTime)})
                                                </span>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1 transition-opacity">
                            {/* Timer controls - only for initiatives */}
                            {node.type === 'initiative' && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleTimerToggle();
                                    }}
                                    onMouseDown={(e) => e.stopPropagation()}
                                    className={cn(
                                        'p-2 rounded-lg transition-all',
                                        isTimerRunning
                                            ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                                            : 'glass-hover text-slate-400 hover:text-green-400'
                                    )}
                                    title={isTimerRunning ? 'Stop timer' : 'Start timer'}
                                >
                                    {isTimerRunning ? (
                                        <Pause className="w-4 h-4" />
                                    ) : (
                                        <Play className="w-4 h-4" />
                                    )}
                                </button>
                            )}

                            {/* Plus button - hidden for initiatives and tasks */}
                            {!['initiative', 'task'].includes(node.type) && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onAddChild(node.id);
                                    }}
                                    onMouseDown={(e) => e.stopPropagation()}
                                    className="p-2 rounded-lg glass-hover text-slate-400 hover:text-purple-400 transition-all"
                                    title="Add child"
                                >
                                    <Plus className="w-4 h-4" />
                                </button>
                            )}

                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDelete(node);
                                }}
                                onMouseDown={(e) => e.stopPropagation()}
                                className="p-2 rounded-lg glass-hover text-slate-400 hover:text-red-400 transition-all"
                                title="Delete"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
