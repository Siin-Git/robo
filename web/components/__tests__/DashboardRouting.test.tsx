import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
const route = vi.hoisted(() => ({ search: '', path:'/dashboard' }));
vi.mock('next/navigation', () => ({ usePathname: () => route.path, useSearchParams: () => new URLSearchParams(route.search) }));
vi.mock('next/dynamic', () => ({ default: () => () => <div>Overview</div> }));
vi.mock('@tanstack/react-query', () => ({ useQuery: () => ({ isLoading:true }) }));
vi.mock('@/components/layout/AppShell', () => ({ AppShell: ({children}:any) => <div>{children}</div> }));
vi.mock('@/components/dashboard/HistoricalPreview', () => ({ useHistoricalPreview:()=>({isLoading:true}), HistoricalPreview:()=>null }));
vi.mock('@/components/dashboard/ReplayNotice', () => ({ useLocalReplay:()=>({data:null}) }));
vi.mock('@/lib/api/comparison', () => ({ DEMO_MODE:false }));
import DashboardPage from '@/app/(app)/dashboard/page';
beforeEach(() => { route.search=""; route.path="/dashboard"; });
afterEach(cleanup);
it('opens the overview for an ordinary dashboard visit', () => {
 route.search=''; render(<DashboardPage/>); expect(screen.getByText('Overview')).toBeInTheDocument();
});
it.each(['view=details','comparison=common','period=1M'])('preserves the detailed analytical route: %s', (search) => {
 route.search=search; render(<DashboardPage/>); expect(screen.queryByText('Overview')).not.toBeInTheDocument();
});
it('keeps the performance navigation in the detailed view', () => {
 route.search=''; route.path='/performance'; render(<DashboardPage/>); expect(screen.queryByText('Overview')).not.toBeInTheDocument();
});
