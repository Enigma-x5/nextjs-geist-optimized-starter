# ANPR System Implementation Guide

## 1. Raw Live Footage Storage and Format

### Supported Formats:
- **Images**: JPEG, PNG (recommended: JPEG for smaller file sizes)
- **Videos**: MP4, H.264, RTSP streams
- **Resolution**: Minimum 720p, recommended 1080p for better OCR accuracy

### Storage Architecture:
```
/media/
├── raw_footage/
│   ├── camera_001/
│   │   ├── 2024-01-15/
│   │   │   ├── 14-30-45.jpg
│   │   │   └── 14-30-46.jpg
│   └── camera_002/
├── processed/
│   ├── plates/
│   │   ├── ABC123_2024-01-15_14-30-45.jpg
│   └── thumbnails/
└── archived/
```

### Implementation:
- **Cloud Storage**: AWS S3, Google Cloud Storage, Azure Blob
- **Local Storage**: NAS, SAN for high-speed access
- **Database**: PostgreSQL/MySQL for metadata
- **CDN**: CloudFront/CloudFlare for fast image delivery

### API Endpoint for Media Upload:
```typescript
// POST /api/v1/media/upload
{
  "file": File,
  "plateNumber": "ABC123",
  "cameraId": "CAM_001",
  "timestamp": "2024-01-15T14:30:45Z",
  "coordinates": { "lat": 13.0878, "lng": 80.2785 }
}
```

## 2. UI Improvements and Login Credentials

### Current Login Credentials:
Located in `src/config/auth.ts`:

```typescript
// Admin User
Username: admin
Password: password123
Role: admin
Permissions: view_all, search, export, manage_users

// Operator User  
Username: operator
Password: operator123
Role: operator
Permissions: view_all, search, export

// Viewer User
Username: viewer
Password: viewer123
Role: viewer
Permissions: view_limited, search
```

### How to Change Credentials:
1. **Development**: Edit `src/config/auth.ts`
2. **Production**: Use environment variables or secure database
3. **Security**: Hash passwords using bcrypt or similar

### UI Improvements Made:
- ✅ Separate login page (`/login`) and dashboard (`/dashboard`)
- ✅ Modern gradient background and card-based design
- ✅ Better typography and spacing
- ✅ Loading states and error handling
- ✅ Responsive design for mobile/tablet
- ✅ Toast notifications for user feedback
- ✅ Professional color scheme (blue/gray palette)

## 3. Latitude and Longitude Parameters

### Purpose:
- **Map Visualization**: Display vehicle path on interactive map
- **Geofencing**: Alert when vehicle enters/exits specific areas
- **Route Analysis**: Analyze traffic patterns and optimize routes
- **Evidence**: Provide location context for legal proceedings

### Data Structure:
```typescript
interface Sighting {
  timestamp: string;
  camera_id: string;
  lat: number;        // Required for map display
  lng: number;        // Required for map display
  confidence: number;
  speed: number;
  direction: string;
  image_url: string;
}
```

### Map Features:
- **Path Visualization**: Blue line connecting sighting points
- **Start/End Markers**: Green (start) and Red (end) markers
- **Camera Locations**: Show camera positions
- **Zoom to Fit**: Automatically adjust map bounds

## 4. Testing the System

### Test Scenarios:

#### A. Login Testing:
```bash
# Test different user roles
1. Login as admin (admin/password123)
2. Login as operator (operator/operator123)  
3. Login as viewer (viewer/viewer123)
4. Test invalid credentials
```

#### B. Search Testing:
```bash
# Test plate searches
1. Search for "ABC123" (has mock data)
2. Search for "XYZ789" (has mock data)
3. Search for "INVALID" (no data)
4. Test empty search
```

#### C. API Testing:
```bash
# Test endpoints with curl
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'

curl -X GET http://localhost:8000/api/v1/plates/ABC123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### D. Media Upload Testing:
```bash
curl -X POST http://localhost:8000/api/v1/media/upload \
  -F "file=@test_image.jpg" \
  -F "plateNumber=ABC123" \
  -F "cameraId=CAM_001"
```

### Test Data Available:
- **Plate Numbers**: ABC123, XYZ789, DEF456
- **Mock Coordinates**: Chennai, India area
- **Sample Images**: Placeholder URLs for demonstration

## 5. Security Implementation

### Current Security Features:
- ✅ Separate login page for better security
- ✅ JWT token-based authentication
- ✅ Route protection (dashboard requires login)
- ✅ Role-based access control
- ✅ Input validation and sanitization

### Production Security Recommendations:
```typescript
// 1. Environment Variables
JWT_SECRET=your-super-secret-key
DATABASE_URL=postgresql://...
STORAGE_BUCKET=your-s3-bucket

// 2. Password Hashing
import bcrypt from 'bcrypt';
const hashedPassword = await bcrypt.hash(password, 10);

// 3. HTTPS Only
const isProduction = process.env.NODE_ENV === 'production';
app.use(helmet({ hsts: isProduction }));

// 4. Rate Limiting
import rateLimit from 'express-rate-limit';
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
```

## 6. System Architecture

### Frontend Stack:
- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **Maps**: Leaflet with OpenStreetMap
- **State**: React hooks + localStorage

### Backend Stack:
- **API**: Next.js API Routes
- **Authentication**: JWT tokens
- **File Upload**: Multipart form handling
- **Database**: Mock data (replace with PostgreSQL/MongoDB)

### Deployment:
```bash
# Development
npm run dev

# Production Build
npm run build
npm start

# Docker Deployment
docker build -t anpr-dashboard .
docker run -p 3000:3000 anpr-dashboard
```

## 7. Integration with ANPR Hardware

### Camera Integration:
```typescript
// Real-time stream processing
interface CameraStream {
  id: string;
  rtsp_url: string;
  location: { lat: number; lng: number };
  status: 'active' | 'inactive';
}

// OCR Service Integration
interface OCRResult {
  plate_number: string;
  confidence: number;
  bounding_box: { x: number; y: number; width: number; height: number };
  processing_time_ms: number;
}
```

### Database Schema:
```sql
-- Vehicles table
CREATE TABLE vehicles (
  id SERIAL PRIMARY KEY,
  plate_number VARCHAR(20) UNIQUE,
  first_seen TIMESTAMP,
  last_seen TIMESTAMP,
  total_sightings INTEGER DEFAULT 0
);

-- Sightings table
CREATE TABLE sightings (
  id SERIAL PRIMARY KEY,
  vehicle_id INTEGER REFERENCES vehicles(id),
  camera_id VARCHAR(50),
  timestamp TIMESTAMP,
  latitude DECIMAL(10, 8),
  longitude DECIMAL(11, 8),
  confidence DECIMAL(3, 2),
  speed DECIMAL(5, 2),
  direction VARCHAR(10),
  image_url TEXT
);

-- Cameras table
CREATE TABLE cameras (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100),
  latitude DECIMAL(10, 8),
  longitude DECIMAL(11, 8),
  status VARCHAR(20),
  last_heartbeat TIMESTAMP
);
```

## 8. Performance Optimization

### Frontend Optimizations:
- ✅ Dynamic imports for map components
- ✅ Image lazy loading
- ✅ Component memoization
- ✅ Efficient re-renders

### Backend Optimizations:
- Database indexing on plate_number and timestamp
- Image compression and CDN delivery
- Caching frequently accessed data
- Pagination for large datasets

## 9. Monitoring and Alerts

### System Health:
- Camera status monitoring
- API response times
- Database performance
- Storage usage

### Business Alerts:
- High-confidence plate matches
- Vehicles of interest detected
- System downtime notifications
- Unusual traffic patterns

This comprehensive guide covers all aspects of the ANPR system implementation, testing, and deployment.
