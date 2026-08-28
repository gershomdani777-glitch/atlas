import type { ComponentType } from "react";

export interface TargetCursorProps {
  targetSelector?: string;
  spinDuration?: number;
  hideDefaultCursor?: boolean;
  hoverDuration?: number;
  parallaxOn?: boolean;
  cursorColor?: string;
  cursorColorOnTarget?: string;
}

declare const TargetCursor: ComponentType<TargetCursorProps>;
export default TargetCursor;
