"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface SliderProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  className?: string;
  label?: string;
  showValue?: boolean;
}

function Slider({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  disabled = false,
  className,
  label,
  showValue = true,
}: SliderProps) {
  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div className={cn("w-full", className)}>
      {(label || showValue) && (
        <div className="flex justify-between mb-2">
          {label && (
            <label className="text-sm font-medium text-[var(--foreground)]">
              {label}
            </label>
          )}
          {showValue && (
            <span className="text-sm text-[var(--muted-foreground)]">
              {value}
            </span>
          )}
        </div>
      )}
      <div className="relative h-5 flex items-center">
        <div className="relative w-full h-2 rounded-full bg-[var(--muted)]">
          <div
            className="absolute h-full rounded-full bg-[var(--primary)]"
            style={{ width: `${percentage}%` }}
          />
          <input
            type="range"
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            min={min}
            max={max}
            step={step}
            disabled={disabled}
            className={cn(
              "absolute w-full h-full opacity-0 cursor-pointer",
              disabled && "cursor-not-allowed"
            )}
          />
          <div
            className="absolute w-4 h-4 rounded-full bg-[var(--primary)] border-2 border-[var(--background)] shadow-md -translate-y-1/2 top-1/2 pointer-events-none"
            style={{ left: `calc(${percentage}% - 8px)` }}
          />
        </div>
      </div>
    </div>
  );
}

export { Slider };
