import React from 'react';

export default function LiveDebugHud({
  livekitConnected,
  voiceDegraded,
  liveTurnState,
  interviewerStyle,
  interruptionProfile,
  livekitMicEnabled,
  livekitRemoteAudioActive,
  isBargeInActive,
  lowConfidenceStreak,
  livekitTranscriptEntries,
}) {
  const recentConfidenceEntries = (livekitTranscriptEntries || [])
    .filter((entry) => entry?.speaker === 'you' && entry?.isFinal && typeof entry?.confidence === 'number')
    .slice(-10);

  const recentAverage = recentConfidenceEntries.length
    ? recentConfidenceEntries.reduce((sum, entry) => sum + entry.confidence, 0) / recentConfidenceEntries.length
    : null;

  const chartWidth = 120;
  const chartHeight = 28;
  const trendPoints = recentConfidenceEntries.map((entry, idx, list) => {
    const x = list.length <= 1 ? chartWidth / 2 : (idx * chartWidth) / (list.length - 1);
    const y = chartHeight - Math.max(0, Math.min(1, entry.confidence)) * chartHeight;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <div className="mt-3 rounded-lg border border-cyan-400/20 bg-slate-900/60 p-3">
      <p className="text-[11px] uppercase tracking-wide text-cyan-200 mb-2">Live Debug HUD</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-slate-200">
        <p>Mode: {livekitConnected ? (voiceDegraded ? 'fallback_stream' : 'voice') : 'disconnected'}</p>
        <p>Turn State: {liveTurnState}</p>
        <p>Style: {interviewerStyle}</p>
        <p>Interruption: {interruptionProfile}</p>
        <p>Mic: {livekitMicEnabled ? 'on' : 'off'}</p>
        <p>Agent Audio: {livekitRemoteAudioActive ? 'active' : 'waiting'}</p>
        <p>Barge-in: {isBargeInActive ? 'active' : 'idle'}</p>
        <p>Low Confidence Streak: {lowConfidenceStreak}</p>
        <p>
          Avg Confidence (last {recentConfidenceEntries.length || 0}):{' '}
          {typeof recentAverage === 'number' ? recentAverage.toFixed(2) : 'n/a'}
        </p>
        <p>Transcript Entries: {livekitTranscriptEntries.length}</p>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <span className="text-[11px] text-cyan-100/90">Confidence Trend</span>
        <div className="rounded border border-cyan-400/20 bg-slate-950/50 px-2 py-1">
          <svg width={chartWidth} height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label="confidence trend sparkline">
            <line x1="0" y1={chartHeight} x2={chartWidth} y2={chartHeight} stroke="rgba(148, 163, 184, 0.35)" strokeWidth="1" />
            <line x1="0" y1={chartHeight * 0.5} x2={chartWidth} y2={chartHeight * 0.5} stroke="rgba(34, 211, 238, 0.2)" strokeWidth="1" />
            {trendPoints.length > 0 && (
              <polyline
                fill="none"
                stroke="rgb(34, 211, 238)"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={trendPoints.join(' ')}
              />
            )}
          </svg>
        </div>
      </div>
    </div>
  );
}
