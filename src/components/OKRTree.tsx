import { motion, AnimatePresence } from 'framer-motion';
import { Droppable, Draggable } from '@hello-pangea/dnd';
import type { Node } from '../types';
import { useOKRStore } from '../store/useOKRStore';
import { NodeItem } from './NodeItem';

interface OKRTreeProps {
    nodeIds: string[];
    onAddChild: (parentId: string) => void;
    onDelete: (node: Node) => void;
    parentId?: string;
}

export function OKRTree({ nodeIds, onAddChild, onDelete, parentId = 'root' }: OKRTreeProps) {
    const nodes = useOKRStore(state => state.nodes);

    return (
        <Droppable droppableId={parentId}>
            {(provided) => (
                <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className="space-y-4"
                >
                    <AnimatePresence mode="popLayout">
                        {nodeIds.map((nodeId, index) => {
                            const node = nodes[nodeId];
                            if (!node) return null;

                            return (
                                <Draggable key={node.id} draggableId={node.id} index={index}>
                                    {(provided) => (
                                        <div
                                            ref={provided.innerRef}
                                            {...provided.draggableProps}
                                            {...provided.dragHandleProps}
                                        >
                                            <motion.div
                                                layout
                                                className="space-y-3"
                                            >
                                                <NodeItem
                                                    node={node}
                                                    onAddChild={onAddChild}
                                                    onDelete={onDelete}
                                                />

                                                {/* Render children recursively */}
                                                {node.isExpanded && node.children.length > 0 && (
                                                    <motion.div
                                                        initial={{ opacity: 0, height: 0 }}
                                                        animate={{ opacity: 1, height: 'auto' }}
                                                        exit={{ opacity: 0, height: 0 }}
                                                        transition={{ duration: 0.3 }}
                                                        className="ml-8 pl-4 border-l-2 border-slate-700/50"
                                                    >
                                                        <OKRTree
                                                            nodeIds={node.children}
                                                            onAddChild={onAddChild}
                                                            onDelete={onDelete}
                                                            parentId={node.id}
                                                        />
                                                    </motion.div>
                                                )}
                                            </motion.div>
                                        </div>
                                    )}
                                </Draggable>
                            );
                        })}
                    </AnimatePresence>
                    {provided.placeholder}
                </div>
            )}
        </Droppable>
    );
}
