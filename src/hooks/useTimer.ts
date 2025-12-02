import { useEffect, useState } from 'react';
import { useOKRStore } from '../store/useOKRStore';

export function useTimer() {
    const [, setTick] = useState(0);
    const activeTimer = useOKRStore(state => state.getActiveTimer());

    useEffect(() => {
        if (!activeTimer) return;

        const interval = setInterval(() => {
            setTick(t => t + 1);
        }, 1000);

        return () => clearInterval(interval);
    }, [activeTimer]);

    return activeTimer;
}

export function useCurrentTime(nodeId: string) {
    const [, setTick] = useState(0);
    const node = useOKRStore(state => state.nodes[nodeId]);

    useEffect(() => {
        if (!node?.timerStartedAt) return;

        const interval = setInterval(() => {
            setTick(t => t + 1);
        }, 1000);

        return () => clearInterval(interval);
    }, [node?.timerStartedAt]);

    if (!node) return 0;

    let sessionMinutes = 0;
    if (node.timerStartedAt) {
        sessionMinutes = (Date.now() - node.timerStartedAt) / 60000;
    }

    return sessionMinutes;
}
