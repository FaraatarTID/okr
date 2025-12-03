import { useOKRStore } from '../store/useOKRStore';
import { TaskSummaryModal } from './TaskSummaryModal';

export function GlobalTaskModal() {
    const activeTaskModalNodeId = useOKRStore(state => state.activeTaskModalNodeId);
    const nodes = useOKRStore(state => state.nodes);
    const setActiveTaskModalNodeId = useOKRStore(state => state.setActiveTaskModalNodeId);
    const stopTimer = useOKRStore(state => state.stopTimer);
    const addNode = useOKRStore(state => state.addNode);

    const activeNode = activeTaskModalNodeId ? nodes[activeTaskModalNodeId] : null;

    if (!activeNode) return null;

    const sessionTime = activeNode.timerStartedAt
        ? (Date.now() - activeNode.timerStartedAt) / 60000
        : 0;

    return (
        <TaskSummaryModal
            isOpen={true}
            onClose={() => setActiveTaskModalNodeId(null)}
            onSubmit={(summary) => {
                // Recalculate session time to get accurate elapsed time
                const actualSessionTime = activeNode.timerStartedAt
                    ? (Date.now() - activeNode.timerStartedAt) / 60000
                    : sessionTime;

                // Stop the timer
                stopTimer(activeNode.id);

                // Create a task node as child
                addNode(activeNode.id, 'task', {
                    title: summary,
                    timeSpent: actualSessionTime,
                    lastSessionTime: actualSessionTime,
                });

                setActiveTaskModalNodeId(null);
            }}
            onStopWithoutLog={() => {
                stopTimer(activeNode.id);
                setActiveTaskModalNodeId(null);
            }}
            sessionTime={sessionTime}
        />
    );
}
