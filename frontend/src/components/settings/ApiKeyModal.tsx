import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Key,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  Save,
  Trash2,
  Activity,
  ClipboardPaste,
  ChevronDown,
  ChevronUp,
  Sparkles,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { ApiKeyStatus, ApiKeyTestResponse } from '../../types';
import { saveApiKey, deleteApiKey, testApiKeyConnection } from '../../api';

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiKeyStatus: ApiKeyStatus | null;
  onApiKeyUpdated: (status: ApiKeyStatus) => void;
}

export const ApiKeyModal: React.FC<ApiKeyModalProps> = ({
  isOpen,
  onClose,
  apiKeyStatus,
  onApiKeyUpdated,
}) => {
  const [inputKey, setInputKey] = useState<string>('');
  const [showKey, setShowKey] = useState<boolean>(false);
  const [baseUrl, setBaseUrl] = useState<string>('https://api.deepseek.com/v1');
  const [selectedModel, setSelectedModel] = useState<string>('deepseek-flash');
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // Status & Feedback states
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [statusNotification, setStatusNotification] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);
  const [testResult, setTestResult] = useState<ApiKeyTestResponse | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  // Sync state from active status when opening
  useEffect(() => {
    if (isOpen && apiKeyStatus) {
      if (apiKeyStatus.base_url) setBaseUrl(apiKeyStatus.base_url);
      if (apiKeyStatus.model) setSelectedModel(apiKeyStatus.model);
      setStatusNotification(null);
      setTestResult(null);
      setInputKey('');
    }
  }, [isOpen, apiKeyStatus]);

  if (!isOpen) return null;

  // Handler: Execute Save to .env
  const executeSave = async (keyToSave: string, isAutoPasted = false) => {
    const trimmed = keyToSave.trim();
    if (!trimmed) {
      setStatusNotification({
        type: 'error',
        message: 'Please provide a valid API key string.',
      });
      return;
    }

    setIsSaving(true);
    setStatusNotification({
      type: 'info',
      message: isAutoPasted
        ? 'Pasted key detected · Auto-saving directly into .env...'
        : 'Saving key to .env file and updating runtime engine...',
    });
    setTestResult(null);

    try {
      const res = await saveApiKey({
        api_key: trimmed,
        base_url: baseUrl.trim() || undefined,
        model: selectedModel || undefined,
      });

      onApiKeyUpdated(res);
      setInputKey('');
      setStatusNotification({
        type: 'success',
        message: `✓ API key successfully saved into ${res.env_path ? '.env' : '.env file'} and activated!`,
      });
    } catch (err: any) {
      setStatusNotification({
        type: 'error',
        message: err.message || 'Failed to save API key to .env.',
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Handler: Form submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSave(inputKey);
  };

  // Handler: Paste event with auto-save
  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text');
    if (pasted && pasted.trim().length > 5) {
      setInputKey(pasted.trim());
      // Trigger automatic save to .env
      executeSave(pasted.trim(), true);
    }
  };

  // Handler: Clipboard button paste
  const handleClipboardPasteClick = async () => {
    try {
      if (navigator?.clipboard?.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text.trim().length > 5) {
          setInputKey(text.trim());
          executeSave(text.trim(), true);
        } else {
          setStatusNotification({
            type: 'error',
            message: 'Clipboard is empty or does not contain a valid API key.',
          });
        }
      } else {
        inputRef.current?.focus();
        setStatusNotification({
          type: 'info',
          message: 'Clipboard API not supported in this browser. Please press Ctrl+V directly into the input.',
        });
      }
    } catch (err: any) {
      inputRef.current?.focus();
      setStatusNotification({
        type: 'error',
        message: 'Unable to access clipboard. Please paste directly (Ctrl+V) into the input.',
      });
    }
  };

  // Handler: Test connection
  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    setStatusNotification(null);

    try {
      const res = await testApiKeyConnection({
        api_key: inputKey.trim() || undefined,
        base_url: baseUrl.trim() || undefined,
        model: selectedModel || undefined,
      });

      setTestResult(res);
      if (res.success) {
        setStatusNotification({
          type: 'success',
          message: `✓ Connection Successful: DeepSeek API responded with '${res.response || 'DEEPSEEK_ONLINE'}'`,
        });
      } else {
        setStatusNotification({
          type: 'error',
          message: `Connection failed: ${res.message || 'Unable to authenticate with DeepSeek API.'}`,
        });
      }
    } catch (err: any) {
      setStatusNotification({
        type: 'error',
        message: err.message || 'Connectivity check failed.',
      });
    } finally {
      setIsTesting(false);
    }
  };

  // Handler: Delete / Remove key
  const handleDeleteKey = async () => {
    if (!window.confirm('Are you sure you want to remove the DeepSeek API key from .env? The system will revert to high-fidelity deterministic simulation mode.')) {
      return;
    }

    setIsDeleting(true);
    setStatusNotification(null);
    setTestResult(null);

    try {
      const res = await deleteApiKey();
      setInputKey('');
      onApiKeyUpdated({
        has_key: false,
        masked_key: '',
        provider: 'DeepSeek',
        base_url: baseUrl,
        model: selectedModel,
        is_live: false,
        status: 'SIMULATION',
      });
      setStatusNotification({
        type: 'info',
        message: res.message || 'API key removed from .env. System running in simulation mode.',
      });
    } catch (err: any) {
      setStatusNotification({
        type: 'error',
        message: err.message || 'Failed to remove API key.',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const isConfigured = Boolean(apiKeyStatus?.has_key);

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-center text-purple-600 shadow-xs">
              <Key className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 font-mono uppercase tracking-wide flex items-center space-x-2">
                <span>DeepSeek API Configuration</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-sans font-semibold bg-purple-100 text-purple-700 border border-purple-200">
                  .env Auto-Sync
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                Configure API credentials for live autonomous RCA and AI Diagnostic Copilot
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-4">
          {/* Status Pill Card */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-2 text-xs font-mono">
            <div className="flex justify-between items-center">
              <span className="text-slate-600 font-medium">Active Engine Mode:</span>
              {isConfigured ? (
                <span className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-300 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>● Live DeepSeek API (Active)</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-300 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                  <span>○ Deterministic Simulation Mode</span>
                </span>
              )}
            </div>

            <div className="flex justify-between items-center text-slate-500 pt-1 border-t border-slate-200/60">
              <span>Saved Key in .env:</span>
              <span className="font-semibold text-slate-800 font-mono">
                {isConfigured ? apiKeyStatus?.masked_key : 'None (using test simulation)'}
              </span>
            </div>

            <div className="flex justify-between items-center text-slate-500">
              <span>Persistence Target:</span>
              <span className="font-mono text-[11px] text-slate-600 truncate max-w-[280px]" title={apiKeyStatus?.env_path}>
                {apiKeyStatus?.env_path ? '.env (Root Workspace)' : '.env'}
              </span>
            </div>
          </div>

          {/* Status Notifications */}
          {statusNotification && (
            <div
              className={`p-3 rounded-xl border text-xs font-mono flex items-start space-x-2 transition-all ${
                statusNotification.type === 'success'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : statusNotification.type === 'error'
                  ? 'bg-rose-50 border-rose-200 text-rose-800'
                  : 'bg-blue-50 border-blue-200 text-blue-800'
              }`}
            >
              {statusNotification.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
              ) : statusNotification.type === 'error' ? (
                <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              ) : (
                <RefreshCw className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5 animate-spin" />
              )}
              <div className="flex-1">{statusNotification.message}</div>
            </div>
          )}

          {/* Test Result Metadata (if tested) */}
          {testResult && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono space-y-1">
              <div className="flex items-center justify-between font-bold text-slate-700">
                <span>Diagnostic Ping:</span>
                <span className={testResult.success ? 'text-emerald-600' : 'text-rose-600'}>
                  {testResult.status}
                </span>
              </div>
              {testResult.response && (
                <div className="text-[11px] text-slate-600">
                  <strong>API Echo:</strong> {testResult.response}
                </div>
              )}
            </div>
          )}

          {/* Input & Auto-Save Form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold text-slate-700 font-mono flex items-center space-x-1.5">
                  <Key className="w-3.5 h-3.5 text-purple-600" />
                  <span>DeepSeek API Key</span>
                  <span className="text-[10px] text-slate-400 font-normal">(DEEPSEEK_API_KEY)</span>
                </label>
                <div className="flex items-center space-x-1">
                  <span className="text-[10px] font-sans text-teal-600 bg-teal-50 border border-teal-200 px-1.5 py-0.2 rounded font-medium">
                    ⚡ Auto-saves on paste
                  </span>
                </div>
              </div>

              <div className="relative flex items-center">
                <input
                  ref={inputRef}
                  type={showKey ? 'text' : 'password'}
                  value={inputKey}
                  onChange={(e) => setInputKey(e.target.value)}
                  onPaste={handlePaste}
                  placeholder={
                    isConfigured
                      ? `Key active (${apiKeyStatus?.masked_key}). Paste new key to update...`
                      : 'Paste your sk-... key here (auto-saves instantly)'
                  }
                  className="w-full pl-3 pr-24 py-2 border border-slate-300 rounded-xl text-xs font-mono focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 outline-hidden transition-all bg-white"
                  autoFocus
                />

                <div className="absolute right-1.5 flex items-center space-x-1">
                  {/* Show/Hide password toggle */}
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                    title={showKey ? 'Hide key' : 'Show key'}
                  >
                    {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>

                  {/* Clipboard Paste Quick Action */}
                  <button
                    type="button"
                    onClick={handleClipboardPasteClick}
                    disabled={isSaving}
                    className="px-2 py-1 text-[11px] font-mono bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 rounded-lg transition-colors flex items-center space-x-1 cursor-pointer"
                    title="Paste directly from clipboard and auto-save"
                  >
                    <ClipboardPaste className="w-3 h-3" />
                    <span>Paste</span>
                  </button>
                </div>
              </div>

              <p className="mt-1.5 text-[11px] text-slate-500 flex items-center space-x-1">
                <span>Copy-pasting directly updates your</span>
                <code className="px-1 py-0.2 bg-slate-100 border border-slate-200 rounded text-[10px] font-mono text-slate-700">
                  .env
                </code>
                <span>file without restarting.</span>
              </p>
            </div>

            {/* Action Buttons Row */}
            <div className="flex items-center justify-between pt-1 gap-2">
              <div className="flex items-center space-x-2">
                {/* Test Connection Button */}
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={isTesting || (!isConfigured && !inputKey.trim())}
                  className="px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 rounded-xl text-xs font-mono font-medium flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-40"
                  title="Ping DeepSeek API to verify credential validity"
                >
                  <Activity className={`w-3.5 h-3.5 text-slate-500 ${isTesting ? 'animate-spin' : ''}`} />
                  <span>{isTesting ? 'Testing...' : 'Test Connection'}</span>
                </button>

                {/* Remove Key Button */}
                {isConfigured && (
                  <button
                    type="button"
                    onClick={handleDeleteKey}
                    disabled={isDeleting}
                    className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-700 rounded-xl text-xs font-mono font-medium flex items-center space-x-1.5 transition-colors cursor-pointer disabled:opacity-40"
                    title="Remove key from .env and revert to simulation mode"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-rose-500" />
                    <span>{isDeleting ? 'Removing...' : 'Remove Key'}</span>
                  </button>
                )}
              </div>

              {/* Explicit Save Button */}
              <button
                type="submit"
                disabled={isSaving || !inputKey.trim()}
                className="px-4 py-1.5 bg-purple-600 hover:bg-purple-700 active:bg-purple-800 text-white rounded-xl text-xs font-mono font-semibold flex items-center space-x-1.5 shadow-xs transition-colors cursor-pointer disabled:opacity-40"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{isSaving ? 'Saving to .env...' : 'Save to .env'}</span>
              </button>
            </div>

            {/* Collapsible Advanced Options */}
            <div className="pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center justify-between w-full text-left py-1 text-xs font-mono text-slate-500 hover:text-slate-800 transition-colors cursor-pointer"
              >
                <span className="flex items-center space-x-1">
                  <span>Advanced Settings (Model & Base URL)</span>
                </span>
                {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {showAdvanced && (
                <div className="mt-2.5 p-3.5 bg-slate-50/80 border border-slate-200 rounded-xl space-y-3 animate-in fade-in duration-100 text-xs font-mono">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      DeepSeek Model
                    </label>
                    <select
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:ring-2 focus:ring-purple-500/20 outline-hidden"
                    >
                      <option value="deepseek-flash">deepseek-flash (MoE V4.1 Flash · High-Speed Reasoning)</option>
                      <option value="deepseek-chat">deepseek-chat (General Diagnostic Assistant)</option>
                      <option value="deepseek-reasoner">deepseek-reasoner (R1 Deep Deliberation with Chain-of-Thought)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      API Base URL
                    </label>
                    <input
                      type="text"
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="https://api.deepseek.com/v1"
                      className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:ring-2 focus:ring-purple-500/20 outline-hidden"
                    />
                    <span className="text-[10px] text-slate-400 mt-0.5 block">
                      Change only if using custom reverse proxy or local model gateway.
                    </span>
                  </div>
                </div>
              )}
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
          <a
            href="https://platform.deepseek.com/api_keys"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1 text-purple-600 hover:text-purple-700 hover:underline font-mono text-[11px]"
          >
            <span>Get DeepSeek API Key</span>
            <ExternalLink className="w-3 h-3" />
          </a>

          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1 text-xs font-mono text-slate-600 hover:text-slate-800 hover:bg-slate-200/60 rounded-lg transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
