import type { ComponentType, ReactNode } from "react";

export interface AnimatedListProps {
  items?: unknown[];
  renderItem?: (item: unknown, index: number) => ReactNode;
  onItemSelect?: (item: unknown, index: number) => void;
  showGradients?: boolean;
  enableArrowNavigation?: boolean;
  className?: string;
  itemClassName?: string;
  displayScrollbar?: boolean;
  initialSelectedIndex?: number;
}

declare const AnimatedList: ComponentType<AnimatedListProps>;
export default AnimatedList;
