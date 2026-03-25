import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import StatusIndicator from './StatusIndicator';

afterEach(() => cleanup());

describe('StatusIndicator', () => {
  const defaults = {
    status: 'success',
    label: 'Researcher',
    lastRun: '2026-03-22T06:00:00Z',
    nextRun: '2026-03-22T18:00:00Z',
  };

  it('renders the label', () => {
    render(<StatusIndicator {...defaults} />);
    expect(screen.getByText('Researcher')).toBeInTheDocument();
  });

  it('renders last run and next run times', () => {
    render(<StatusIndicator {...defaults} />);
    expect(screen.getByText(/Last run:/)).toBeInTheDocument();
    expect(screen.getByText(/Next run:/)).toBeInTheDocument();
  });

  it('shows green indicator for success status', () => {
    const { container } = render(<StatusIndicator {...defaults} status="success" />);
    const dot = container.querySelector('.bg-green-600');
    expect(dot).toBeInTheDocument();
  });

  it('shows red indicator for failure status', () => {
    const { container } = render(<StatusIndicator {...defaults} status="failure" />);
    const dot = container.querySelector('.bg-red-600');
    expect(dot).toBeInTheDocument();
  });

  it('shows yellow indicator for unknown status', () => {
    const { container } = render(<StatusIndicator {...defaults} status="unknown" />);
    const dot = container.querySelector('.bg-yellow-500');
    expect(dot).toBeInTheDocument();
  });

  it('falls back to yellow for unrecognized status', () => {
    const { container } = render(<StatusIndicator {...defaults} status="pending" />);
    const dot = container.querySelector('.bg-yellow-500');
    expect(dot).toBeInTheDocument();
  });

  it('does not show error text when lastError is null', () => {
    render(<StatusIndicator {...defaults} lastError={null} />);
    expect(screen.queryByText(/Error:/)).not.toBeInTheDocument();
  });

  it('shows error message when lastError is provided', () => {
    render(<StatusIndicator {...defaults} lastError="Connection timeout" />);
    expect(screen.getByText('Error: Connection timeout')).toBeInTheDocument();
  });
});
