import React from 'react';

export default function LiveTranscriptPanels({ livekitFallbackMessages, livekitTranscriptEntries }) {
  return (
    <>
      {livekitFallbackMessages.length > 0 && (
        <div className="mt-3 rounded-lg border border-cyan-400/20 bg-slate-900/40 p-3">
          <p className="text-[11px] uppercase tracking-wide text-cyan-200 mb-2">Coach Stream</p>
          <div className="space-y-1">
            {livekitFallbackMessages.map((message, idx) => (
              <p key={`coach-msg-${idx}`} className="text-xs text-slate-200">
                {message}
              </p>
            ))}
          </div>
        </div>
      )}

      {livekitTranscriptEntries.length > 0 && (
        <div className="mt-3 rounded-lg border border-cyan-400/20 bg-slate-900/40 p-3">
          <p className="text-[11px] uppercase tracking-wide text-cyan-200 mb-2">Live Transcript</p>
          <div className="space-y-1 max-h-48 overflow-auto pr-1">
            {livekitTranscriptEntries.map((entry, idx) => (
              <p key={`transcript-${entry.ts}-${idx}`} className="text-xs text-slate-200">
                <span className="text-cyan-300">{entry.speaker === 'you' ? 'You' : 'Interviewer'}:</span>{' '}
                {entry.text}
                {!entry.isFinal && <span className="text-slate-400"> ...</span>}
                <span className="text-slate-500"> {new Date(entry.ts).toLocaleTimeString()}</span>
                {typeof entry.confidence === 'number' && (
                  <span className="text-slate-500"> · conf {entry.confidence.toFixed(2)}</span>
                )}
              </p>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
