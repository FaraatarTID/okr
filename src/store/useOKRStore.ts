import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Node, OKRStore } from '../types';

const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

const calculateProgress = (nodeId: string, nodes: Record<string, Node>): number => {
    const node = nodes[nodeId];
    if (!node || node.children.length === 0) {
        return node?.progress || 0;
    }

    const childrenProgress = node.children
        .map(childId => calculateProgress(childId, nodes))
        .filter(p => !isNaN(p));

    if (childrenProgress.length === 0) return node.progress;

    const average = childrenProgress.reduce((sum, p) => sum + p, 0) / childrenProgress.length;
    return Math.round(average);
};

const recalculateProgressUpwards = (nodeId: string | undefined, nodes: Record<string, Node>): Record<string, Node> => {
    if (!nodeId) return nodes;

    const node = nodes[nodeId];
    if (!node) return nodes;

    const newProgress = calculateProgress(nodeId, nodes);
    const updatedNodes = {
        ...nodes,
        [nodeId]: { ...node, progress: newProgress }
    };

    return recalculateProgressUpwards(node.parentId, updatedNodes);
};

export const useOKRStore = create<OKRStore>()(
    persist(
        (set, get) => ({
            nodes: {},
            rootIds: [],
            activeTaskModalNodeId: null,
            setActiveTaskModalNodeId: (id) => {
                const currentState = get().activeTaskModalNodeId;

                // Force update even if same value by toggling
                if (currentState === id) {
                    set({ activeTaskModalNodeId: null });
                    setTimeout(() => set({ activeTaskModalNodeId: id }), 0);
                } else {
                    set({ activeTaskModalNodeId: id });
                }
            },

            addNode: (parentId, type, data) => {
                const id = generateId();
                const newNode: Node = {
                    id,
                    type,
                    title: data.title || 'Untitled',
                    description: data.description,
                    progress: data.progress || 0,
                    children: [],
                    parentId: parentId || undefined,
                    createdAt: Date.now(),
                    timeSpent: 0,
                    isExpanded: true,
                    rating: 0,
                    ...data,
                };

                set((state) => {
                    const nodes = { ...state.nodes, [id]: newNode };

                    if (parentId) {
                        const parent = nodes[parentId];
                        if (parent) {
                            nodes[parentId] = {
                                ...parent,
                                children: [...parent.children, id],
                            };
                        }
                    }

                    return {
                        nodes,
                        rootIds: parentId ? state.rootIds : [...state.rootIds, id],
                    };
                });
            },

            updateNode: (id, data) => {
                set((state) => {
                    const node = state.nodes[id];
                    if (!node) return state;

                    let nodes = {
                        ...state.nodes,
                        [id]: { ...node, ...data },
                    };

                    // If progress was updated, recalculate parent progress
                    if (data.progress !== undefined && data.progress !== node.progress) {
                        nodes = recalculateProgressUpwards(node.parentId, nodes);
                    }

                    return { nodes };
                });
            },

            deleteNode: (id) => {
                set((state) => {
                    const node = state.nodes[id];
                    if (!node) return state;

                    const nodes = { ...state.nodes };

                    // Recursively delete children
                    const deleteRecursive = (nodeId: string) => {
                        const n = nodes[nodeId];
                        if (!n) return;

                        n.children.forEach(childId => deleteRecursive(childId));
                        delete nodes[nodeId];
                    };

                    deleteRecursive(id);

                    // Remove from parent's children array
                    if (node.parentId) {
                        const parent = nodes[node.parentId];
                        if (parent) {
                            nodes[node.parentId] = {
                                ...parent,
                                children: parent.children.filter(childId => childId !== id),
                            };
                        }
                    }

                    return {
                        nodes,
                        rootIds: state.rootIds.filter(rootId => rootId !== id),
                    };
                });
            },

            moveNode: (dragId, parentId, newIndex) => {
                set((state) => {
                    const nodes = { ...state.nodes };
                    let rootIds = [...state.rootIds];
                    const node = nodes[dragId];

                    if (!node) return state;

                    // 1. Remove from old position
                    if (node.parentId) {
                        const oldParent = nodes[node.parentId];
                        if (oldParent) {
                            nodes[node.parentId] = {
                                ...oldParent,
                                children: oldParent.children.filter(id => id !== dragId)
                            };
                        }
                    } else {
                        rootIds = rootIds.filter(id => id !== dragId);
                    }

                    // 2. Update node's parentId
                    nodes[dragId] = {
                        ...node,
                        parentId: parentId || undefined
                    };

                    // 3. Insert into new position
                    if (parentId) {
                        const newParent = nodes[parentId];
                        if (newParent) {
                            const newChildren = [...newParent.children];
                            // Ensure index is valid
                            const safeIndex = Math.min(newIndex, newChildren.length);
                            newChildren.splice(safeIndex, 0, dragId);

                            nodes[parentId] = {
                                ...newParent,
                                children: newChildren
                            };
                        }
                    } else {
                        // Ensure index is valid
                        const safeIndex = Math.min(newIndex, rootIds.length);
                        rootIds.splice(safeIndex, 0, dragId);
                    }

                    return { nodes, rootIds };
                });
            },

            toggleExpand: (id) => {
                set((state) => {
                    const node = state.nodes[id];
                    if (!node) return state;

                    return {
                        nodes: {
                            ...state.nodes,
                            [id]: { ...node, isExpanded: !node.isExpanded },
                        },
                    };
                });
            },

            startTimer: (id) => {
                set((state) => {
                    const nodes = { ...state.nodes };

                    // Stop all other timers
                    Object.keys(nodes).forEach(nodeId => {
                        if (nodes[nodeId].timerStartedAt) {
                            nodes[nodeId] = {
                                ...nodes[nodeId],
                                // Just stop the timer, don't auto-log time (user must use stop button to log)
                                timerStartedAt: undefined,
                            };
                        }
                    });

                    // Start this timer
                    const node = nodes[id];
                    if (node) {
                        nodes[id] = {
                            ...node,
                            timerStartedAt: Date.now(),
                        };
                    }

                    return { nodes };
                });
            },

            stopTimer: (id) => {
                set((state) => {
                    const node = state.nodes[id];
                    if (!node || !node.timerStartedAt) return state;

                    return {
                        nodes: {
                            ...state.nodes,
                            [id]: {
                                ...node,
                                timerStartedAt: undefined,
                            },
                        },
                    };
                });
            },

            getActiveTimer: () => {
                const nodes = get().nodes;
                const node = Object.values(nodes).find(n => n.timerStartedAt);
                return node || null;
            },
        }),
        {
            name: 'okr-storage',
            partialize: (state) => ({
                nodes: state.nodes,
                rootIds: state.rootIds,
            }),
        }
    )
);
