const RTL_REGEX = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;

export function isRtl(text: string): boolean {
  return RTL_REGEX.test(text);
}

export function rtlStyle(text: string): React.CSSProperties | undefined {
  return isRtl(text) ? { direction: "rtl", textAlign: "right" } : undefined;
}
