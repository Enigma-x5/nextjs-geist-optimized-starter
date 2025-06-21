import { NextResponse } from 'next/server'

export async function GET(
  request: Request,
  { params }: { params: { plate: string } }
) {
  try {
    // Mock data for demonstration
    const mockSightings = [
      {
        timestamp: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
        camera_id: "CAM_001",
        lat: 13.0878,
        lng: 80.2785,
        confidence: 0.95,
        speed: 45.5,
        direction: "North",
        image_url: "https://via.placeholder.com/400x300",
        vehicle_id: "VEH_001"
      },
      {
        timestamp: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
        camera_id: "CAM_002",
        lat: 13.0825,
        lng: 80.2750,
        confidence: 0.88,
        speed: 38.2,
        direction: "South",
        image_url: "https://via.placeholder.com/400x300",
        vehicle_id: "VEH_001"
      },
      {
        timestamp: new Date(Date.now() - 10800000).toISOString(), // 3 hours ago
        camera_id: "CAM_003",
        lat: 13.0850,
        lng: 80.2707,
        confidence: 0.92,
        speed: 42.0,
        direction: "East",
        image_url: "https://via.placeholder.com/400x300",
        vehicle_id: "VEH_001"
      }
    ]

    return NextResponse.json(mockSightings)
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
