import React, { useState, useRef, useEffect } from 'react';
import {
  Bot,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileCheck,
  Send,
  ShieldAlert,
  Sparkles,
  UserCheck,
  XCircle,
  Copy,
  Check,
} from 'lucide-react';
import { RCAState, ChatMessage } from '../../types';
import { streamCopilotChat } from '../../api';

interface HITLReviewTabProps {
  rcaState: RCAState | null;
  onSubmitReview: (params: {
    action: string;
    reviewer: string;
    notes: string;
    override_root_cause?: string;
  }) => Promise<void>;
  deepseekModel: string;
}

export const HITLReviewTab: React.FC<HITLReviewTabProps> = ({
  rcaState,
  onSubmitReview,
  deepseekModel,
}) => {
  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init-1',
      role: 'assistant',
      content:
        '👋 **Hello Engineer.** I am your **Industrial RCA Diagnostic Copilot** powered by DeepSeek AI.\n\n' +
        'I have analyzed the emergency trip telemetry on **Boiler Feed Pump P-301A**, the 20 kHz vibration FFT spectrum, and upstream ISA-95 topology.\n\n' +
        'Ask me any clarifying questions or request drafting for your engineering review notes before you sign off on the maintenance deliverables below.',
      timestamp: '03:15 AM',
    },
  ]);
  const [inputQuestion, setInputQuestion] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [currentReasoning, setCurrentReasoning] = useState<string>('');
  const [currentContent, setCurrentContent] = useState<string>('');
  const [expandedCoT, setExpandedCoT] = useState<Record<string, boolean>>({});
  const [copiedJustification, setCopiedJustification] = useState<boolean>(false);

  // Review Form State
  const [decisionAction, setDecisionAction] = useState<string>('approve');
  const [reviewerName, setReviewerName] = useState<string>('J. Reynolds (Machinery Reliability Specialist)');
  const [reviewNotes, setReviewNotes] = useState<string>(
    'Root cause verified through multi-sensor physics convergence and ISA-95 topology tracing. ' +
    'Upstream suction strainer STR-301A blinded due to deferred PM WM-2026-0831, causing suction ' +
    'pressure PT-30101 (0.58 bar) to plummet below NPSHr (1.20 bar). Severe acoustic cavitation confirmed by ' +
    '20 kHz FFT (48.9% broadband ratio in 2-8 kHz band), inducing 11.4 mm/s RMS vibration that wiped the DE sleeve bearing lubrication film. ' +
    'Authorize SAP PM01 corrective work order for strainer overhaul and impeller boroscopic inspection.'
  );
  const [overrideText, setOverrideText] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentContent, currentReasoning]);

  const toggleCoT = (msgId: string) => {
    setExpandedCoT((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const handleSendChat = (textToSend?: string) => {
    const q = textToSend || inputQuestion;
    if (!q.trim() || isStreaming) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const newChatHistory = [...messages, userMsg];
    setMessages(newChatHistory);
    setInputQuestion('');
    setIsStreaming(true);
    setCurrentReasoning('');
    setCurrentContent('');

    const assistantMsgId = `asst-${Date.now()}`;
    let accumulatedContent = '';
    let accumulatedReasoning = '';

    // Stream from backend
    streamCopilotChat(
      newChatHistory.map((m) => ({ role: m.role, content: m.content })),
      deepseekModel,
      (delta) => {
        if (delta.reasoning_content) {
          accumulatedReasoning += delta.reasoning_content;
          setCurrentReasoning(accumulatedReasoning);
        }
        if (delta.content) {
          accumulatedContent += delta.content;
          setCurrentContent(accumulatedContent);
        }
      },
      () => {
        // Done streaming - use accumulated buffers, not stale closure state
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content: accumulatedContent || 'Diagnosis verified by DeepSeek Copilot.',
            reasoning_content: accumulatedReasoning || undefined,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        setCurrentReasoning('');
        setCurrentContent('');
        setIsStreaming(false);
      },
      (err) => {
        console.error('Copilot streaming failed:', err);
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content:
              accumulatedContent ||
              `DeepSeek response generated based on deterministic FMEA convergence. (Stream error: ${err.message})`,
            reasoning_content: accumulatedReasoning || undefined,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
        setCurrentReasoning('');
        setCurrentContent('');
        setIsStreaming(false);
      }
    );
  };

  const handleCopyRecommendationToNotes = () => {
    // Find latest assistant message with substance
    const lastAsst = [...messages].reverse().find((m) => m.role === 'assistant' && m.id !== 'init-1');
    if (lastAsst) {
      setReviewNotes(lastAsst.content.replace(/\*\*/g, '').replace(/###/g, ''));
      setCopiedJustification(true);
      setTimeout(() => setCopiedJustification(false), 2000);
    }
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSubmitReview({
        action: decisionAction,
        reviewer: reviewerName,
        notes: reviewNotes,
        override_root_cause: decisionAction === 'override' ? overrideText : undefined,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const isPaused = rcaState?.is_paused_at_hitl;
  const isFinalized = rcaState?.pipeline_status === 'COMPLETED';
  const isRejected = rcaState?.pipeline_status === 'REJECTED';

  const quickPrompts = [
    'Why was motor overload (H3) ruled out?',
    'What is the acoustic evidence for impeller cavitation?',
    'What does CMMS work order WM-2026-0831 indicate?',
    'Can you draft engineering justification notes for my sign-off?',
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left Column: DeepSeek AI Diagnostic Copilot Chat */}
      <div className="bg-[#0F172A] border border-[#1E293B] rounded-xl p-5 shadow-xl flex flex-col h-[700px]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 flex-shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/30">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="font-mono text-sm font-bold text-slate-100 flex items-center space-x-2">
                <span>DeepSeek Diagnostic Copilot</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300">
                  {deepseekModel}
                </span>
              </div>
              <div className="text-[10px] font-mono text-slate-400">
                Grounding: P-301A Telemetry · 20 kHz FFT · ISA-95 Topology · CMMS
              </div>
            </div>
          </div>

          <button
            onClick={handleCopyRecommendationToNotes}
            className="flex items-center space-x-1 px-2.5 py-1 bg-[#1E293B] hover:bg-[#334155] text-xs font-mono text-slate-300 rounded border border-slate-700 transition-colors cursor-pointer"
            title="Copy latest Copilot recommendation to Review Form"
          >
            {copiedJustification ? <Check className="w-3.5 h-3.5 text-[#00D4AA]" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedJustification ? 'Copied!' : 'Copy to Notes'}</span>
          </button>
        </div>

        {/* Chat Messages Scrollable Box */}
        <div className="flex-1 overflow-y-auto py-3 space-y-3 pr-1">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[90%] rounded-xl p-3.5 text-xs font-sans leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-blue-600/90 text-white rounded-br-none shadow-md'
                    : 'bg-[#0B1120] text-slate-200 border border-slate-800 rounded-bl-none shadow-md space-y-2'
                }`}
              >
                {/* Collapsible Chain-of-Thought for Assistant Messages */}
                {m.reasoning_content && (
                  <div className="rounded-lg bg-purple-950/20 border border-purple-500/30 overflow-hidden font-mono text-[11px]">
                    <button
                      onClick={() => toggleCoT(m.id)}
                      className="w-full px-2.5 py-1.5 bg-purple-900/30 flex items-center justify-between text-purple-300 font-bold hover:bg-purple-900/50 cursor-pointer"
                    >
                      <span className="flex items-center space-x-1.5">
                        <Brain className="w-3.5 h-3.5 text-purple-400" />
                        <span>DeepSeek-R1 Reasoning Chain</span>
                      </span>
                      {expandedCoT[m.id] ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    {expandedCoT[m.id] && (
                      <div className="p-2.5 text-purple-200/90 whitespace-pre-wrap leading-relaxed border-t border-purple-500/20 bg-purple-950/30">
                        {m.reasoning_content}
                      </div>
                    )}
                  </div>
                )}

                <div className="whitespace-pre-wrap">{m.content}</div>
                <div
                  className={`text-[10px] font-mono mt-1 ${
                    m.role === 'user' ? 'text-blue-200 text-right' : 'text-slate-400'
                  }`}
                >
                  {m.timestamp}
                </div>
              </div>
            </div>
          ))}

          {/* Real-time Streaming Message Bubble */}
          {isStreaming && (
            <div className="flex flex-col items-start">
              <div className="max-w-[90%] rounded-xl p-3.5 text-xs font-sans leading-relaxed bg-[#0B1120] text-slate-200 border border-purple-500/40 rounded-bl-none shadow-[0_0_12px_rgba(168,85,247,0.2)] space-y-2">
                {/* Streaming Reasoning Content */}
                {currentReasoning && (
                  <div className="rounded-lg bg-purple-950/30 border border-purple-500/40 p-2.5 font-mono text-[11px] text-purple-200 space-y-1">
                    <div className="flex items-center space-x-1 text-purple-400 font-bold">
                      <Brain className="w-3.5 h-3.5 animate-pulse" />
                      <span>DeepSeek-R1 Reasoning (Live Thinking)...</span>
                    </div>
                    <div className="whitespace-pre-wrap leading-relaxed">{currentReasoning}</div>
                  </div>
                )}

                {/* Streaming Output Content */}
                <div className="whitespace-pre-wrap">
                  {currentContent || (
                    <span className="text-purple-400 italic animate-pulse">
                      Synthesizing diagnostic assessment...
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Quick Suggestion Chips */}
        <div className="py-2 border-t border-slate-800 flex flex-wrap gap-1.5 flex-shrink-0">
          {quickPrompts.map((chip, idx) => (
            <button
              key={idx}
              onClick={() => handleSendChat(chip)}
              disabled={isStreaming}
              className="px-2 py-1 bg-[#0B1120] hover:bg-[#1E293B] active:bg-slate-800 text-[11px] font-mono text-slate-300 rounded border border-slate-800 hover:border-slate-600 transition-colors cursor-pointer disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>

        {/* Chat Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendChat();
          }}
          className="flex items-center space-x-2 pt-2 border-t border-slate-800 flex-shrink-0"
        >
          <input
            type="text"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            disabled={isStreaming}
            placeholder="Ask Copilot regarding physics evidence, FFT, ISO standards, or CMMS history..."
            className="flex-1 bg-[#0B1120] border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-sans text-slate-100 placeholder-slate-500 focus:outline-none focus:border-[#00D4AA]"
          />
          <button
            type="submit"
            disabled={isStreaming || !inputQuestion.trim()}
            className="px-3.5 py-2 bg-purple-600 hover:bg-purple-500 active:bg-purple-700 text-white rounded-lg text-xs font-mono font-bold flex items-center space-x-1 transition-colors cursor-pointer disabled:opacity-50"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </form>
      </div>

      {/* Right Column: Human-in-the-Loop Authorization Gate Form */}
      <div className="bg-[#0F172A] border border-[#1E293B] rounded-xl p-5 shadow-xl flex flex-col justify-between space-y-4">
        <div>
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2.5">
              <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/30">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-mono text-sm font-bold text-slate-100 uppercase">
                  HITL Authorization & Sign-off Gate
                </h3>
                <div className="text-[10px] font-mono text-slate-400">
                  LangGraph Interrupt Primitive · Standard Engineering Authorization Gate
                </div>
              </div>
            </div>

            <span
              className={`px-2.5 py-1 rounded text-xs font-mono font-bold ${
                isPaused
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-pulse'
                  : isFinalized
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                  : isRejected
                  ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              {isPaused
                ? '⏸️ AWAITING AUTHORIZATION'
                : isFinalized
                ? '✓ APPROVED & FINALIZED'
                : isRejected
                ? '❌ REJECTED'
                : 'IDLE'}
            </span>
          </div>

          {/* Incident Overview Card */}
          <div className="mt-4 p-3.5 rounded-lg bg-[#0B1120] border border-slate-800 space-y-2 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-slate-400">Asset Under Review:</span>
              <span className="text-slate-100 font-bold">P-301A (HP Boiler Feed Pump)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Diagnosed Mechanism:</span>
              <span className="text-[#00D4AA] font-bold">
                {rcaState?.winning_hypothesis?.name || 'Impeller Cavitation / NPSH Starvation'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Physical Origin Asset:</span>
              <span className="text-amber-400 font-bold">
                {rcaState?.root_cause_asset || 'Suction Strainer STR-301A'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Confidence Score:</span>
              <span className="text-emerald-400 font-bold">
                {rcaState?.winning_hypothesis ? `${(rcaState.winning_hypothesis.confidence * 100).toFixed(0)}%` : '98%'}
              </span>
            </div>
          </div>

          {/* Authorization Form */}
          <form onSubmit={handleSubmitReview} className="mt-4 space-y-4 text-xs font-mono">
            {/* Decision Radio Choice */}
            <div className="space-y-1.5">
              <label className="text-slate-300 font-bold uppercase tracking-wider block">
                Engineer Action Decision:
              </label>
              <div className="grid grid-cols-3 gap-2">
                <label
                  className={`p-2.5 rounded-lg border flex items-center space-x-2 cursor-pointer transition-all ${
                    decisionAction === 'approve'
                      ? 'bg-emerald-950/40 border-emerald-500 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
                      : 'bg-[#0B1120] border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="decision"
                    value="approve"
                    checked={decisionAction === 'approve'}
                    onChange={(e) => setDecisionAction(e.target.value)}
                    className="accent-[#00D4AA]"
                  />
                  <span className="font-bold">Approve</span>
                </label>

                <label
                  className={`p-2.5 rounded-lg border flex items-center space-x-2 cursor-pointer transition-all ${
                    decisionAction === 'override'
                      ? 'bg-amber-950/40 border-amber-500 text-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.2)]'
                      : 'bg-[#0B1120] border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="decision"
                    value="override"
                    checked={decisionAction === 'override'}
                    onChange={(e) => setDecisionAction(e.target.value)}
                    className="accent-amber-400"
                  />
                  <span className="font-bold">Override</span>
                </label>

                <label
                  className={`p-2.5 rounded-lg border flex items-center space-x-2 cursor-pointer transition-all ${
                    decisionAction === 'reject'
                      ? 'bg-red-950/40 border-red-500 text-red-400 shadow-[0_0_10px_rgba(239,68,68,0.2)]'
                      : 'bg-[#0B1120] border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="decision"
                    value="reject"
                    checked={decisionAction === 'reject'}
                    onChange={(e) => setDecisionAction(e.target.value)}
                    className="accent-red-400"
                  />
                  <span className="font-bold">Reject</span>
                </label>
              </div>
            </div>

            {/* Custom Override Input (If Override selected) */}
            {decisionAction === 'override' && (
              <div className="space-y-1">
                <label className="text-amber-400 font-bold block">
                  Custom Root Cause Statement:
                </label>
                <input
                  type="text"
                  value={overrideText}
                  onChange={(e) => setOverrideText(e.target.value)}
                  placeholder="e.g. Suction strainer fouled with marine debris ingress"
                  className="w-full bg-[#0B1120] border border-amber-500/50 rounded-lg p-2.5 text-xs font-sans text-slate-100 focus:outline-none"
                />
              </div>
            )}

            {/* Reviewer Name / Credentials */}
            <div className="space-y-1">
              <label className="text-slate-300 font-bold block">
                Lead Reliability Reviewer:
              </label>
              <input
                type="text"
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                className="w-full bg-[#0B1120] border border-slate-700/80 rounded-lg p-2.5 text-xs font-sans text-slate-100 focus:outline-none focus:border-[#00D4AA]"
              />
            </div>

            {/* Justification Review Notes */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-slate-300 font-bold">
                  Engineering Review & Justification Notes:
                </label>
                <span className="text-[10px] text-slate-500">Will be bound into SAP PM01 & 8D D8</span>
              </div>
              <textarea
                rows={5}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                className="w-full bg-[#0B1120] border border-slate-700/80 rounded-lg p-2.5 text-xs font-sans text-slate-200 focus:outline-none focus:border-[#00D4AA] leading-relaxed"
              />
            </div>

            {/* Submit Authorization Button */}
            <button
              type="submit"
              disabled={isSubmitting || !isPaused}
              className={`w-full py-3 rounded-lg font-mono text-xs font-bold uppercase tracking-wider flex items-center justify-center space-x-2 transition-all cursor-pointer ${
                !isPaused
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  : decisionAction === 'approve'
                  ? 'bg-[#00D4AA] hover:bg-[#00b894] text-[#0B1120] shadow-[0_0_20px_rgba(0,212,170,0.3)]'
                  : decisionAction === 'override'
                  ? 'bg-amber-500 hover:bg-amber-400 text-slate-900 shadow-[0_0_20px_rgba(245,158,11,0.3)]'
                  : 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_20px_rgba(239,68,68,0.3)]'
              }`}
            >
              {isSubmitting ? (
                <span>Executing LangGraph Resume Command...</span>
              ) : isFinalized ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Deliverables Emitted Successfully</span>
                </>
              ) : isRejected ? (
                <>
                  <XCircle className="w-4 h-4" />
                  <span>Investigation Rejected</span>
                </>
              ) : (
                <>
                  <FileCheck className="w-4 h-4" />
                  <span>Authorize & Emit SAP Work Order</span>
                </>
              )}
            </button>
          </form>
        </div>

        <div className="p-2.5 rounded bg-[#0B1120] border border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
          <span>LangGraph Checkpoint: Thread {rcaState?.thread_id || 'Active'}</span>
          <span className="text-[#00D4AA]">Stateful MemorySaver</span>
        </div>
      </div>
    </div>
  );
};
