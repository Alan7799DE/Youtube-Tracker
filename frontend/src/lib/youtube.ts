// Link directo al video, opcionalmente al timestamp de la evidencia.
export function youtubeTimestampUrl(videoId: string, seconds: number | null): string {
  const base = `https://youtu.be/${videoId}`;
  return seconds && seconds > 0 ? `${base}?t=${seconds}` : base;
}
