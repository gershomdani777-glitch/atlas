import type { ComponentType } from "react";

export interface FlowingMenuItem {
  link: string;
  text: string;
  image: string;
}

export interface FlowingMenuProps {
  items?: FlowingMenuItem[];
  speed?: number;
  textColor?: string;
  bgColor?: string;
  marqueeBgColor?: string;
  marqueeTextColor?: string;
  borderColor?: string;
}

declare const FlowingMenu: ComponentType<FlowingMenuProps>;
export default FlowingMenu;
