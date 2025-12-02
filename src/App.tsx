import { useState, useEffect } from 'react';
import { DragDropContext, DropResult } from '@hello-pangea/dnd';
import { motion } from 'framer-motion';
import { Target } from 'lucide-react';
import { Layout } from './components/Layout';
import { OKRTree } from './components/OKRTree';
import { AddNodeModal } from './components/AddNodeModal';
import { InlineDeleteModal } from './components/InlineDeleteModal';
import { GlobalTaskModal } from './components/GlobalTaskModal';
import { useOKRStore } from './store/useOKRStore';
import type { Node } from './types';



function App() {
    const rootIds = useOKRStore(state => state.rootIds);
    const deleteNodeStore = useOKRStore(state => state.deleteNode);
    const moveNode = useOKRStore(state => state.moveNode);
    const getActiveTimer = useOKRStore(state => state.getActiveTimer);
    const stopTimer = useOKRStore(state => state.stopTimer);

    // Handle browser close/refresh
    useEffect(() => {
        const handleBeforeUnload = () => {
            const activeNode = getActiveTimer();
            if (activeNode) {
                stopTimer(activeNode.id);
            }
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [getActiveTimer, stopTimer]);

    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [addParentId, setAddParentId] = useState<string | null>(null);

    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [nodeToDelete, setNodeToDelete] = useState<Node | null>(null);

    const handleAddRoot = () => {
        setAddParentId(null);
        setIsAddModalOpen(true);
    };

    const handleAddChild = (parentId: string) => {
        setAddParentId(parentId);
        setIsAddModalOpen(true);
    };

    const handleCloseAddModal = () => {
        setIsAddModalOpen(false);
        setAddParentId(null);
    };

    const handleDelete = (node: Node) => {
        setNodeToDelete(node);
        setIsDeleteModalOpen(true);
    };

    const handleCloseDeleteModal = () => {
        setIsDeleteModalOpen(false);
        setNodeToDelete(null);
    };

    const handleConfirmDelete = () => {
        if (nodeToDelete) {
            deleteNodeStore(nodeToDelete.id);
        }
    };

    const handleDragEnd = (result: DropResult) => {
        const { destination, source, draggableId } = result;

        if (!destination) return;

        if (
            destination.droppableId === source.droppableId &&
            destination.index === source.index
        ) {
            return;
        }

        // We only allow reordering within the same parent (same droppableId) for now
        if (destination.droppableId !== source.droppableId) {
            return;
        }

        // droppableId should be the parentId or 'root'
        const parentId = destination.droppableId === 'root' ? null : destination.droppableId;

        moveNode(draggableId, parentId, destination.index);
    };

    return (
        <>
            <Layout onAddRoot={handleAddRoot}>
                {rootIds.length === 0 ? (
                    // Empty State
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-col items-center justify-center py-20"
                    >
                        <div className="node-card max-w-md text-center">
                            <div className="inline-flex p-4 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 shadow-2xl mb-6">
                                <Target className="w-12 h-12 text-white" />
                            </div>

                            <h2 className="text-3xl font-bold gradient-text mb-4">
                                Welcome to OKR Tracker
                            </h2>

                            <p className="text-slate-300 mb-6 leading-relaxed">
                                Start by creating your first 2-year goal. From there, you can build out your
                                strategies, objectives, key results, and initiatives in a beautiful tree structure.
                            </p>

                            <div className="space-y-3 text-sm text-slate-400 mb-8">
                                <div className="flex items-center gap-2 justify-center">
                                    <div className="w-2 h-2 rounded-full bg-pink-500" />
                                    <span>Track progress across all levels</span>
                                </div>
                                <div className="flex items-center gap-2 justify-center">
                                    <div className="w-2 h-2 rounded-full bg-purple-500" />
                                    <span>Time tracking for initiatives</span>
                                </div>
                                <div className="flex items-center gap-2 justify-center">
                                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                                    <span>Automatic progress calculation</span>
                                </div>
                                <div className="flex items-center gap-2 justify-center">
                                    <div className="w-2 h-2 rounded-full bg-green-500" />
                                    <span>Local storage - your data stays private</span>
                                </div>
                            </div>

                            <button
                                onClick={handleAddRoot}
                                className="btn-primary text-lg px-8 py-3"
                            >
                                Create Your First Goal
                            </button>
                        </div>
                    </motion.div>
                ) : (
                    // Tree View
                    <div className="pb-12">
                        <DragDropContext onDragEnd={handleDragEnd}>
                            <OKRTree
                                nodeIds={rootIds}
                                onAddChild={handleAddChild}
                                onDelete={handleDelete}
                            />
                        </DragDropContext>
                    </div>
                )}

            </Layout>

            {/* Modals */}
            <AddNodeModal
                isOpen={isAddModalOpen}
                onClose={handleCloseAddModal}
                parentId={addParentId}
            />


            <InlineDeleteModal
                isOpen={isDeleteModalOpen}
                onClose={handleCloseDeleteModal}
                onConfirm={handleConfirmDelete}
                nodeTitle={nodeToDelete?.title || ''}
                hasChildren={nodeToDelete ? nodeToDelete.children.length > 0 : false}
            />

            <GlobalTaskModal />
        </>
    );
}

export default App;
