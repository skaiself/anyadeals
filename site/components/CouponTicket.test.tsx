import { render, screen, cleanup, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import CouponTicket from './CouponTicket';

let mockWriteText: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockWriteText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: mockWriteText },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('CouponTicket', () => {
  it('renders the coupon code', () => {
    render(<CouponTicket code="TEST10" label="Test Label" sublabel="Test sub" />);
    expect(screen.getByText('TEST10')).toBeInTheDocument();
  });

  it('renders label and sublabel', () => {
    render(<CouponTicket code="X" label="Step 1" sublabel="5% off" />);
    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('5% off')).toBeInTheDocument();
  });

  it('has accessible aria-label with the code', () => {
    render(<CouponTicket code="OFR0296" label="L" sublabel="S" />);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Copy coupon code OFR0296');
  });

  it('has correct id based on lowercased code', () => {
    render(<CouponTicket code="GOLD60" label="L" sublabel="S" />);
    expect(screen.getByRole('button')).toHaveAttribute('id', 'coupon-gold60');
  });

  it('copies code to clipboard on click', async () => {
    render(<CouponTicket code="COPY_ME" label="L" sublabel="S" />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button'));
    });
    expect(mockWriteText).toHaveBeenCalledWith('COPY_ME');
  });

  it('shows "Copied!" feedback after clicking', async () => {
    const user = userEvent.setup();

    render(<CouponTicket code="X" label="L" sublabel="S" />);
    expect(screen.getByText('Copy')).toBeInTheDocument();
    await user.click(screen.getByRole('button'));
    expect(screen.getByText('Copied!')).toBeInTheDocument();
  });

  it('shows "Copy" text initially', () => {
    render(<CouponTicket code="X" label="L" sublabel="S" />);
    expect(screen.getByText('Copy')).toBeInTheDocument();
  });
});
