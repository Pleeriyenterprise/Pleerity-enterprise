import React from 'react';
import { Outlet } from 'react-router-dom';

/** Thin wrapper so /reports and /reports/audit-pack share one route tree. */
export default function ReportsLayout() {
  return <Outlet />;
}
