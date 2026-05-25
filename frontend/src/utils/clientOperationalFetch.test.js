import {
  clearOperationalCache,
  fetchOperational,
  peekOperationalCache,
} from './clientOperationalFetch';

describe('clientOperationalFetch', () => {
  beforeEach(() => {
    clearOperationalCache();
  });

  it('dedupes concurrent fetches for the same key', async () => {
    const fetcher = jest.fn(() => Promise.resolve({ n: 1 }));
    const [a, b] = await Promise.all([
      fetchOperational('test:dedupe', fetcher),
      fetchOperational('test:dedupe', fetcher),
    ]);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(a.data).toEqual({ n: 1 });
    expect(b.data).toEqual({ n: 1 });
  });

  it('returns fresh cache without refetching', async () => {
    const fetcher = jest.fn(() => Promise.resolve({ n: 2 }));
    await fetchOperational('test:fresh', fetcher);
    const second = await fetchOperational('test:fresh', fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(second.fromCache).toBe(true);
    expect(second.refreshing).toBe(false);
  });

  it('stale-while-refresh returns cached data and calls onRefresh', async () => {
    const fetcher = jest.fn()
      .mockResolvedValueOnce({ v: 1 })
      .mockResolvedValueOnce({ v: 2 });
    await fetchOperational('test:stale', fetcher, { staleMs: 0 });
    const onRefresh = jest.fn();
    const stale = await fetchOperational('test:stale', fetcher, { staleMs: 0, onRefresh });
    expect(stale.data).toEqual({ v: 1 });
    expect(stale.refreshing).toBe(true);
    await new Promise((resolve) => {
      setTimeout(resolve, 10);
    });
    expect(onRefresh).toHaveBeenCalledWith({ v: 2 });
    expect(peekOperationalCache('test:stale')).toEqual({ v: 2 });
  });
});
