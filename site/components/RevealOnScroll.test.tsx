import { render, screen, act, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import RevealOnScroll from './RevealOnScroll';

// --- Mocks ---

let intersectionCallback: IntersectionObserverCallback;
const mockObserve = vi.fn();
const mockUnobserve = vi.fn();
const mockDisconnect = vi.fn();

class MockIntersectionObserver {
  constructor(cb: IntersectionObserverCallback) {
    intersectionCallback = cb;
  }
  observe = mockObserve;
  unobserve = mockUnobserve;
  disconnect = mockDisconnect;
}

function setupIntersectionObserver() {
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
}

function mockMatchMedia(prefersReducedMotion: boolean) {
  vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
    matches: query === '(prefers-reduced-motion: reduce)' ? prefersReducedMotion : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));
}

function mockElementPosition(position: 'above-fold' | 'below-fold') {
  const top = position === 'above-fold' ? 100 : 1000;
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    top,
    bottom: top + 200,
    left: 0,
    right: 300,
    width: 300,
    height: 200,
    x: 0,
    y: top,
    toJSON: () => {},
  });
}

function triggerIntersection(isIntersecting: boolean) {
  act(() => {
    intersectionCallback(
      [{ isIntersecting } as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
  });
}

// --- Tests ---

describe('RevealOnScroll', () => {
  beforeEach(() => {
    mockObserve.mockClear();
    mockUnobserve.mockClear();
    mockDisconnect.mockClear();
    setupIntersectionObserver();
    mockMatchMedia(false);
    Object.defineProperty(window, 'innerHeight', { value: 800, writable: true });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  // --- SSR / initial render ---

  it('renders children', () => {
    mockElementPosition('above-fold');
    render(<RevealOnScroll>Hello</RevealOnScroll>);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('renders fully visible by default before hydration', () => {
    // Before useEffect runs, revealed=true so SSR paint is visible
    mockElementPosition('above-fold');
    render(<RevealOnScroll><span data-testid="child">Content</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('1');
    expect(wrapper.style.transform).toBe('translateY(0)');
  });

  // --- Above fold ---

  it('stays visible when element is above the fold', () => {
    mockElementPosition('above-fold');
    render(<RevealOnScroll><span data-testid="child">Above</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('1');
    expect(wrapper.style.transform).toBe('translateY(0)');
  });

  it('does not create an observer when above the fold', () => {
    mockElementPosition('above-fold');
    render(<RevealOnScroll>Above</RevealOnScroll>);
    expect(mockObserve).not.toHaveBeenCalled();
  });

  // --- Below fold ---

  it('starts hidden when element is below the fold', () => {
    mockElementPosition('below-fold');
    render(<RevealOnScroll><span data-testid="child">Below</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('0');
    expect(wrapper.style.transform).toBe('translateY(28px)');
  });

  it('reveals when intersection observer fires', () => {
    mockElementPosition('below-fold');
    render(<RevealOnScroll><span data-testid="child">Below</span></RevealOnScroll>);
    triggerIntersection(true);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('1');
    expect(wrapper.style.transform).toBe('translateY(0)');
  });

  it('unobserves element after revealing', () => {
    mockElementPosition('below-fold');
    render(<RevealOnScroll><span data-testid="child">Below</span></RevealOnScroll>);
    triggerIntersection(true);
    expect(mockUnobserve).toHaveBeenCalled();
  });

  it('stays hidden when observer fires with isIntersecting false', () => {
    mockElementPosition('below-fold');
    render(<RevealOnScroll><span data-testid="child">Below</span></RevealOnScroll>);
    triggerIntersection(false);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('0');
  });

  it('disconnects observer on unmount', () => {
    mockElementPosition('below-fold');
    const { unmount } = render(<RevealOnScroll>Below</RevealOnScroll>);
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  // --- Reduced motion ---

  it('renders with opacity 1 and no transform when reduced motion is preferred', () => {
    mockMatchMedia(true);
    mockElementPosition('below-fold');
    render(<RevealOnScroll><span data-testid="child">Motion</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('1');
    expect(wrapper.style.transform).toBe('none');
  });

  // --- Props ---

  it('forwards className to wrapper div', () => {
    mockElementPosition('above-fold');
    render(<RevealOnScroll className="custom-class"><span data-testid="child">Cls</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper).toHaveClass('custom-class');
  });

  it('applies transitionDelay when delay prop is provided', () => {
    mockElementPosition('above-fold');
    render(<RevealOnScroll delay={200}><span data-testid="child">Delayed</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.transitionDelay).toBe('200ms');
  });

  it('does not apply transitionDelay when delay is 0', () => {
    mockElementPosition('above-fold');
    render(<RevealOnScroll delay={0}><span data-testid="child">No delay</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.transitionDelay).toBe('');
  });

  it('applies transition property for animation', () => {
    mockElementPosition('above-fold');
    render(<RevealOnScroll><span data-testid="child">Trans</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.transition).toContain('opacity');
    expect(wrapper.style.transition).toContain('transform');
  });

  // --- Fold threshold boundary ---

  it('treats element at exactly 92% viewport height as below fold', () => {
    // rect.top = 736 = 800 * 0.92 — condition is `<` strict, so 736 < 736 is false
    // meaning the element is NOT above fold, observer is created
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      top: 736, bottom: 936, left: 0, right: 300,
      width: 300, height: 200, x: 0, y: 736, toJSON: () => {},
    });
    render(<RevealOnScroll><span data-testid="child">Edge</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('0');
    expect(mockObserve).toHaveBeenCalled();
  });

  it('treats element just inside 92% viewport height as above fold', () => {
    // rect.top = 735 < 736 — element is above fold, no observer
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      top: 735, bottom: 935, left: 0, right: 300,
      width: 300, height: 200, x: 0, y: 735, toJSON: () => {},
    });
    render(<RevealOnScroll><span data-testid="child">Edge</span></RevealOnScroll>);
    const wrapper = screen.getByTestId('child').parentElement!;
    expect(wrapper.style.opacity).toBe('1');
    expect(mockObserve).not.toHaveBeenCalled();
  });
});
