import type { Node } from '../types';
import { useOKRStore } from '../store/useOKRStore';
import { NodeItem } from './NodeItem';

interface OKRTreeProps {
    nodeIds: string[];
    onAddChild: (parentId: string) => void;
    onDelete: (node: Node) => void;
}

export function OKRTree({ nodeIds, onAddChild, onDelete }: OKRTreeProps) {
    const nodes = useOKRStore(state => state.nodes);

    return (
        <div className="space-y-4">
            {nodeIds.map((nodeId) => {
                const node = nodes[nodeId];
                if (!node) return null;

                return (
                    <div key={node.id} className="space-y-3">
                        <NodeItem
                            node={node}
                            onAddChild={onAddChild}
                            onDelete={onDelete}
                        />

                        {/* Render children recursively */}
                        {node.isExpanded && node.children.length > 0 && (
                            <div className="ml-8 pl-4 border-l-2 border-slate-700/50">
                                <OKRTree
                                    nodeIds={node.children}
                                    onAddChild={onAddChild}
                                    onDelete={onDelete}
                                />
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
