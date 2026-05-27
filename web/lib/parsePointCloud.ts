export interface ParsedFrame {
  positions: Float32Array;
  pointCount: number;
}

const MAGIC_0 = 0x50; // 'P'
const MAGIC_1 = 0x43; // 'C'
const HEADER_BYTES = 6;

export function parseFrame(buffer: ArrayBuffer): ParsedFrame | null {
  if (buffer.byteLength < HEADER_BYTES) return null;

  const header = new Uint8Array(buffer, 0, HEADER_BYTES);
  if (header[0] !== MAGIC_0 || header[1] !== MAGIC_1) return null;

  const pointCount = new DataView(buffer, 2, 4).getUint32(0, true);
  const expectedBytes = HEADER_BYTES + pointCount * 12;
  if (buffer.byteLength !== expectedBytes) return null;

  // Zero-copy view — no allocation per frame.
  const positions = new Float32Array(buffer, HEADER_BYTES, pointCount * 3);
  return { positions, pointCount };
}
