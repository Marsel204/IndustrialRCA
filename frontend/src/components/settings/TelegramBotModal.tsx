import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Send,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  Save,
  Trash2,
  Activity,
  ClipboardPaste,
  RefreshCw,
  ExternalLink,
  Users,
  Bell,
  Sparkles,
  Bot,
  Layers,
} from 'lucide-react';
import { TelegramBotStatus } from '../../types';
import { saveBotSettings, sendBotTestAlert } from '../../api';

interface TelegramBotModalProps {
  isOpen: boolean;
  onClose: () => void;
  botStatus: TelegramBotStatus | null;
  onBotStatusUpdated: (status: TelegramBotStatus) => void;
}

export const TelegramBotModal: React.FC<TelegramBotModalProps> = ({
  isOpen,
  onClose,
  botStatus,
  onBotStatusUpdated,
}) => {
  const [inputToken, setInputToken] = useState<string>('');
  const [showToken, setShowToken] = useState<boolean>(false);
  const [defaultChatId, setDefaultChatId] = useState<string>('');
  const [dashboardUrl, setDashboardUrl] = useState<string>('http://localhost:5173');

  // Status & Feedback states
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [statusNotification, setStatusNotification] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  // Sync state from active status when opening
  useEffect(() => {
    if (isOpen && botStatus) {
      if (botStatus.default_chat_id) setDefaultChatId(botStatus.default_chat_id);
      if (botStatus.dashboard_url) setDashboardUrl(botStatus.dashboard_url);
      setStatusNotification(null);
      setInputToken('');
    }
  }, [isOpen, botStatus]);

  if (!isOpen) return null;

  // Handler: Save Settings
  const executeSave = async (tokenToSave?: string) => {
    const token = (tokenToSave !== undefined ? tokenToSave : inputToken).trim();

    setIsSaving(true);
    setStatusNotification({
      type: 'info',
      message: 'Saving Telegram Bot configuration into .env and starting polling loop...',
    });

    try {
      const res = await saveBotSettings({
        bot_token: token || undefined,
        default_chat_id: defaultChatId.trim() || undefined,
        dashboard_url: dashboardUrl.trim() || undefined,
      });

      onBotStatusUpdated(res);
      setInputToken('');
      setStatusNotification({
        type: 'success',
        message: '✓ Telegram Bot settings saved and polling service active!',
      });
    } catch (err: any) {
      setStatusNotification({
        type: 'error',
        message: `Failed to save bot settings: ${err.message || String(err)}`,
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Handler: Clear / Disconnect Bot
  const handleClearToken = async () => {
    if (!window.confirm('Are you sure you want to disconnect and unconfigure the Telegram Bot?')) {
      return;
    }

    setIsSaving(true);
    setStatusNotification({
      type: 'info',
      message: 'Disconnecting Telegram Bot...',
    });

    try {
      const res = await saveBotSettings({
        bot_token: '',
      });
      onBotStatusUpdated(res);
      setInputToken('');
      setStatusNotification({
        type: 'success',
        message: '✓ Telegram Bot disconnected.',
      });
    } catch (err: any) {
      setStatusNotification({
        type: 'error',
        message: `Failed to disconnect bot: ${err.message || String(err)}`,
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Handler: Test Alert
  const handleSendTestAlert = async () => {
    setIsTesting(true);
    setStatusNotification({
      type: 'info',
      message: 'Dispatching sample trip notification with waveform to subscribers...',
    });

    try {
      const res = await sendBotTestAlert();
      setStatusNotification({
        type: 'success',
        message: `✓ Test alert delivered successfully to ${res.recipients_reached}/${res.recipients_total} subscribers!`,
      });
    } catch (err: any) {
      setStatusNotification({
        type: 'error',
        message: `Test alert delivery failed: ${err.message || String(err)}`,
      });
    } finally {
      setIsTesting(false);
    }
  };

  // Handler: Quick Paste
  const handlePasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      const cleaned = text.trim();
      if (cleaned) {
        setInputToken(cleaned);
        setStatusNotification({
          type: 'info',
          message: 'Token pasted from clipboard. Click "Save & Connect" to activate.',
        });
      }
    } catch {
      setStatusNotification({
        type: 'error',
        message: 'Clipboard access denied. Please paste directly into the field.',
      });
    }
  };

  const isConfigured = botStatus?.is_configured ?? false;
  const isOnline = botStatus?.status === 'ONLINE' || botStatus?.is_polling;
  const subscriberCount = botStatus?.subscribers_count ?? 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center text-sky-600 shadow-2xs">
              <Send className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <span>Telegram Bot & Mobile Alerts</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-100/70 text-sky-800 border border-sky-200">
                  Two-Way HITL
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                Machine trip alarms, in-memory waveforms, and DeepSeek AI Copilot
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {/* Status Card */}
          <div
            className={`p-3.5 rounded-lg border flex items-center justify-between transition-colors ${
              isOnline
                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950'
                : isConfigured
                ? 'bg-sky-50/70 border-sky-200 text-sky-950'
                : 'bg-amber-50/70 border-amber-200 text-amber-950'
            }`}
          >
            <div className="flex items-center space-x-3">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  isOnline
                    ? 'bg-emerald-100 text-emerald-700'
                    : isConfigured
                    ? 'bg-sky-100 text-sky-700'
                    : 'bg-amber-100 text-amber-700'
                }`}
              >
                {isOnline ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : isConfigured ? (
                  <Activity className="w-4 h-4" />
                ) : (
                  <AlertCircle className="w-4 h-4" />
                )}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold font-mono tracking-tight">
                    {isOnline ? 'TELEGRAM BOT ONLINE' : isConfigured ? 'BOT READY' : 'BOT UNCONFIGURED'}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold uppercase ${
                      isOnline
                        ? 'bg-emerald-200 text-emerald-800'
                        : isConfigured
                        ? 'bg-sky-200 text-sky-800'
                        : 'bg-amber-200 text-amber-800'
                    }`}
                  >
                    {botStatus?.status || 'OFFLINE'}
                  </span>
                </div>
                <p className="text-[11px] opacity-80 mt-0.5">
                  {isConfigured
                    ? `Token: ${botStatus?.token_masked || 'Active'} · ${subscriberCount} subscribed chat(s)`
                    : 'Configure your bot token from @BotFather to enable mobile alerting'}
                </p>
              </div>
            </div>

            {/* Test Alert Button */}
            {isConfigured && (
              <button
                type="button"
                onClick={handleSendTestAlert}
                disabled={isTesting || subscriberCount === 0}
                className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-all cursor-pointer ${
                  subscriberCount === 0
                    ? 'opacity-60 cursor-not-allowed bg-slate-100 text-slate-400 border-slate-200'
                    : 'bg-white hover:bg-slate-50 text-slate-700 border-slate-200 shadow-2xs'
                }`}
                title={subscriberCount === 0 ? 'Send /start in Telegram first to subscribe' : 'Send test alert'}
              >
                <Send className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : 'text-sky-600'}`} />
                <span>{isTesting ? 'Sending...' : 'Test Alert'}</span>
              </button>
            )}
          </div>

          {/* Inline Notification Banner */}
          {statusNotification && (
            <div
              className={`p-3 rounded-lg border text-xs flex items-start space-x-2 animate-in fade-in duration-200 ${
                statusNotification.type === 'success'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : statusNotification.type === 'error'
                  ? 'bg-rose-50 border-rose-200 text-rose-800'
                  : 'bg-sky-50 border-sky-200 text-sky-800'
              }`}
            >
              {statusNotification.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              ) : statusNotification.type === 'error' ? (
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              ) : (
                <Activity className="w-4 h-4 shrink-0 mt-0.5 animate-spin" />
              )}
              <span className="leading-relaxed">{statusNotification.message}</span>
            </div>
          )}

          {/* Token Input Section */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="telegramTokenInput" className="text-xs font-semibold text-slate-700 flex items-center space-x-1">
                <span>Telegram Bot API Token</span>
                <span className="text-rose-500">*</span>
              </label>
              <button
                type="button"
                onClick={handlePasteFromClipboard}
                className="text-[11px] text-sky-600 hover:text-sky-700 flex items-center space-x-1 font-medium cursor-pointer"
              >
                <ClipboardPaste className="w-3 h-3" />
                <span>Paste from Clipboard</span>
              </button>
            </div>

            <div className="relative flex items-center">
              <input
                id="telegramTokenInput"
                ref={inputRef}
                type={showToken ? 'text' : 'password'}
                value={inputToken}
                onChange={(e) => setInputToken(e.target.value)}
                placeholder={botStatus?.token_masked || 'e.g. 789123456:AAFlkj...'}
                className="w-full px-3 py-2 pr-16 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all"
              />
              <div className="absolute right-2 flex items-center space-x-1">
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="p-1 text-slate-400 hover:text-slate-600 cursor-pointer rounded"
                  title={showToken ? 'Hide token' : 'Show token'}
                >
                  {showToken ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <p className="text-[11px] text-slate-500 flex items-center gap-1">
              <span>Get your free token from</span>
              <a
                href="https://t.me/BotFather"
                target="_blank"
                rel="noreferrer"
                className="text-sky-600 hover:underline font-semibold inline-flex items-center gap-0.5"
              >
                <span>@BotFather</span>
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
              <span>(send <code>/newbot</code>)</span>
            </p>
          </div>

          {/* Optional Default Chat ID */}
          <div className="space-y-1.5">
            <label htmlFor="telegramChatIdInput" className="text-xs font-semibold text-slate-700 flex items-center justify-between">
              <span>Default Alert Chat / Channel ID (Optional)</span>
              <span className="text-[10px] text-slate-400 font-normal">Auto-registered on /start</span>
            </label>
            <input
              id="telegramChatIdInput"
              type="text"
              value={defaultChatId}
              onChange={(e) => setDefaultChatId(e.target.value)}
              placeholder="e.g. 123456789 or -100123456789 (Channel)"
              className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all"
            />
            <p className="text-[11px] text-slate-500">
              Any operator who messages <code>/start</code> to your bot is automatically registered for trip alerts.
            </p>
          </div>

          {/* Active Subscribers List */}
          {botStatus && botStatus.subscribers && botStatus.subscribers.length > 0 && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-sky-600" />
                  <span>Subscribed Alert Recipients ({botStatus.subscribers.length})</span>
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto pt-1">
                {botStatus.subscribers.map((id) => (
                  <span
                    key={id}
                    className="px-2 py-0.5 bg-white border border-slate-200 rounded text-[10px] font-mono text-slate-600 shadow-2xs"
                  >
                    Chat ID: {id}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Commands Quick-Guide */}
          <div className="p-3 bg-sky-50/50 rounded-lg border border-sky-100 text-[11px] text-slate-600 space-y-1">
            <span className="font-semibold text-sky-900 block">⚡ Quick Commands in Telegram:</span>
            <div className="grid grid-cols-2 gap-1 text-[10px] font-mono text-slate-700">
              <div><code>/status</code> — Real-time telemetry</div>
              <div><code>/chart</code> — Waveform plot</div>
              <div><code>/rca</code> — 5-Whys diagnosis</div>
              <div><code>/alarms</code> — Active trip state</div>
            </div>
            <p className="text-[10px] text-slate-500 mt-1">
              💬 Operators can also type plain English questions answered by DeepSeek AI grounded in live telemetry!
            </p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-5 py-3.5 border-t border-slate-100 bg-slate-50/70">
          <div>
            {isConfigured && (
              <button
                type="button"
                onClick={handleClearToken}
                disabled={isSaving}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Disconnect</span>
              </button>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => executeSave()}
              disabled={isSaving}
              className="flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-sky-600 hover:bg-sky-700 shadow-xs hover:shadow-sm transition-all cursor-pointer disabled:opacity-50"
            >
              <Save className={`w-3.5 h-3.5 ${isSaving ? 'animate-spin' : ''}`} />
              <span>{isSaving ? 'Connecting...' : 'Save & Connect'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
