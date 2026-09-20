import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ResetPortfolioButton } from '../portfolio/ResetPortfolioButton';
const { post, replace, refresh } = vi.hoisted(() => ({ post: vi.fn(), replace: vi.fn(), refresh: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ post, ApiError: class extends Error {} }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace, refresh }) }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['comparison', 'me'], { old: true });
  render(<QueryClientProvider client={client}><ResetPortfolioButton/></QueryClientProvider>);
  return client;
}
describe('portfolio reset', () => {
  it('cancelling confirmation makes no request', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    mount(); fireEvent.click(screen.getByRole('button', { name: '포트폴리오 초기화' }));
    expect(post).not.toHaveBeenCalled();
  });
  it('confirmed reset clears cached performance and opens first setup', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true); post.mockResolvedValue({ status: 'setup_required' });
    const client = mount(); fireEvent.click(screen.getByRole('button', { name: '포트폴리오 초기화' }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/setup/portfolio?step=risk'));
    expect(post).toHaveBeenCalledWith('/api/v1/me/experiment/reset', { confirm: true });
    expect(client.getQueryData(['comparison', 'me'])).toBeUndefined();
  });
  it('failed reset leaves the saved comparison and allows retry', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true); post.mockRejectedValue(new Error('offline'));
    const client = mount(); fireEvent.click(screen.getByRole('button', { name: '포트폴리오 초기화' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('초기화하지 못했습니다');
    expect(client.getQueryData(['comparison', 'me'])).toEqual({ old: true });
    expect(screen.getByRole('button', { name: '포트폴리오 초기화' })).toBeEnabled();
  });
});
