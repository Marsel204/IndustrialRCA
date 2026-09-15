import React, { useState } from 'react';
import {
  GitFork,
  ArrowRight,
  ChevronRight,
  ChevronDown,
  Sliders,
  Layers,
} from 'lucide-react';
import { TopologyData } from '../../types';

interface TopologyTabProps {
  topology: TopologyData | null;
}

export const TopologyTab: React.FC<TopologyTabProps> = ({ topology }) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string>('VFD_VM_01');
  const [treeExpanded, setTreeExpanded] = useState<Record<string, boolean>>({
    enterprise: true,
    site: true,
    area: true,
    unit: true,
  });

  const toggleTree = (key: string) => {
    setTreeExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const nodes = topology?.graph?.nodes || [];
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || nodes[0];

  // Control & Power Supply Branch
  const controlSupplyOrder = [
    { id: 'GRID_AC_220V', label: '220V AC Grid', sub: 'Single-Phase 50Hz' },
    { id: 'CB_01', label: 'MCCB Breaker', sub: '16A Thermal-Mag' },
    { id: 'PLC_LX_01', label: 'Wecon LX PLC', sub: 'D-Variable Logic' },
    { id: 'HMI_TOUCH_01', label: 'Operator HMI', sub: '192.168.1.104' },
  ];

  // Drive & Motion Power Branch
  const vfdPowerOrder = [
    { id: 'VFD_VM_01', label: 'Wecon VM VFD', sub: '0.75kW Inverter' },
    { id: 'DC_BUS_LINK', label: 'DC Bus Link', sub: '182V nom · 195V trip' },
    { id: 'BRK_RESISTOR_01', label: 'Braking Resistor', sub: 'P+/PB Terminals' },
    { id: 'IND_MOTOR_01', label: 'Induction Motor', sub: '4-Pole 1440 RPM' },
  ];

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
            <GitFork className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold font-mono text-slate-800 uppercase">
              ISA-95 Plant Topology & Electrical Control Graph
            </div>
            <div className="text-[11px] text-slate-500">
              Correlated Directed Traversal · Bench 01 Wecon VFD & Induction Motor Rig
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
            Root Origin: <strong>PLC_LX_01</strong>
          </span>
          <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
            Tripped Asset: <strong>VFD_VM_01</strong>
          </span>
        </div>
      </div>

      {/* Interactive Process Flow Diagram */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-800">
            Interactive Electrical & Control Diagram (Click Node to Inspect)
          </span>
          <span className="text-[11px] font-mono text-slate-500">
            220V AC Mains → PLC / HMI → Wecon VM Inverter → Induction Motor
          </span>
        </div>

        {/* Electrical & PLC Control Branch */}
        <div className="space-y-1.5">
          <span className="text-[11px] font-mono text-purple-700 font-semibold uppercase tracking-wider">
            ⚡ AC Mains Supply & PLC Control Branch (Modbus RTU / MQTT)
          </span>
          <div className="flex flex-wrap items-center gap-2">
            {controlSupplyOrder.map((item, idx) => {
              const isSelected = selectedNodeId === item.id;
              const isRoot = item.id === 'PLC_LX_01';
              return (
                <React.Fragment key={item.id}>
                  <button
                    onClick={() => setSelectedNodeId(item.id)}
                    className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer min-w-[145px] ${
                      isSelected
                        ? 'bg-purple-50 border-purple-400 ring-1 ring-purple-400/30'
                        : isRoot
                        ? 'bg-rose-50/50 border-rose-300'
                        : 'bg-slate-50/60 border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-mono text-xs font-bold text-purple-900">
                        {item.id}
                      </span>
                      <span className={`text-[9px] font-mono px-1 py-0.2 rounded font-bold ${
                        isRoot ? 'bg-rose-100 text-rose-800' : 'bg-purple-100 text-purple-700'
                      }`}>
                        {isRoot ? 'ROOT TRIGGER' : 'CONTROL'}
                      </span>
                    </div>
                    <div className="text-xs font-medium text-slate-800">{item.label}</div>
                    <div className="text-[10px] font-mono text-slate-500">{item.sub}</div>
                  </button>
                  {idx < controlSupplyOrder.length - 1 && (
                    <ArrowRight className="w-3.5 h-3.5 text-purple-300 flex-shrink-0" />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* VFD Inverter Drive & Motion Branch */}
        <div className="space-y-1.5 pt-1">
          <span className="text-[11px] font-mono text-teal-700 font-semibold uppercase tracking-wider">
            ⚙️ Wecon VM Inverter, DC Link & Induction Motor Branch
          </span>
          <div className="flex flex-wrap items-center gap-2">
            {vfdPowerOrder.map((item, idx) => {
              const isSelected = selectedNodeId === item.id;
              const isTripped = item.id === 'VFD_VM_01';

              let borderColor = 'border-slate-200';
              let badgeBg = 'bg-slate-100 text-slate-600';
              let badgeText = 'HEALTHY';
              let cardBg = 'bg-slate-50/60';

              if (isTripped) {
                borderColor = isSelected ? 'border-amber-500 ring-2 ring-amber-500/20' : 'border-amber-300';
                cardBg = 'bg-amber-50/40';
                badgeBg = 'bg-amber-100 text-amber-800';
                badgeText = 'TRIPPED ASSET';
              } else if (isSelected) {
                borderColor = 'border-blue-500 ring-2 ring-blue-500/20';
                cardBg = 'bg-blue-50/40';
              }

              return (
                <React.Fragment key={item.id}>
                  <button
                    onClick={() => setSelectedNodeId(item.id)}
                    className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer min-w-[145px] ${cardBg} ${borderColor}`}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="font-mono text-xs font-bold text-slate-900">
                        {item.id}
                      </span>
                      <span className={`text-[9px] font-mono px-1 py-0.2 rounded font-bold ${badgeBg}`}>
                        {badgeText}
                      </span>
                    </div>
                    <div className="text-xs font-medium text-slate-800">{item.label}</div>
                    <div className="text-[10px] font-mono text-slate-500">{item.sub}</div>
                  </button>
                  {idx < vfdPowerOrder.length - 1 && (
                    <div className="flex items-center space-x-0.5 flex-shrink-0">
                      <ArrowRight className="w-3.5 h-3.5 text-teal-600" />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom Grid: Node Detail Inspector + ISA-95 Tree */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Selected Asset Detail Inspector */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div className="flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-teal-600" />
              <h3 className="font-mono text-xs font-bold text-slate-900 uppercase">
                Asset Inspector: {selectedNode?.name || selectedNodeId}
              </h3>
            </div>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                selectedNode?.status === 'ROOT_CAUSE'
                  ? 'bg-rose-50 text-rose-700 border border-rose-200'
                  : selectedNode?.status === 'TRIPPED'
                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {selectedNode?.status || 'HEALTHY'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px]">Asset Tag</span>
              <span className="font-bold text-slate-900">{selectedNode?.id}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px]">ISA-95 Level</span>
              <span className="font-bold text-slate-900">Level {selectedNode?.isa95_level || 2}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px]">Equipment Type</span>
              <span className="font-bold text-slate-900">{selectedNode?.type}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
              <span className="text-slate-500 block text-[10px]">Role in Incident</span>
              <span className="font-bold text-slate-900">
                {selectedNode?.id === 'STR-301A'
                  ? 'Primary Root Cause'
                  : selectedNode?.id === 'P-301A'
                  ? 'Tripped Machinery'
                  : 'Component'}
              </span>
            </div>
          </div>

          {/* Sensors Attached */}
          <div className="space-y-1.5 pt-1">
            <div className="text-xs font-mono font-semibold text-slate-700">
              Attached Sensors & Instrumentation:
            </div>
            {selectedNode?.sensors && selectedNode.sensors.length > 0 ? (
              <div className="space-y-1">
                {selectedNode.sensors.map((sensor) => (
                  <div
                    key={sensor.tag}
                    className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono flex items-center justify-between"
                  >
                    <div>
                      <strong className="text-blue-700">{sensor.tag}</strong>
                      <span className="text-slate-700 ml-2">{sensor.description}</span>
                    </div>
                    {sensor.trip_limit && (
                      <span className="text-[10px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                        Limit: {sensor.trip_limit} {sensor.unit}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs font-mono text-slate-400 italic">
                No active analog transmitters bound directly to this passive junction node.
              </p>
            )}
          </div>
        </div>

        {/* Right: ISA-95 Hierarchical Tree */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-3">
          <div className="flex items-center space-x-2 border-b border-slate-100 pb-2.5">
            <Layers className="w-4 h-4 text-blue-600" />
            <h3 className="font-mono text-xs font-bold text-slate-900 uppercase">
              ISA-95 Enterprise Hierarchy
            </h3>
          </div>

          <div className="font-mono text-xs space-y-1.5">
            <div>
              <button
                onClick={() => toggleTree('enterprise')}
                className="flex items-center space-x-1.5 text-slate-800 font-bold hover:text-teal-700 cursor-pointer"
              >
                {treeExpanded.enterprise ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                <span>🏢 Global PetroChem Refining Corp (L5)</span>
              </button>

              {treeExpanded.enterprise && (
                <div className="ml-4 mt-1 pl-2.5 border-l border-slate-200 space-y-1.5">
                  <div>
                    <button
                      onClick={() => toggleTree('site')}
                      className="flex items-center space-x-1.5 text-blue-700 font-semibold hover:text-blue-800 cursor-pointer"
                    >
                      {treeExpanded.site ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      <span>📍 Site Alpha - Baytown Complex (L4)</span>
                    </button>

                    {treeExpanded.site && (
                      <div className="ml-4 mt-1 pl-2.5 border-l border-slate-200 space-y-1.5">
                        <div>
                          <button
                            onClick={() => toggleTree('area')}
                            className="flex items-center space-x-1.5 text-amber-700 font-semibold hover:text-amber-800 cursor-pointer"
                          >
                            {treeExpanded.area ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                            <span>⚙️ Area 03 - Steam Generation (L3)</span>
                          </button>

                          {treeExpanded.area && (
                            <div className="ml-4 mt-1 pl-2.5 border-l border-slate-200 space-y-1">
                              <div className="text-teal-700 font-semibold">
                                💧 Unit 300 - HP Boiler Feedwater (L2)
                              </div>

                              <div className="ml-3 space-y-1 text-slate-700">
                                <div className="text-slate-500 text-[10px] font-bold uppercase mt-1">
                                  Equipment Modules (L1/L2):
                                </div>
                                <div className="flex items-center space-x-2 py-0.2">
                                  <span>•</span>
                                  <span className="font-bold text-slate-800">TK-300:</span>
                                  <span className="text-slate-600">Feedwater Deaerator Vessel</span>
                                </div>
                                <div className="flex items-center space-x-2 py-0.2 text-rose-700 font-bold">
                                  <span>•</span>
                                  <span>STR-301A:</span>
                                  <span className="font-normal text-rose-800">Suction Strainer (Blinded Root Cause)</span>
                                </div>
                                <div className="flex items-center space-x-2 py-0.2">
                                  <span>•</span>
                                  <span className="font-bold text-slate-800">LINE-30101:</span>
                                  <span className="text-slate-600">Suction Feed Piping Header</span>
                                </div>
                                <div className="flex items-center space-x-2 py-0.2 text-amber-700 font-bold">
                                  <span>•</span>
                                  <span>P-301A:</span>
                                  <span className="font-normal text-amber-800">HP Boiler Feed Pump (Tripped)</span>
                                </div>
                                <div className="flex items-center space-x-2 py-0.2">
                                  <span>•</span>
                                  <span className="font-bold text-slate-800">M-301A:</span>
                                  <span className="text-slate-600">450 kW Induction Motor</span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
