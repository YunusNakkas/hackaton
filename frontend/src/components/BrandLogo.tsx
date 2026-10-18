import { themeLogo, useTheme } from "../lib/theme";

export function BrandLogo() {
  const { theme } = useTheme();
  return <span className="flex h-10 w-10 shrink-0 items-center justify-center">
    <img src={themeLogo(theme)} alt="" aria-hidden="true" width={40} height={40} className="h-full w-full object-contain" />
  </span>;
}
