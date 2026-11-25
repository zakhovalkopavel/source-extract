export type Point2 = [number, number];
export type Wt3 = [number, number, number];

export function cornersFromCalibration(
  components: string[],
  calibration: Record<string, number[]>,
): Point2[] {
  return components.map((name) => {
    const xy = calibration[name];
    if (!xy || xy.length < 2) throw new Error(`Missing calibration for ${name}`);
    return [Number(xy[0]), Number(xy[1])];
  });
}

export function normalizeWt(wt: number[] | Record<string, number>, components?: string[]): Wt3 {
  if (Array.isArray(wt)) {
    return [Number(wt[0]), Number(wt[1]), Number(wt[2])];
  }
  if (!components) {
    const vals = Object.values(wt);
    return [Number(vals[0]), Number(vals[1]), Number(vals[2])];
  }
  return [Number(wt[components[0]]), Number(wt[components[1]]), Number(wt[components[2]])];
}

export function wtToPixel(
  wt: number[] | Record<string, number>,
  corners: Point2[],
  components?: string[],
): Point2 {
  const [a0, b0, c0] = normalizeWt(wt, components);
  const a = a0 / 100;
  const b = b0 / 100;
  const c = c0 / 100;
  return [
    a * corners[0][0] + b * corners[1][0] + c * corners[2][0],
    a * corners[0][1] + b * corners[1][1] + c * corners[2][1],
  ];
}

export function pixelToWt(page: Point2, corners: Point2[]): Wt3 {
  const [[x1, y1], [x2, y2], [x3, y3]] = corners;
  const [x, y] = page;
  const denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3);
  if (Math.abs(denom) < 1e-12) return [100 / 3, 100 / 3, 100 / 3];
  let a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denom;
  let b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denom;
  let c = 1 - a - b;
  a = Math.max(a, 0);
  b = Math.max(b, 0);
  c = Math.max(c, 0);
  const s = a + b + c;
  if (s <= 0) return [100 / 3, 100 / 3, 100 / 3];
  return [Math.round((a / s) * 10000) / 100, Math.round((b / s) * 10000) / 100, Math.round((c / s) * 10000) / 100];
}
