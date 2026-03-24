import type { Metadata } from 'next';
import { getDashboard } from '@/lib/data';
import StatusIndicator from '@/components/StatusIndicator';
import RevealOnScroll from '@/components/RevealOnScroll';

export const metadata: Metadata = {
  title: 'System Dashboard — AnyaDeals',
  description: 'Pipeline status and system statistics.',
};

export default function DashboardPage() {
  const { jobs, stats } = getDashboard();

  return (
    <article className="pt-28 pb-24">
      <header className="max-w-7xl mx-auto px-6 md:px-12">
        <RevealOnScroll>
          <p className="text-xs uppercase tracking-[0.2em] text-signal font-medium font-sans mb-5">System</p>
        </RevealOnScroll>
        <RevealOnScroll delay={80}>
          <h1 className="headline-lg mb-2">Pipeline Dashboard</h1>
        </RevealOnScroll>
        <RevealOnScroll delay={120}>
          <p className="text-ink-muted text-sm font-sans mb-12">This page updates hourly. All times in UTC.</p>
        </RevealOnScroll>
      </header>

      {/* Pipeline Status */}
      <section className="max-w-7xl mx-auto px-6 md:px-12">
        <RevealOnScroll>
          <h2 className="headline-md font-editorial mb-6">Pipeline Status</h2>
        </RevealOnScroll>
        <RevealOnScroll delay={60}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-ink/10">
            <div className="border-b md:border-b-0 md:border-r border-ink/10">
              <StatusIndicator status={jobs.researcher.status} label="Researcher" lastRun={jobs.researcher.last_run} nextRun={jobs.researcher.next_run} lastError={jobs.researcher.last_error} />
            </div>
            <div className="border-b md:border-b-0 md:border-r border-ink/10">
              <StatusIndicator status={jobs.validator.status} label="Validator" lastRun={jobs.validator.last_run} nextRun={jobs.validator.next_run} lastError={jobs.validator.last_error} />
            </div>
            <div>
              <StatusIndicator status={jobs.poster.status} label="Poster" lastRun={jobs.poster.last_run} nextRun={jobs.poster.next_run} lastError={jobs.poster.last_error} />
            </div>
          </div>
        </RevealOnScroll>
      </section>

      {/* Stats */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 mt-16">
        <RevealOnScroll>
          <h2 className="headline-md font-editorial mb-6">Stats</h2>
        </RevealOnScroll>
        <RevealOnScroll delay={60}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-0 border border-ink/10">
            <div className="border-b md:border-b-0 md:border-r border-ink/10 p-6 text-center">
              <p className="font-editorial text-3xl font-bold text-signal">{stats.total_active_codes}</p>
              <p className="text-xs text-ink-muted font-sans mt-1">Active Codes</p>
            </div>
            <div className="border-b md:border-b-0 md:border-r border-ink/10 p-6 text-center">
              <p className="font-editorial text-3xl font-bold text-ink">{stats.total_expired_codes}</p>
              <p className="text-xs text-ink-muted font-sans mt-1">Expired</p>
            </div>
            <div className="border-b md:border-b-0 md:border-r border-ink/10 p-6 text-center">
              <p className="font-editorial text-3xl font-bold text-gold">{stats.total_posts_this_week}</p>
              <p className="text-xs text-ink-muted font-sans mt-1">Posts This Week</p>
            </div>
            <div className="p-6 text-center">
              <p className="font-editorial text-3xl font-bold text-ink">
                {new Date(stats.last_deploy).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </p>
              <p className="text-xs text-ink-muted font-sans mt-1">Last Deploy</p>
            </div>
          </div>
        </RevealOnScroll>
      </section>
    </article>
  );
}
