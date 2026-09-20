import AtlasShell from "@/components/AtlasShell";

/**
 * Shared parent for every application route, so `AtlasShell` is mounted once
 * instead of once per route.
 *
 * The eight routes in this group used to each render their own `<AtlasShell />`.
 * Because Next.js remounts a route's subtree when a sibling route replaces it,
 * every navigation between them threw away the shell's entire state (2268 lines
 * of component state) and re-ran its boot sequence: the auth bootstrap, the
 * snapshot lifecycle, and the single-shot deep-link bootstrap. Hoisting the shell
 * into this layout makes Next.js keep it mounted across a navigation inside the
 * group and swap only `children`.
 *
 * The route's own `page.tsx` files render `null` on purpose. They exist so the
 * URL resolves; the shell chooses what to show from the current path and query
 * (see `useDeepLinkCycleBootstrap`, which reconciles the location on change), so
 * a route having no body of its own is the intended shape rather than a stub
 * waiting to be filled in.
 *
 * `/login` and `/ritual` deliberately live outside this group: neither may mount
 * the shell, and the forced-password-change gate that C9 enforces at the shell
 * boundary depends on the login route not mounting it.
 *
 * The `spa-route-shell` wrapper preserves the container each route used to
 * provide. It is not decorative: `.spa-route-shell` sets `position: relative`,
 * which is the containing block the shell's own floating elements were laid out
 * against. The per-route modifier classes (`--weekly`, `--admin`, and the rest)
 * had no CSS rules anywhere in `globals.css` — the selector list at
 * `.spa-route-shell` is stated once and the modifiers were never referenced — so
 * dropping them cannot change layout, and a single shared wrapper would only
 * fail to distinguish routes visually if such rules existed. The one genuinely
 * route-specific wrapper, `--dashboard`, was applied to the `/` route rather than
 * to `/dashboard`, which is itself evidence the modifiers were cosmetic.
 */
export default function ShellLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="spa-route-shell">
      <AtlasShell />
      {children}
    </div>
  );
}
