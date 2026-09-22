import React, { useState } from 'react';
import { X, CheckCircle2, ShieldCheck, AlertTriangle, FileCheck2, UserCheck } from 'lucide-react';
import { RCAState } from '../../types';

interface ReviewSignOffModalProps {
  isOpen: boolean;
  onClose: () => void;
  rcaState: RCAState | null;
  onSubmitReview: (params: {
    action: string;
    reviewer: string;
    notes: string;
    override_root_cause?: string;
  }) => Promise<void>;
}

export const ReviewSignOffModal: React.FC<ReviewSignOffModalProps> = ({
  isOpen,
  onClose,
  rcaState,
  onSubmitReview,
}) => {
  const [decision, setDecision] = useState<'approve' | 'reject' | 'override'>('approve');
  const [reviewerName, setReviewerName] = useState<string>(
    'J. Reynolds (Machinery Reliability Specialist)'
  );
  const [digitalSignature, setDigitalSignature] = useState<string>('J. Reynolds, PE #84920');
  const [notes, setNotes] = useState<string>(
    'Verified via multi-sensor physical convergence and ISA-95 upstream topology tracing. ' +
    'Suction strainer STR-301A differential pressure breached 1.85 bar due to deferred PM WM-2026-0831. ' +
    'Resulting NPSHa starvation triggered severe acoustic cavitation (48.9% broadband ratio in 2-8 kHz FFT), ' +
    'wiping the DE sleeve bearing lubrication film. Corrective overhaul authorized.'
  );
  const [overrideRootCause, setOverrideRootCause] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const fullNotes = `${notes.trim()}\n\n[Digital Signature: ${digitalSignature.trim()} | Timestamp: ${new Date().toISOString()}]`;
      await onSubmitReview({
        action: decision,
        reviewer: reviewerName,
        notes: fullNotes,
        override_root_cause: decision === 'override' ? overrideRootCause : undefined,
      });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to submit review');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFinalized = rcaState?.pipeline_status === 'COMPLETED';

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-2xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-600">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 font-mono uppercase tracking-wide">
                Review & Authorize Action
              </h2>
              <p className="text-xs text-slate-500">
                HITL Gate: Human authorization required for SAP PM01 & 8D release
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs font-mono text-red-700">
              {error}
            </div>
          )}

          {/* Diagnostic Context Pill */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-2 text-xs font-mono">
            <div className="flex justify-between items-center text-slate-600">
              <span>Target Asset:</span>
              <strong className="text-slate-900">{rcaState?.root_cause_asset ? `${rcaState.root_cause_asset} (Wecon VM Inverter)` : 'VFD_VM_01 (Wecon VM Series Inverter)'}</strong>
            </div>
            <div className="flex justify-between items-center text-slate-600">
              <span>Diagnosed Root Cause:</span>
              <strong className="text-teal-700">
                {rcaState?.winning_hypothesis?.name || 'NPSH Starvation via Blinded Strainer STR-301A'}
              </strong>
            </div>
            <div className="flex justify-between items-center text-slate-600">
              <span>Deliverables Generated:</span>
              <span className="text-blue-700 font-semibold">1 SAP Work Order (PM01) + 8D Incident Report</span>
            </div>
          </div>

          {/* Action Choice Toggle */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono font-semibold text-slate-700 block uppercase">
              Authorization Decision:
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setDecision('approve')}
                className={`py-2 px-3 rounded-lg border text-xs font-mono font-semibold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                  decision === 'approve'
                    ? 'bg-teal-50 border-teal-500 text-teal-800 ring-2 ring-teal-500/20'
                    : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                <CheckCircle2 className="w-4 h-4 text-teal-600" />
                <span>Approve</span>
              </button>

              <button
                type="button"
                onClick={() => setDecision('override')}
                className={`py-2 px-3 rounded-lg border text-xs font-mono font-semibold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                  decision === 'override'
                    ? 'bg-amber-50 border-amber-500 text-amber-800 ring-2 ring-amber-500/20'
                    : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Override</span>
              </button>

              <button
                type="button"
                onClick={() => setDecision('reject')}
                className={`py-2 px-3 rounded-lg border text-xs font-mono font-semibold flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                  decision === 'reject'
                    ? 'bg-red-50 border-red-500 text-red-800 ring-2 ring-red-500/20'
                    : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                <X className="w-4 h-4 text-red-600" />
                <span>Reject</span>
              </button>
            </div>
          </div>

          {/* Conditional Override Input */}
          {decision === 'override' && (
            <div className="space-y-1">
              <label className="text-xs font-mono font-semibold text-amber-800 block">
                Custom Root Cause Override:
              </label>
              <input
                type="text"
                value={overrideRootCause}
                onChange={(e) => setOverrideRootCause(e.target.value)}
                placeholder="e.g., Mechanical seal barrier fluid failure"
                required
                className="w-full bg-white border border-amber-300 rounded-lg px-3 py-2 text-xs font-sans text-slate-800 focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>
          )}

          {/* Reviewer & Digital Signature Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-mono font-semibold text-slate-700 block">
                Engineer Name:
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  required
                  className="w-full bg-white border border-slate-200 rounded-lg pl-8 pr-3 py-2 text-xs font-sans text-slate-800 focus:outline-none focus:ring-1 focus:ring-teal-500"
                />
                <UserCheck className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-mono font-semibold text-slate-700 block">
                Digital Signature / Stamp:
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={digitalSignature}
                  onChange={(e) => setDigitalSignature(e.target.value)}
                  placeholder="e.g. J. Reynolds, PE #84920"
                  required
                  className="w-full bg-white border border-slate-200 rounded-lg pl-8 pr-3 py-2 text-xs font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-teal-500"
                />
                <ShieldCheck className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              </div>
            </div>
          </div>

          {/* Engineering Justification Notes */}
          <div className="space-y-1">
            <div className="flex justify-between items-center">
              <label className="text-xs font-mono font-semibold text-slate-700">
                Engineering Review & Sign-Off Notes:
              </label>
              <span className="text-[10px] text-slate-500 font-mono">Bound to SAP PM01 & 8D</span>
            </div>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              required
              className="w-full bg-white border border-slate-200 rounded-lg p-2.5 text-xs font-sans text-slate-700 focus:outline-none focus:ring-1 focus:ring-teal-500 leading-relaxed"
            />
          </div>

          {/* Footer Actions */}
          <div className="pt-2 flex items-center justify-end space-x-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg border border-slate-200 text-xs font-mono text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className={`px-5 py-2 rounded-lg text-xs font-mono font-bold uppercase tracking-wider flex items-center space-x-2 transition-all cursor-pointer shadow-xs ${
                decision === 'approve'
                  ? 'bg-teal-600 hover:bg-teal-700 text-white'
                  : decision === 'override'
                  ? 'bg-amber-600 hover:bg-amber-700 text-white'
                  : 'bg-red-600 hover:bg-red-700 text-white'
              }`}
            >
              <FileCheck2 className="w-4 h-4" />
              <span>
                {isSubmitting
                  ? 'Processing Sign-Off...'
                  : isFinalized
                  ? 'Update Sign-Off'
                  : 'Authorize & Emit Deliverables'}
              </span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
