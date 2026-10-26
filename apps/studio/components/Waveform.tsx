"use client";

import { useEffect, useRef } from "react";

export function Waveform({ url }: { url: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !url) return;
    let disposed = false;
    let destroy: (() => void) | undefined;

    void import("wavesurfer.js").then(({ default: WaveSurfer }) => {
      if (disposed || !containerRef.current) return;
      const instance = WaveSurfer.create({
        container: containerRef.current,
        url,
        height: 72,
        normalize: true,
        cursorWidth: 1,
      });
      destroy = () => instance.destroy();
    });

    return () => {
      disposed = true;
      destroy?.();
    };
  }, [url]);

  return <div ref={containerRef} className="waveform" aria-label="Local audio waveform" />;
}
