import React, { useState } from 'react';
import { FileCheck2, Copy, Printer } from 'lucide-react';
import { RCAState } from '../../types';

export const DeliverablesTab: React.FC<{ rcaState: RCAState | null }> = ({ rcaState }) => {
  const [copyStatus, setCopyStatus] = useState('');
  const report = rcaState?.incident_report_8d;
  const order = rcaState?.sap_work_order;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify({ incident_report_8d: report, sap_work_order: order }, null, 2));
      setCopyStatus('Copied');
    } catch {
      setCopyStatus('Copy failed. Try again or use Print.');
    }
  };
  return (
    <div className="space-y-4 text-sm text-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold flex items-center gap-2"><FileCheck2 className="w-4 h-4 text-teal-700" />Reviewed maintenance drafts</h2>
        {(report || order) && <div className="flex gap-2"><button onClick={copy} className="flex items-center gap-2 px-3 py-2 border border-slate-300 rounded-lg hover:bg-slate-100"><Copy className="w-4 h-4" />Copy JSON</button><button onClick={() => window.print()} className="flex items-center gap-2 px-3 py-2 border border-slate-300 rounded-lg hover:bg-slate-100"><Printer className="w-4 h-4" />Print</button></div>}
      </div>
      <p role="status" className="text-slate-600">{copyStatus || 'These are local drafts. No work order has been submitted to SAP.'}</p>
      {!report && !order && <p className="p-4 bg-white border border-slate-200 rounded-lg">No maintenance artifacts have been generated. A supported diagnosis and explicit human approval are required.</p>}
      {report && <section className="space-y-3 p-4 bg-white border border-slate-200 rounded-lg">
        <h3 className="font-semibold">8D investigation report · {report.incident_id}</h3>
        <p>{report.d2_problem_description.what}</p>
        <p>{report.d4_root_cause_analysis.root_cause_statement}</p>
        <h4 className="font-semibold pt-2">Reviewed actions</h4>
        <ul className="list-disc pl-5 space-y-1">{report.d5_permanent_corrective_actions.map((action, index) => <li key={index}>{action}</li>)}</ul>
        <p className="text-slate-600">Reviewed by {report.d8_sign_off.reviewed_by} · {report.d8_sign_off.date}</p>
        <details><summary className="cursor-pointer">Full report and evidence</summary><pre className="text-xs whitespace-pre-wrap break-words mt-3">{JSON.stringify(report, null, 2)}</pre></details>
      </section>}
      {order && <section className="space-y-3 p-4 bg-white border border-slate-200 rounded-lg">
        <h3 className="font-semibold">PM01 local draft · {order.order_number}</h3>
        <p>Equipment: {order.equipment_id} · Status: {order.system_status}</p>
        <ol className="list-decimal pl-5 space-y-2">{order.operations.map((operation) => <li key={operation.operation_number}>{operation.description}</li>)}</ol>
        <p>Estimated hours: {order.total_estimated_hours ?? 'Not specified'}</p>
        <p>Materials: {order.materials_required.length ? order.materials_required.map((material) => material.description).join(', ') : 'None specified by the reviewed diagnosis'}</p>
      </section>}
    </div>
  );
};
