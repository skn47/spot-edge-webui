"use client";

import { useEffect, useRef } from "react";
import { BufferGeometry, Float32BufferAttribute } from "three";
import { POINT_COLOR, POINT_SIZE } from "@/lib/constants";

interface PointCloudProps {
  positions: Float32Array;
  pointCount: number;
  pointSize?: number;
  color?: string;
}

export function PointCloud({
  positions,
  pointCount,
  pointSize = POINT_SIZE,
  color = POINT_COLOR,
}: PointCloudProps) {
  const geoRef = useRef<BufferGeometry>(null);

  useEffect(() => {
    const geo = geoRef.current;
    if (!geo) return;
    geo.setAttribute("position", new Float32BufferAttribute(positions, 3));
    geo.setDrawRange(0, pointCount);
    geo.computeBoundingSphere();
  }, [positions, pointCount]);

  useEffect(() => {
    return () => {
      geoRef.current?.dispose();
    };
  }, []);

  return (
    <points>
      <bufferGeometry ref={geoRef} />
      <pointsMaterial size={pointSize} color={color} sizeAttenuation />
    </points>
  );
}
