import React from 'react';
import { ChevronDown, ChevronRight, ExternalLink, Terminal, CheckCircle2, Loader2 } from 'lucide-react';
import { ToolExecutionItem } from '../../types';

interface ToolExecutionCardProps {
  tool: ToolExecutionItem;
  isExpanded: boolean;
  onToggle: () => void;
  onSelectInspectorTab: (tabId: string) => void;
}

export const ToolExecutionCard: React.FC<ToolExecutionCardProps> = ({
  tool,
  isExpanded,
  onToggle,
  onSelectInspectorTab,
}) => {
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden bg-white shadow-xs">
      <button
        onClick={onToggle}
        className="w-full text-left px-3 py-2 bg-slate-50/70 hover:bg-slate-100/70 transition-colors flex items-center justify-between text-xs"
      >
        <div className="flex items-center space-x-2 min-w-0">
          {tool.status === 'running' ? (
            <Loader2 className="w-3.5 h-3.5 text-teal-600 animate-spin shrink-0" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
          )}
          <span className="font-mono font-bold text-slate-800 truncate">
            {tool.name}
          </span>
          <span className="text-slate-500 font-mono text-[11px] truncate">
            {tool.summary}
          </span>
        </div>
        <div className="flex items-center space-x-2 shrink-0 ml-2">
          {tool.duration_ms && (
            <span className="text-[10px] font-mono text-slate-400">
              {tool.duration_ms}ms
            </span>
          )}
          {isExpanded ? (
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="p-3 border-t border-slate-100 space-y-2 bg-white text-xs">
          {tool.command && (
            <div className="flex items-center space-x-2 font-mono text-[11px] text-slate-600 bg-slate-50 px-2 py-1.5 rounded border border-slate-200">
              <Terminal className="w-3 h-3 text-slate-400 shrink-0" />
              <span className="overflow-x-auto select-all">{tool.command}</span>
            </div>
          )}

          {tool.logs && tool.logs.length > 0 && (
            <div className="bg-slate-900 text-slate-200 rounded p-2 font-mono text-[10px] space-y-1 max-h-28 overflow-y-auto">
              {tool.logs.map((log, idx) => (
                <div key={idx} className="leading-tight">
                  {log}
                </div>
              ))}
            </div>
          )}

          {tool.output_details && (
            <div className="bg-slate-50 p-2 rounded border border-slate-200 font-mono text-[11px] text-slate-700 overflow-x-auto">
              <pre className="text-[10px] leading-tight">
                {JSON.stringify(tool.output_details, null, 2)}
              </pre>
            </div>
          )}

          {tool.inspector_tab && (
            <div className="flex justify-end pt-1">
              <button
                onClick={() => onSelectInspectorTab(tool.inspector_tab!)}
                className="inline-flex items-center space-x-1 text-[11px] font-mono font-medium text-teal-700 hover:text-teal-800 transition-colors"
              >
                <span>{tool.tab_label || 'View in Inspector'}</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
