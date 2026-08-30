import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Upload from "./pages/Upload";
import Dashboard from "./pages/Dashboard";

export default function App() {
  return (
    <BrowserRouter>
      <nav
        style={{
          display: "flex",
          gap: 20,
          padding: "16px 24px",
          borderBottom: "1px solid #e5e7eb",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <strong>SIH26034 · Compliance Checker</strong>
        <Link to="/">Scan</Link>
        <Link to="/dashboard">Dashboard</Link>
      </nav>
      <div style={{ fontFamily: "system-ui, sans-serif" }}>
        <Routes>
          <Route path="/" element={<Upload />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
