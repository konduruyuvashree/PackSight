import React, { useEffect, useState } from "react";
import { listScans, getStats, reportPdfUrl } from "../api";

export default function Dashboard() {
  const [scans, setScans] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    getStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    listScans(filter || undefined).then(setScans).catch(() => {});
  }, [filter]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Enforcement Dashboard</h1>

      {stats && (
        <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
          <StatCard label="Total Scanned" value={stats.total_scanned} />
          <StatCard label="Passed" value={stats.passed} color="#16a34a" />
          <StatCard label="Failed" value={stats.failed} color="#dc2626" />
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <label>Filter: </label>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All</option>
          <option value="PASS">Pass</option>
          <option value="FAIL">Fail</option>
        </select>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #e5e7eb" }}>
            <th style={{ padding: 8 }}>ID</th>
            <th style={{ padding: 8 }}>Product</th>
            <th style={{ padding: 8 }}>Status</th>
            <th style={{ padding: 8 }}>Violations</th>
            <th style={{ padding: 8 }}>Scanned At</th>
            <th style={{ padding: 8 }}>Report</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((s) => (
            <tr key={s.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: 8 }}>{s.id}</td>
              <td style={{ padding: 8 }}>{s.product_name || "—"}</td>
              <td style={{ padding: 8, color: s.overall_status === "PASS" ? "#16a34a" : "#dc2626" }}>
                {s.overall_status}
              </td>
              <td style={{ padding: 8 }}>{s.violation_count}</td>
              <td style={{ padding: 8, fontSize: 13, color: "#6b7280" }}>
                {new Date(s.scanned_at).toLocaleString()}
              </td>
              <td style={{ padding: 8 }}>
                <a href={reportPdfUrl(s.id)} target="_blank" rel="noreferrer">
                  PDF
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatCard({ label, value, color = "#111827" }) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 16, flex: 1 }}>
      <div style={{ fontSize: 13, color: "#6b7280" }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}
