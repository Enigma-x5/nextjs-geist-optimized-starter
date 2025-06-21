"use client";

import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Polyline, Marker, Popup } from "react-leaflet";
import L from "leaflet";

interface VehiclePathMapProps {
  plate: string | null;
}

const VehiclePathMap: React.FC<VehiclePathMapProps> = ({ plate }) => {
  const [positions, setPositions] = useState<[number, number][]>([]);

  useEffect(() => {
    if (!plate) {
      setPositions([]);
      return;
    }

    const fetchPath = async () => {
      try {
        const token = localStorage.getItem("jwt_token");
        const res = await fetch(`/api/v1/plates/${plate}/path`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (data.geometry && data.geometry.coordinates) {
          const coords = data.geometry.coordinates.map(
            (coord: [number, number]) => [coord[1], coord[0]]
          );
          setPositions(coords);
        }
      } catch (error) {
        console.error("Error fetching plate path", error);
        setPositions([]);
      }
    };

    fetchPath();
  }, [plate]);

  return (
    <MapContainer
      center={positions.length > 0 ? positions[0] : [13.0827, 80.2707]}
      zoom={13}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://osm.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {positions.length > 0 && (
        <>
          <Polyline positions={positions} color="blue" />
          {positions.map((pos, idx) => (
            <Marker key={idx} position={pos}>
              <Popup>
                Point {idx + 1}: [{pos[0].toFixed(4)}, {pos[1].toFixed(4)}]
              </Popup>
            </Marker>
          ))}
        </>
      )}
    </MapContainer>
  );
};

export default VehiclePathMap;
