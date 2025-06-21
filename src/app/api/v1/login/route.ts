import { NextResponse } from 'next/server'
import { DEMO_USERS } from '@/config/auth'

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { username, password } = body

    if (!username || !password) {
      return NextResponse.json(
        { error: 'Username and password are required' },
        { status: 400 }
      )
    }

    // Find user in demo users list
    const user = DEMO_USERS.find(
      u => u.username === username && u.password === password
    )

    if (user) {
      // In production, use proper JWT signing
      const token = 'demo_token_' + Math.random().toString(36).substring(7)
      
      return NextResponse.json({
        access_token: token,
        user: {
          username: user.username,
          role: user.role,
          permissions: user.permissions
        },
        expires_in: '24h'
      })
    }

    return NextResponse.json(
      { error: 'Invalid username or password' },
      { status: 401 }
    )
  } catch (error) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
