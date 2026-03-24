interface StatusIndicatorProps {
  status: string;
  label: string;
  lastRun: string;
  nextRun: string;
  lastError?: string | null;
}

const statusColors: Record<string, string> = {
  success: 'bg-green-600',
  failure: 'bg-red-600',
  unknown: 'bg-yellow-500',
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
  });
}

export default function StatusIndicator({ status, label, lastRun, nextRun, lastError }: StatusIndicatorProps) {
  const color = statusColors[status] || statusColors.unknown;
  return (
    <div className="border border-ink/10 p-6">
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-3 h-3 rounded-full ${color}`} />
        <h3 className="font-semibold text-ink capitalize font-sans">{label}</h3>
      </div>
      <div className="space-y-1 text-xs text-ink-muted font-sans">
        <p>Last run: {formatTime(lastRun)}</p>
        <p>Next run: {formatTime(nextRun)}</p>
        {lastError && <p className="text-red-600">Error: {lastError}</p>}
      </div>
    </div>
  );
}
