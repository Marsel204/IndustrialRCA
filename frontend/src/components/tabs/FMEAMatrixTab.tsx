import React from 'react';
import { ShieldAlert } from 'lucide-react';
import { RCAState } from '../../types';

interface FMEAMatrixTabProps {
  rcaState: RCAState | null;
  onSimulateScenario?: (scenario: string) => void;
  simulationScenario?: string;
  simulationPhase?: string;
  simulationCountdown?: number;
}

export const FMEAMatrixTab: React.FC<FMEAMatrixTabProps> = ({ rcaState }) => {
  const hypotheses = rcaState?.hypothesis_results || [];
  const whys = rcaState?.causal_chain_5_whys || [];
  return (
    <div className="space-y-4 text-sm text-slate-800">
      <div className="flex items-center gap-2">
        <ShieldAlert className="w-4 h-4 text-teal-700" />
        <h2 className="font-semibold">Investigation hypotheses</h2>
      </div>
      <p className="text-slate-600">Candidates and evidence come from the active investigation. Confidence is a model assessment, not a calibrated probability.</p>
      {!hypotheses.length && <p role="status" className="p-4 bg-white border border-slate-200 rounded-lg">No hypotheses have been submitted. {rcaState?.pipeline_status === 'INCONCLUSIVE' ? 'The investigation ended without a supported diagnosis.' : 'Start an investigation to gather evidence.'}</p>}
      {hypotheses.map((hypothesis) => (
        <details key={hypothesis.hypothesis_id} className="bg-white border border-slate-200 rounded-lg p-4" open={hypothesis.hypothesis_id === rcaState?.winning_hypothesis?.hypothesis_id}>
          <summary className="cursor-pointer font-semibold break-words">{hypothesis.name} · {hypothesis.status} · {(hypothesis.confidence * 100).toFixed(0)}%</summary>
          <p className="mt-3 break-words">{hypothesis.falsification_rationale}</p>
          <ul className="mt-3 space-y-2 list-disc pl-5">
            {hypothesis.evidence.map((item, index) => <li key={index} className="break-words"><strong>{item.check}</strong><pre className="whitespace-pre-wrap break-words text-xs mt-1">{item.observation}</pre></li>)}
          </ul>
          {!!hypothesis.proposed_actions.length && <p className="mt-3">Proposed follow-up: {hypothesis.proposed_actions.join('; ')}</p>}
        </details>
      ))}
      {!!whys.length && <section className="space-y-3"><h3 className="font-semibold">Evidence-linked causal explanation</h3>{whys.map((step, index) => <div key={index} className="p-3 border border-slate-200 rounded-lg bg-white"><p className="font-medium">{step.question}</p><p>{step.answer}</p><p className="text-slate-600 mt-2">Evidence: {step.evidence}</p></div>)}</section>}
      {!!rcaState?.missing_evidence?.length && <section role="status" className="p-4 bg-amber-50 border border-amber-200 rounded-lg"><h3 className="font-semibold">Evidence still needed</h3><ul className="list-disc pl-5 mt-2 space-y-1">{rcaState.missing_evidence.map((gap, index) => <li key={index}>{gap}</li>)}</ul></section>}
    </div>
  );
};
