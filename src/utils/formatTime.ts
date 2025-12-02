export function formatTime(minutes: number): string {
    if (minutes < 1) {
        return '0m';
    }

    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);

    if (hours === 0) {
        return `${mins}m`;
    }

    if (mins === 0) {
        return `${hours}h`;
    }

    return `${hours}h ${mins}m`;
}

export function formatTimeDetailed(minutes: number): string {
    if (minutes < 1) {
        return '0 minutes';
    }

    const days = Math.floor(minutes / (60 * 24));
    const hours = Math.floor((minutes % (60 * 24)) / 60);
    const mins = Math.floor(minutes % 60);

    const parts: string[] = [];

    if (days > 0) {
        parts.push(`${days} ${days === 1 ? 'day' : 'days'}`);
    }
    if (hours > 0) {
        parts.push(`${hours} ${hours === 1 ? 'hour' : 'hours'}`);
    }
    if (mins > 0) {
        parts.push(`${mins} ${mins === 1 ? 'minute' : 'minutes'}`);
    }

    return parts.join(', ');
}
