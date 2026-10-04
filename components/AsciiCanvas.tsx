"use client";

import React, { useEffect, useRef, useState } from "react";

interface AsciiCanvasProps {
  characters?: string;
  cellSize?: number;
  color?: string;
  direction?: "left" | "right" | "top" | "bottom";
  speed?: number;
  waveTension?: number;
  noiseScale?: number;
  intensity?: number;
  fontWeight?: number | string;
  className?: string;
  mode?: "ascii" | "dots";
}

let globalCanvasStartTime = 0;

export const AsciiCanvas: React.FC<AsciiCanvasProps> = ({
  characters = " ·•●",
  cellSize = 18,
  color,
  direction = "left",
  speed = 12,
  waveTension = 5,
  noiseScale = 12,
  intensity = 9,
  fontWeight = 400,
  className = "",
  mode = "dots",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameId = useRef<number>(0);
  const isIntersecting = useRef<boolean>(true);
  const [dimensions, setDimensions] = useState<{ w: number; h: number }>({ w: 0, h: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const rect = entry.contentRect;
        setDimensions({
          w: Math.max(1, Math.floor(rect.width)),
          h: Math.max(1, Math.floor(rect.height)),
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { w, h } = dimensions;
    if (w === 0 || h === 0) return;

    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.scale(dpr, dpr);

    const computed = getComputedStyle(container);
    const textColor =
      color?.trim() ||
      computed.getPropertyValue("--color-fg-faint").trim() ||
      "#7a7a82";
    const fontFamily =
      computed.fontFamily || "var(--font-mono), monospace";

    const sVal = speed / 20;
    const wVal = waveTension / 10;
    const nVal = noiseScale / 100;
    const iVal = intensity / 10;

    const dirMap: Record<string, [number, number]> = {
      left: [1, 0],
      right: [-1, 0],
      top: [0, 1],
      bottom: [0, -1],
    };
    const [dx, dy] = dirMap[direction] ?? dirMap.left;

    const cellH = Math.max(4, cellSize);
    const cellW = 0.6 * cellH;
    const cols = Math.ceil(w / cellW) + 1;
    const rows = Math.ceil(h / cellH) + 1;
    const chars = characters && characters.length ? characters : " .:-+*=%@#";
    const maxIdx = chars.length - 1;

    ctx.font = `${fontWeight} ${cellH}px ${fontFamily}`;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    ctx.fillStyle = textColor;

    const noise = (x: number, y: number, t: number) =>
      (Math.sin(1.3 * x + t) * Math.cos(1.1 * y - 0.7 * t) +
        Math.sin((x + y) * 0.7 + 0.5 * t) +
        Math.sin(0.4 * x - 0.6 * y + 0.3 * t)) /
      3;

    const renderFrame = (now: number) => {
      if (!globalCanvasStartTime) globalCanvasStartTime = now;
      const t = ((now - globalCanvasStartTime) / 1000) * sVal;

      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = textColor;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const shiftX = 2.2 * t * dx;
          const shiftY = 2.2 * t * dy;
          const raw =
            (noise(
              c * nVal + shiftX + 2.5 * Math.sin((r + t * 1.3) * 0.12),
              r * nVal + shiftY + 2.5 * Math.cos((c + t * 1.3) * 0.12),
              t * wVal * 1.4
            ) *
              iVal +
              1) /
            2;
          const clamped = Math.max(0, Math.min(1, raw));

          if (mode === "dots") {
            const radius = 0.8 + clamped * 2.8;
            ctx.globalAlpha = 0.25 + clamped * 0.75;
            ctx.beginPath();
            ctx.arc(c * cellW + cellW / 2, r * cellH + cellH / 2, radius, 0, Math.PI * 2);
            ctx.fill();
          } else {
            const char = chars.charAt(Math.round(clamped * maxIdx));
            if (char !== " ") {
              ctx.fillText(char, c * cellW, r * cellH);
            }
          }
        }
      }
      ctx.globalAlpha = 1.0;
    };

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      renderFrame(1000);
      return;
    }

    const iObserver = new IntersectionObserver(
      ([entry]) => {
        isIntersecting.current = entry.isIntersecting;
      },
      { threshold: 0 }
    );
    iObserver.observe(container);

    const tick = (time: number) => {
      if (isIntersecting.current) {
        renderFrame(time);
      }
      animFrameId.current = requestAnimationFrame(tick);
    };

    animFrameId.current = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(animFrameId.current);
      iObserver.disconnect();
    };
  }, [dimensions, characters, cellSize, color, direction, speed, waveTension, noiseScale, intensity, fontWeight, mode]);

  return (
    <div
      ref={containerRef}
      aria-hidden={true}
      className={className}
      style={{ fontFamily: "var(--font-mono)", overflow: "hidden" }}
    >
      <canvas ref={canvasRef} style={{ display: "block" }} />
    </div>
  );
};
