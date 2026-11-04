"use client";

import {useState} from 'react';
import {PerformancePanels} from '@/app/(app)/dashboard/performance-panels';
import type {Report} from '@/app/(app)/dashboard/performance-data';
import styles from '@/app/(app)/dashboard/dashboard.module.css';

/** Display only server-calculated attribution, for the selected record source. */
export function ReturnContribution({report}:{report?:Report}) {
  const [mode,setMode]=useState<'groups'|'assets'>('groups');
  const [selected,setSelected]=useState<string|null>(null);
  if(!report || (report.attribution?.length??0)<2) return null;
  return <PerformancePanels report={report} styles={styles} onlyContribution
    mode={mode} selected={selected} onSelect={setSelected}
    onMode={value=>{setMode(value);setSelected(null);}}/>;
}
