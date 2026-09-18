import { create } from "zustand";

type UiState = { menuOpen: boolean; toggleMenu: () => void; closeMenu: () => void };

export const useUiStore = create<UiState>((set) => ({
  menuOpen: false,
  toggleMenu: () => set((state) => ({ menuOpen: !state.menuOpen })),
  closeMenu: () => set({ menuOpen: false })
}));
