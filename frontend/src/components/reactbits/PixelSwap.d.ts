import type { ComponentType, CSSProperties, ReactNode } from "react";

export interface PixelSwapProps {
  firstContent: ReactNode;
  secondContent: ReactNode;
  pixelSize?: number;
  gap?: number;
  pixelRadius?: number;
  pixelSpin?: number;
  pixelScale?: number;
  fade?: boolean;
  duration?: number;
  pixelDuration?: number;
  pattern?: "random" | "center" | "edges" | "left-to-right" | "right-to-left" | "top-to-bottom" | "bottom-to-top" | "diagonal" | "spiral";
  randomness?: number;
  easing?: string;
  trigger?: "hover" | "click" | "manual";
  initialActive?: boolean;
  active?: boolean;
  onActiveChange?: (active: boolean) => void;
  onComplete?: (active: boolean) => void;
  aspectRatio?: string;
  className?: string;
  style?: CSSProperties;
}

declare const PixelSwap: ComponentType<PixelSwapProps>;
export default PixelSwap;
