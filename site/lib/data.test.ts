import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getCoupons, getActiveCoupons, getExpiredCoupons, getDashboard } from './data';
import type { Coupon, Dashboard } from './data';

// --- Test fixtures ---

function makeCoupon(overrides: Partial<Coupon> = {}): Coupon {
  return {
    code: 'TEST10',
    type: 'promo',
    discount: '10% off',
    regions: ['us'],
    min_cart_value: 0,
    status: 'valid',
    first_seen: '2026-03-01',
    last_validated: '2026-03-20T08:00:00Z',
    last_failed: null,
    fail_count: 0,
    source: 'test',
    stackable_with_referral: false,
    notes: '',
    ...overrides,
  };
}

const VALID_COUPON = makeCoupon({ code: 'VALID1', status: 'valid' });
const REGION_COUPON = makeCoupon({ code: 'REGION1', status: 'region_limited', regions: ['de'] });
const EXPIRED_COUPON = makeCoupon({ code: 'OLD1', status: 'expired', fail_count: 3 });
const INVALID_COUPON = makeCoupon({ code: 'BAD1', status: 'invalid' });
const DISCOVERED_COUPON = makeCoupon({ code: 'NEW1', status: 'discovered' });

const ALL_COUPONS: Coupon[] = [VALID_COUPON, REGION_COUPON, EXPIRED_COUPON, INVALID_COUPON, DISCOVERED_COUPON];

const VALID_DASHBOARD: Dashboard = {
  affiliate_code: 'OFR0296',
  jobs: {
    researcher: { last_run: '2026-03-22T06:00:00Z', status: 'success', next_run: '2026-03-22T18:00:00Z', last_error: null, codes_found: 3 },
    validator: { last_run: '2026-03-22T08:00:00Z', status: 'success', next_run: '2026-03-22T20:00:00Z', last_error: null, codes_validated: 7 },
    poster: { last_run: '2026-03-22T09:00:00Z', status: 'success', next_run: '2026-03-22T13:00:00Z', last_error: null, posts_today: 1 },
  },
  stats: {
    total_active_codes: 2,
    total_expired_codes: 1,
    total_posts_this_week: 0,
    last_deploy: '2026-03-23T23:00:00Z',
  },
};

// --- Mock fs ---

const mockReadFileSync = vi.hoisted(() => vi.fn());

vi.mock('fs', () => ({
  readFileSync: mockReadFileSync,
  default: { readFileSync: mockReadFileSync },
}));

beforeEach(() => {
  mockReadFileSync.mockReset();
});

// --- getCoupons ---

describe('getCoupons', () => {
  it('returns parsed coupon array from coupons.json', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(ALL_COUPONS));
    const result = getCoupons();
    expect(result).toHaveLength(5);
    expect(result[0].code).toBe('VALID1');
  });

  it('reads from data/coupons.json path', () => {
    mockReadFileSync.mockReturnValue('[]');
    getCoupons();
    const calledPath = mockReadFileSync.mock.calls[0][0] as string;
    expect(calledPath).toContain('data');
    expect(calledPath).toContain('coupons.json');
  });

  it('returns empty array when file contains empty array', () => {
    mockReadFileSync.mockReturnValue('[]');
    expect(getCoupons()).toEqual([]);
  });

  it('preserves all coupon fields', () => {
    const coupon = makeCoupon({
      code: 'FULL',
      regions: ['us', 'de', 'gb'],
      min_cart_value: 40,
      stackable_with_referral: true,
      last_failed: '2026-03-15T00:00:00Z',
      fail_count: 2,
    });
    mockReadFileSync.mockReturnValue(JSON.stringify([coupon]));
    const result = getCoupons()[0];
    expect(result.code).toBe('FULL');
    expect(result.regions).toEqual(['us', 'de', 'gb']);
    expect(result.min_cart_value).toBe(40);
    expect(result.stackable_with_referral).toBe(true);
    expect(result.last_failed).toBe('2026-03-15T00:00:00Z');
    expect(result.fail_count).toBe(2);
  });
});

// --- getActiveCoupons ---

describe('getActiveCoupons', () => {
  it('returns only valid and region_limited coupons', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(ALL_COUPONS));
    const result = getActiveCoupons();
    expect(result).toHaveLength(2);
    expect(result.map(c => c.code)).toEqual(['VALID1', 'REGION1']);
  });

  it('excludes expired coupons', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(ALL_COUPONS));
    const result = getActiveCoupons();
    expect(result.find(c => c.status === 'expired')).toBeUndefined();
  });

  it('excludes invalid coupons', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(ALL_COUPONS));
    const result = getActiveCoupons();
    expect(result.find(c => c.status === 'invalid')).toBeUndefined();
  });

  it('excludes discovered coupons', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(ALL_COUPONS));
    const result = getActiveCoupons();
    expect(result.find(c => c.status === 'discovered')).toBeUndefined();
  });

  it('returns empty array when no active coupons exist', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify([EXPIRED_COUPON, INVALID_COUPON]));
    expect(getActiveCoupons()).toEqual([]);
  });
});

// --- getExpiredCoupons ---

describe('getExpiredCoupons', () => {
  it('returns only expired coupons', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(ALL_COUPONS));
    const result = getExpiredCoupons();
    expect(result).toHaveLength(1);
    expect(result[0].code).toBe('OLD1');
  });

  it('excludes valid and region_limited coupons', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(ALL_COUPONS));
    const result = getExpiredCoupons();
    expect(result.every(c => c.status === 'expired')).toBe(true);
  });

  it('returns empty array when no expired coupons exist', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify([VALID_COUPON]));
    expect(getExpiredCoupons()).toEqual([]);
  });
});

// --- getDashboard ---

describe('getDashboard', () => {
  it('returns parsed dashboard data', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(VALID_DASHBOARD));
    const result = getDashboard();
    expect(result.affiliate_code).toBe('OFR0296');
  });

  it('reads from data/dashboard.json path', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(VALID_DASHBOARD));
    getDashboard();
    const calledPath = mockReadFileSync.mock.calls[0][0] as string;
    expect(calledPath).toContain('dashboard.json');
  });

  it('returns all three job statuses', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(VALID_DASHBOARD));
    const { jobs } = getDashboard();
    expect(jobs.researcher.status).toBe('success');
    expect(jobs.validator.status).toBe('success');
    expect(jobs.poster.status).toBe('success');
  });

  it('returns stats with expected values', () => {
    mockReadFileSync.mockReturnValue(JSON.stringify(VALID_DASHBOARD));
    const { stats } = getDashboard();
    expect(stats.total_active_codes).toBe(2);
    expect(stats.total_expired_codes).toBe(1);
    expect(stats.total_posts_this_week).toBe(0);
    expect(stats.last_deploy).toBe('2026-03-23T23:00:00Z');
  });

  it('handles job with failure status and error message', () => {
    const dashboard = {
      ...VALID_DASHBOARD,
      jobs: {
        ...VALID_DASHBOARD.jobs,
        researcher: { ...VALID_DASHBOARD.jobs.researcher, status: 'failure' as const, last_error: 'Connection timeout' },
      },
    };
    mockReadFileSync.mockReturnValue(JSON.stringify(dashboard));
    const { jobs } = getDashboard();
    expect(jobs.researcher.status).toBe('failure');
    expect(jobs.researcher.last_error).toBe('Connection timeout');
  });
});

// --- Coupon JSON schema contract ---

describe('Coupon JSON schema contract', () => {
  it('matches the schema produced by the validator service', () => {
    // This is the exact shape the Python validator writes to coupons.json.
    // If the validator changes its output, this test should fail so the
    // site data layer can be updated to match.
    const validatorOutput = {
      code: 'WELCOME25',
      type: 'promo',
      discount: '25% off first order',
      regions: ['us', 'de', 'gb'],
      min_cart_value: 40,
      status: 'valid',
      first_seen: '2026-03-10',
      last_validated: '2026-03-22T08:00:00Z',
      last_failed: null,
      fail_count: 0,
      source: 'couponfollow.com',
      stackable_with_referral: true,
      notes: 'New customers only',
    };
    mockReadFileSync.mockReturnValue(JSON.stringify([validatorOutput]));
    const result = getCoupons();
    expect(result[0]).toEqual(validatorOutput);
  });

  it('handles coupon with all valid status values', () => {
    const statuses = ['valid', 'expired', 'region_limited', 'invalid', 'discovered'] as const;
    const coupons = statuses.map(s => makeCoupon({ code: s.toUpperCase(), status: s }));
    mockReadFileSync.mockReturnValue(JSON.stringify(coupons));
    const result = getCoupons();
    expect(result.map(c => c.status)).toEqual([...statuses]);
  });
});

// --- Dashboard JSON schema contract ---

describe('Dashboard JSON schema contract', () => {
  it('matches the schema produced by the orchestrator dashboard_writer', () => {
    // This is the exact shape dashboard_writer.py produces.
    mockReadFileSync.mockReturnValue(JSON.stringify(VALID_DASHBOARD));
    const result = getDashboard();
    expect(result).toEqual(VALID_DASHBOARD);
  });

  it('supports extra fields on job objects via index signature', () => {
    const dashboard = {
      ...VALID_DASHBOARD,
      jobs: {
        ...VALID_DASHBOARD.jobs,
        researcher: { ...VALID_DASHBOARD.jobs.researcher, codes_found: 5 },
      },
    };
    mockReadFileSync.mockReturnValue(JSON.stringify(dashboard));
    const { jobs } = getDashboard();
    expect(jobs.researcher.codes_found).toBe(5);
  });
});
