"use client";

import { useCallback, useEffect, useRef, type PointerEvent, type ReactNode } from "react";

type DocumentSheetProps = {
  children: ReactNode;
  onDismiss: () => void;
};

const RESPONSE_SECONDS = 0.34;

export function DocumentSheet({ children, onDismiss }: DocumentSheetProps) {
  const backdropRef = useRef<HTMLDivElement>(null);
  const sheetRef = useRef<HTMLElement>(null);
  const offsetRef = useRef(0);
  const velocityRef = useRef(0);
  const animationRef = useRef<number | null>(null);
  const dismissingRef = useRef(false);
  const dismissActionRef = useRef<() => void>(() => undefined);
  const springActionRef = useRef<(target: number, damping: number, velocity: number, dismissAfter?: boolean) => void>(() => undefined);
  const dismissRef = useRef(onDismiss);
  const dragRef = useRef({
    pointerId: -1,
    startY: 0,
    startOffset: 0,
    lastY: 0,
    lastTime: 0,
    pointerVelocity: 0,
    committed: false,
  });

  const paint = useCallback((y: number, alpha?: number) => {
    offsetRef.current = y;
    if (sheetRef.current) sheetRef.current.style.transform = `translate3d(0, ${y}px, 0)`;
    if (backdropRef.current) {
      backdropRef.current.style.opacity = String(alpha ?? Math.max(0.2, 1 - Math.max(0, y) / Math.max(window.innerHeight, 1)));
    }
  }, []);

  const stopAnimation = useCallback(() => {
    if (animationRef.current !== null) cancelAnimationFrame(animationRef.current);
    animationRef.current = null;
  }, []);

  const springTo = useCallback((target: number, damping: number, initialVelocity: number, dismissAfter = false) => {
    stopAnimation();
    const stiffness = (4 * Math.PI * Math.PI) / (RESPONSE_SECONDS * RESPONSE_SECONDS);
    const dampingCoefficient = 2 * damping * Math.sqrt(stiffness);
    let position = offsetRef.current;
    let velocity = initialVelocity;
    let previousTime = 0;

    const frame = (now: number) => {
      const dt = previousTime === 0 ? 0 : Math.min((now - previousTime) / 1000, 0.032);
      previousTime = now;
      const acceleration = -stiffness * (position - target) - dampingCoefficient * velocity;
      velocity += acceleration * dt;
      position += velocity * dt;

      if (Math.abs(position - target) < 0.5 && Math.abs(velocity) < 8) {
        paint(target, dismissAfter ? 0 : 1);
        animationRef.current = null;
        velocityRef.current = 0;
        if (dismissAfter) dismissRef.current();
        return;
      }

      velocityRef.current = velocity;
      paint(position);
      animationRef.current = requestAnimationFrame(frame);
    };

    velocityRef.current = velocity;
    animationRef.current = requestAnimationFrame(frame);
  }, [paint, stopAnimation]);

  const requestDismiss = useCallback(() => {
    if (dismissingRef.current) return;
    dismissingRef.current = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      if (sheetRef.current) sheetRef.current.style.opacity = "0";
      if (backdropRef.current) backdropRef.current.style.opacity = "0";
      window.setTimeout(() => dismissRef.current(), 140);
      return;
    }
    springActionRef.current(Math.max(window.innerHeight, 600), 0.8, Math.max(velocityRef.current, 0), true);
  }, []);

  useEffect(() => {
    dismissRef.current = onDismiss;
    dismissActionRef.current = requestDismiss;
    springActionRef.current = springTo;
  }, [onDismiss, requestDismiss, springTo]);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const firstControl = sheetRef.current?.querySelector<HTMLElement>("button, a[href], input, select, textarea, [tabindex='0']");
    (firstControl ?? sheetRef.current)?.focus({ preventScroll: true });

    if (reducedMotion) {
      paint(0, 0);
      if (sheetRef.current) sheetRef.current.style.opacity = "0";
      requestAnimationFrame(() => {
        if (sheetRef.current) sheetRef.current.style.opacity = "1";
        if (backdropRef.current) backdropRef.current.style.opacity = "1";
      });
    } else {
      paint(30, 0.72);
      animationRef.current = requestAnimationFrame(() => springActionRef.current(0, 1, 0));
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        dismissActionRef.current();
        return;
      }
      if (event.key !== "Tab" || !sheetRef.current) return;
      const controls = Array.from(sheetRef.current.querySelectorAll<HTMLElement>("button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex='0']"));
      if (controls.length === 0) {
        event.preventDefault();
        sheetRef.current.focus();
        return;
      }
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      stopAnimation();
      document.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus({ preventScroll: true });
    };
  }, [paint, stopAnimation]);

  function onHandlePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0 && event.pointerType === "mouse") return;
    stopAnimation();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startY: event.clientY,
      startOffset: offsetRef.current,
      lastY: event.clientY,
      lastTime: performance.now(),
      pointerVelocity: velocityRef.current,
      committed: false,
    };
  }

  function onHandlePointerMove(event: PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (drag.pointerId !== event.pointerId) return;
    const delta = event.clientY - drag.startY;
    if (!drag.committed && Math.abs(delta) < 10) return;
    drag.committed = true;
    event.preventDefault();
    const now = performance.now();
    const elapsed = Math.max(now - drag.lastTime, 1);
    drag.pointerVelocity = ((event.clientY - drag.lastY) / elapsed) * 1000;
    drag.lastY = event.clientY;
    drag.lastTime = now;
    const rawOffset = drag.startOffset + delta;
    const resistedOffset = rawOffset < 0 ? rawOffset * 0.55 : rawOffset;
    paint(resistedOffset);
  }

  function onHandlePointerUp(event: PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (drag.pointerId !== event.pointerId) return;
    drag.pointerId = -1;
    if (!drag.committed) {
      springActionRef.current(0, 1, velocityRef.current);
      return;
    }
    const shouldDismiss = offsetRef.current > 120 || drag.pointerVelocity > 720;
    if (shouldDismiss) {
      const exitDistance = Math.max(window.innerHeight, 600);
      const carryVelocity = Math.max(drag.pointerVelocity, 0);
      springActionRef.current(exitDistance, 0.8, carryVelocity, true);
    } else {
      springActionRef.current(0, 1, drag.pointerVelocity);
    }
  }

  return (
    <div
      ref={backdropRef}
      className="modal-backdrop sheet-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) dismissActionRef.current();
      }}
    >
      <section ref={sheetRef} className="document-modal document-sheet" role="dialog" aria-modal="true" aria-label="Document details" tabIndex={-1}>
        <div
          className="sheet-drag-handle"
          role="presentation"
          onPointerDown={onHandlePointerDown}
          onPointerMove={onHandlePointerMove}
          onPointerUp={onHandlePointerUp}
          onPointerCancel={onHandlePointerUp}
        >
          <span />
          <button className="sheet-close" type="button" onPointerDown={(event) => event.stopPropagation()} onClick={() => dismissActionRef.current()}>Close</button>
        </div>
        {children}
      </section>
    </div>
  );
}
