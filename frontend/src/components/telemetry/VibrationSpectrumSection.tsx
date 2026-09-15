import React from 'react';
import ReactECharts from 'echarts-for-react';
import { Radio } from 'lucide-react';
import { SpectrumData } from '../../types';

interface VibrationSpectrumSectionProps {
  spectrum: SpectrumData | null;
  fftSpectrumOption: any;
  echartsOpts?: { renderer: 'canvas' | 'svg' };
}

export const VibrationSpectrumSection: React.FC<VibrationSpectrumSectionProps> = ({
  spectrum,
  fftSpectrumOption,
  echartsOpts = { renderer: 'canvas' },
}) => {
  if (!spectrum || !fftSpectrumOption) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
        <div className="flex items-center space-x-2">
          <Radio className="w-4 h-4 text-purple-600" />
          <span className="font-mono text-xs font-bold text-slate-900">
            Acoustic Frequency Decomposition (FFT)
          </span>
        </div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span
            className={`px-2 py-0.5 rounded font-bold ${
              spectrum.analysis?.cavitation_detected
                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
            }`}
          >
            {spectrum.analysis?.cavitation_detected ? '🚨 CAVITATION CONFIRMED' : '✓ HEALTHY BASELINE'}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-600">
            Broadband Ratio: <strong className="text-purple-700">{spectrum.analysis?.broadband_cavitation_ratio_pct}%</strong>
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-600">
            Overall RMS: <strong className="text-amber-700">{spectrum.analysis?.overall_rms} mm/s</strong>
          </span>
        </div>
      </div>

      <div className="h-[240px] w-full">
        <ReactECharts
          option={fftSpectrumOption}
          style={{ height: '100%', width: '100%' }}
          opts={echartsOpts}
          lazyUpdate={true}
          notMerge={false}
        />
      </div>

      <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 flex items-start space-x-2">
        <span className="text-teal-700 font-bold">FFT Diagnosis:</span>
        <span>{spectrum.analysis?.diagnosis}</span>
      </div>
    </div>
  );
};
