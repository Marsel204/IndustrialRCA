import React, { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';
import { Radio, Waves } from 'lucide-react';
import { TelemetryData, SpectrumData } from '../../types';

interface TelemetryAnalyticsTabProps {
  telemetry: TelemetryData | null;
  spectrum: SpectrumData | null;
  activeScenarioId?: string;
}

const EMPTY_TIMESTAMPS: number[] = [];
const EMPTY_SERIES: Record<string, number[]> = {};

export const TelemetryAnalyticsTab: React.FC<TelemetryAnalyticsTabProps> = ({
  telemetry,
  spectrum,
}) => {
  const timestamps = telemetry?.timestamps || EMPTY_TIMESTAMPS;
  const series = telemetry?.series || EMPTY_SERIES;

  // Formatter for timestamp seconds to mm:ss
  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `T+${m}m${s.toString().padStart(2, '0')}s`;
  };

  // Synchronize timeseries charts group for crosshair and zoom linking
  const onTelemetryChartReady = useCallback((instance: any) => {
    if (instance) {
      instance.group = 'telemetry_sync';
      echarts.connect('telemetry_sync');
    }
  }, []);

  // Base options template for crisp light ECharts
  const baseChartTheme = useMemo(
    () => ({
      backgroundColor: '#FFFFFF',
      textStyle: { fontFamily: 'JetBrains Mono, monospace', color: '#334155' },
      grid: { top: 35, right: 20, bottom: 25, left: 55 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#E2E8F0',
        textStyle: { color: '#0F172A', fontSize: 11 },
        extraCssText: 'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-radius: 8px;',
        axisPointer: { type: 'cross', lineStyle: { color: '#94A3B8', type: 'dashed' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100, xAxisIndex: 0 },
      ],
    }),
    []
  );

  // 1. Bearing Temp Chart
  const bearingTempOption = useMemo(() => {
    const data = series['TI-301-DE'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'TI-301-DE · Drive-End Bearing Temperature (°C)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 40,
        max: 100,
        axisLabel: { formatter: '{value}°C', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Bearing Temp',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#DC2626' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(220, 38, 38, 0.18)' },
                { offset: 1, color: 'rgba(220, 38, 38, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 90.0,
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'Trip 90°C', position: 'insideEndTop', color: '#DC2626' },
              },
              {
                yAxis: 80.0,
                name: 'Alarm Limit',
                lineStyle: { color: '#D97706', type: 'dotted', width: 1.5 },
                label: { formatter: 'Alarm 80°C', position: 'insideEndTop', color: '#D97706' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 2. Vibration RMS Chart
  const vibrationOption = useMemo(() => {
    const data = series['VI-301-R'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'VI-301-R · Radial Vibration Velocity (mm/s RMS)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 14,
        axisLabel: { formatter: '{value}', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Vibration RMS',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#7C3AED' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(124, 58, 237, 0.18)' },
                { offset: 1, color: 'rgba(124, 58, 237, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 7.10,
                name: 'ISO Zone D Trip',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'Zone D Trip 7.1 mm/s', position: 'insideEndTop', color: '#DC2626' },
              },
              {
                yAxis: 4.50,
                name: 'Zone C Alarm',
                lineStyle: { color: '#D97706', type: 'dotted', width: 1.5 },
                label: { formatter: 'Zone C Alarm 4.5 mm/s', position: 'insideEndTop', color: '#D97706' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 3. Strainer Delta-P Chart
  const strainerDpOption = useMemo(() => {
    const data = series['DPS-30101'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'DPS-30101 · Suction Strainer STR-301A Delta-P (bar)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 2.2,
        axisLabel: { formatter: '{value} bar', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Strainer Delta-P',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#D97706' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(217, 119, 6, 0.18)' },
                { offset: 1, color: 'rgba(217, 119, 6, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 1.00,
                name: 'High Alarm',
                lineStyle: { color: '#D97706', type: 'dashed', width: 2 },
                label: { formatter: 'Alarm 1.00 bar', position: 'insideEndTop', color: '#D97706' },
              },
              {
                yAxis: 1.80,
                name: 'Trip Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 1.5 },
                label: { formatter: 'Trip 1.80 bar', position: 'insideEndTop', color: '#DC2626' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 4. Suction Pressure vs NPSHr Chart
  const suctionOption = useMemo(() => {
    const data = series['PT-30101'] || [];
    return {
      ...baseChartTheme,
      title: {
        text: 'PT-30101 · Pump Suction Pressure vs NPSHr (bar)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 3.0,
        axisLabel: { formatter: '{value} bar', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Suction Pressure',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#2563EB' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(37, 99, 235, 0.18)' },
                { offset: 1, color: 'rgba(37, 99, 235, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 1.20,
                name: 'NPSH Required Limit',
                lineStyle: { color: '#DC2626', type: 'dashed', width: 2 },
                label: { formatter: 'NPSHr 1.20 bar (Cavitation Inception)', position: 'insideEndBottom', color: '#DC2626' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 5. Motor Line Current Chart
  const motorCurrentOption = useMemo(() => {
    const data = series['IT-30101'] || [];
    return {
      ...baseChartTheme,
      grid: { top: 35, right: 20, bottom: 45, left: 55 },
      dataZoom: [
        { type: 'inside', start: 0, end: 100, xAxisIndex: 0 },
        {
          type: 'slider',
          start: 0,
          end: 100,
          xAxisIndex: 0,
          height: 16,
          bottom: 4,
          borderColor: '#E2E8F0',
          fillerColor: 'rgba(13, 148, 136, 0.12)',
          handleStyle: { color: '#0D9488', borderColor: '#CBD5E1' },
          textStyle: { color: '#334155', fontSize: 10 },
          moveHandleStyle: { color: '#94A3B8' },
        },
      ],
      title: {
        text: 'IT-30101 · Induction Motor Line Current (Amperes)',
        textStyle: { color: '#0F172A', fontSize: 12, fontWeight: 'bold' },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLabel: { formatter: (v: number) => (v % 600 === 0 ? formatTime(v) : ''), fontSize: 10, color: '#334155' },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 130,
        axisLabel: { formatter: '{value} A', fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Motor Current',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 2, color: '#0D9488' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(13, 148, 136, 0.15)' },
                { offset: 1, color: 'rgba(13, 148, 136, 0.0)' },
              ],
            },
          },
          markLine: {
            symbol: 'none',
            data: [
              {
                yAxis: 115.0,
                name: 'Continuous FLA',
                lineStyle: { color: '#D97706', type: 'dashed', width: 1.5 },
                label: { formatter: 'Rated FLA 115.0 A', position: 'insideEndTop', color: '#D97706' },
              },
            ],
          },
          data,
        },
      ],
    };
  }, [baseChartTheme, series, timestamps]);

  // 6. 20 kHz Vibration FFT Spectrum Chart
  const fftSpectrumOption = useMemo(() => {
    if (!spectrum) return null;
    const freqs = spectrum.frequencies || [];
    const mags = spectrum.magnitudes || [];
    const dataPairs = freqs.map((f, i) => [f, mags[i]]);

    const shaft1x = spectrum.shaft_1x_hz || 49.7;
    const shaft2x = spectrum.shaft_2x_hz || 99.3;

    return {
      backgroundColor: '#FFFFFF',
      textStyle: { fontFamily: 'JetBrains Mono, monospace', color: '#334155' },
      grid: { top: 50, right: 30, bottom: 40, left: 60 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#E2E8F0',
        textStyle: { color: '#0F172A', fontSize: 11 },
        extraCssText: 'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-radius: 8px;',
        formatter: (params: any[]) => {
          const item = params[0];
          const val = Array.isArray(item.value) ? item.value : [item.name, item.value];
          return `<div class="font-mono text-xs"><b>${val[0]} Hz</b>: ${val[1]} mm/s</div>`;
        },
      },
      title: {
        text: '20 kHz Vibration Velocity FFT Spectrum (0 - 10,000 Hz)',
        subtext: 'Discrete Shaft Harmonics (1X: 49.7 Hz, 2X: 99.3 Hz) vs High-Frequency Cavitation Noise Floor (2.0 - 8.0 kHz)',
        textStyle: { color: '#0F172A', fontSize: 13, fontWeight: 'bold' },
        subtextStyle: { color: '#475569', fontSize: 10 },
        left: 10,
        top: 8,
      },
      xAxis: {
        type: 'value',
        min: 0,
        max: 10000,
        name: 'Frequency (Hz)',
        nameLocation: 'middle',
        nameGap: 25,
        nameTextStyle: { color: '#334155' },
        axisLabel: {
          formatter: (val: number) => (val % 1000 === 0 ? `${val / 1000}k` : ''),
          fontSize: 10,
          color: '#334155',
        },
        axisLine: { lineStyle: { color: '#CBD5E1' } },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      yAxis: {
        type: 'value',
        name: 'Amplitude (mm/s)',
        nameTextStyle: { color: '#334155' },
        axisLabel: { fontSize: 10, color: '#334155' },
        splitLine: { lineStyle: { color: '#F1F5F9' } },
      },
      series: [
        {
          name: 'Spectral Amplitude',
          type: 'line',
          showSymbol: false,
          sampling: 'lttb',
          lineStyle: { width: 1.5, color: '#0284C7' },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(2, 132, 199, 0.25)' },
                { offset: 1, color: 'rgba(2, 132, 199, 0.01)' },
              ],
            },
          },
          markArea: {
            itemStyle: {
              color: 'rgba(220, 38, 38, 0.08)',
              borderWidth: 1,
              borderColor: 'rgba(220, 38, 38, 0.25)',
            },
            data: [
              [
                {
                  name: 'Broadband Cavitation Acoustic Floor (2.0 - 8.0 kHz)',
                  xAxis: 2000,
                  label: {
                    position: 'top',
                    color: '#DC2626',
                    fontSize: 10,
                    fontFamily: 'JetBrains Mono',
                  },
                },
                { xAxis: 8000 },
              ],
            ],
          },
          markPoint: {
            symbol: 'pin',
            symbolSize: 35,
            itemStyle: { color: '#D97706' },
            data: [
              {
                name: '1X Running Speed',
                coord: [shaft1x, spectrum.analysis?.peak_1x_amplitude_mms || 2.8],
                value: `1X (${shaft1x} Hz)`,
              },
              {
                name: '2X Harmonic',
                coord: [shaft2x, spectrum.analysis?.peak_2x_amplitude_mms || 0.4],
                value: `2X (${shaft2x} Hz)`,
              },
            ],
          },
          data: dataPairs,
        },
      ],
    };
  }, [spectrum]);

  return (
    <div className="space-y-4">
      {/* Overview Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-teal-50 text-teal-600 border border-teal-100">
            <Waves className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold font-mono text-slate-800 uppercase">
              High-Frequency Synchronized Telemetry Analytics
            </div>
            <div className="text-[11px] text-slate-500">
              60-minute interval (3,600 samples at 1 Hz) + 20,000-point 20 kHz Piezoelectric FFT
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-700">
            Points: <strong className="text-teal-700">{timestamps.length.toLocaleString()}</strong>
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-700">
            Engine: <strong className="text-blue-700">ECharts Canvas (60 FPS)</strong>
          </span>
        </div>
      </div>

      {/* 20 kHz FFT Vibration Spectrum Panel */}
      {spectrum && fftSpectrumOption && (
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
              opts={{ renderer: 'canvas' }}
            />
          </div>

          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 flex items-start space-x-2">
            <span className="text-teal-700 font-bold">FFT Diagnosis:</span>
            <span>{spectrum.analysis?.diagnosis}</span>
          </div>
        </div>
      )}

      {/* 5 Core Process & Electrical Timeseries Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Chart 1: Bearing Temp */}
        <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
          <div className="h-[200px] w-full">
            <ReactECharts
              option={bearingTempOption}
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
              onChartReady={onTelemetryChartReady}
            />
          </div>
        </div>

        {/* Chart 2: Vibration RMS */}
        <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
          <div className="h-[200px] w-full">
            <ReactECharts
              option={vibrationOption}
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
              onChartReady={onTelemetryChartReady}
            />
          </div>
        </div>

        {/* Chart 3: Strainer Delta-P */}
        <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
          <div className="h-[200px] w-full">
            <ReactECharts
              option={strainerDpOption}
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
              onChartReady={onTelemetryChartReady}
            />
          </div>
        </div>

        {/* Chart 4: Suction Pressure vs NPSHr */}
        <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
          <div className="h-[200px] w-full">
            <ReactECharts
              option={suctionOption}
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
              onChartReady={onTelemetryChartReady}
            />
          </div>
        </div>

        {/* Chart 5: Motor Line Current (Full Width) */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-3 shadow-xs">
          <div className="h-[200px] w-full">
            <ReactECharts
              option={motorCurrentOption}
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
              onChartReady={onTelemetryChartReady}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
