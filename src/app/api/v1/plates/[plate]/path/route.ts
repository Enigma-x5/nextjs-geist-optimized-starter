import { NextResponse } from 'next/server'

export async function GET(
  request: Request,
  { params }: { params: { plate: string } }
) {
  try {
    // Mock path data for demonstration
    const mockPath = {
      coordinates: [
        [13.0878, 80.2785], // Start point
        [13.0825, 80.2750], // Waypoint 1
        [13.0850, 80.2707], // End point
      ]
    }

    return NextResponse.json(mockPath)
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
