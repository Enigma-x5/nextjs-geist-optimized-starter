'use client';

import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface VehiclePathMapProps {
  plate: string;
}

export default function VehiclePathMap({ plate }: VehiclePathMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initialize map
    if (!mapRef.current && mapContainerRef.current) {
      mapRef.current = L.map(mapContainerRef.current).setView([13.0878, 80.2785], 13);
      
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
      }).addTo(mapRef.current);
    }

    // Fetch and display path data
    const fetchPath = async () => {
      try {
        const token = localStorage.getItem('jwt_token');
        const response = await fetch(`/api/v1/plates/${plate}/path`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });

        if (!response.ok) throw new Error('Failed to fetch path data');

        const data = await response.json();
        
        if (data.coordinates && data.coordinates.length > 0 && mapRef.current) {
          // Create path line
          const pathLine = L.polyline(data.coordinates, {
            color: 'blue',
            weight: 3,
            opacity: 0.7
          }).addTo(mapRef.current);

          // Add markers for start and end points
          const startPoint = data.coordinates[0];
          const endPoint = data.coordinates[data.coordinates.length - 1];

          L.marker(startPoint, {
            icon: L.divIcon({
              className: 'custom-div-icon',
              html: '<div style="background-color: green; width: 10px; height: 10px; border-radius: 50%;"></div>',
              iconSize: [10, 10]
            })
          }).addTo(mapRef.current);

          L.marker(endPoint, {
            icon: L.divIcon({
              className: 'custom-div-icon',
              html: '<div style="background-color: red; width: 10px; height: 10px; border-radius: 50%;"></div>',
              iconSize: [10, 10]
            })
          }).addTo(mapRef.current);

          // Add waypoint marker
          const waypoint = data.coordinates[1];
          L.marker(waypoint, {
            icon: L.divIcon({
              className: 'custom-div-icon',
              html: '<div style="background-color: yellow; width: 10px; height: 10px; border-radius: 50%;"></div>',
              iconSize: [10, 10]
            })
          }).addTo(mapRef.current);

          // Fit map bounds to show entire path
          mapRef.current.fitBounds(pathLine.getBounds(), { padding: [50, 50] });
        }
      } catch (error) {
        console.error('Error fetching path data:', error);
      }
    };

    if (plate) {
      fetchPath();
    }

    // Cleanup
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [plate]);

  return (
    <div 
      ref={mapContainerRef} 
      className="w-full h-full rounded-lg"
      style={{ minHeight: '400px' }}
    />
  );
}
