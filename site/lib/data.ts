import { readFileSync } from 'fs';
import { join } from 'path';

export interface Coupon {
  code: string;
  type: string;
  discount: string;
  regions: string[];
  min_cart_value: number;
  status: 'valid' | 'expired' | 'region_limited' | 'invalid' | 'discovered';
  first_seen: string;
  last_validated: string;
  last_failed: string | null;
  fail_count: number;
  source: string;
  stackable_with_referral: boolean;
  notes: string;
}

export interface DashboardJob {
  last_run: string;
  status: 'success' | 'failure' | 'unknown';
  next_run: string;
  last_error: string | null;
  [key: string]: unknown;
}

export interface Dashboard {
  affiliate_code: string;
  jobs: {
    researcher: DashboardJob;
    validator: DashboardJob;
    poster: DashboardJob;
  };
  stats: {
    total_active_codes: number;
    total_expired_codes: number;
    total_posts_this_week: number;
    last_deploy: string;
  };
}

function readJson<T>(filename: string): T {
  const raw = readFileSync(join(process.cwd(), 'data', filename), 'utf-8');
  return JSON.parse(raw) as T;
}

export function getCoupons(): Coupon[] {
  return readJson<Coupon[]>('coupons.json');
}

export function getActiveCoupons(): Coupon[] {
  return getCoupons().filter(c => c.status === 'valid' || c.status === 'region_limited');
}

export function getExpiredCoupons(): Coupon[] {
  return getCoupons().filter(c => c.status === 'expired');
}

export function getDashboard(): Dashboard {
  return readJson<Dashboard>('dashboard.json');
}

export interface ResearchEntry {
  code: string;
  validation_status?: string;
  [key: string]: unknown;
}

export interface ResearchStats {
  totalDiscovered: number;
  totalValidated: number;
}

export function getResearchStats(): ResearchStats {
  const entries = readJson<ResearchEntry[]>('research.json');
  return {
    totalDiscovered: entries.length,
    totalValidated: entries.filter(e => e.validation_status && e.validation_status !== 'none').length,
  };
}
