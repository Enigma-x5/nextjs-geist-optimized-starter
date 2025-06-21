'use client';

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import VehiclePathMap from "@/components/VehiclePathMap";
import { useToast } from "@/components/ui/use-toast";

interface PlateSighting {
  timestamp: string;
  camera_id: string;
  lat: number;
  lng: number;
  confidence: number;
  speed?: number;
  direction?: string;
  image_url: string;
  vehicle_id: string;
}

export default function DashboardClient() {
  const [stats, setStats] = useState<{
    totalSightings: number;
    avgConfidence: number;
    uniqueCameras: number;
    timeRange: { start: string; end: string };
  }>({
    totalSightings: 0,
    avgConfidence: 0,
    uniqueCameras: 0,
    timeRange: { start: "", end: "" }
  });
  const [plateNumber, setPlateNumber] = useState("");
  const [sightings, setSightings] = useState<PlateSighting[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedPlate, setSelectedPlate] = useState<string | null>(null);
  const [showImageDialog, setShowImageDialog] = useState(false);
  const [selectedImage, setSelectedImage] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  
  const router = useRouter();
  const { toast } = useToast();

  useEffect(() => {
    const token = localStorage.getItem("jwt_token");
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      const response = await fetch("/api/v1/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("jwt_token", data.access_token);
        setIsAuthenticated(true);
        toast({
          title: "Success",
          description: "Successfully logged in",
        });
      } else {
        throw new Error("Invalid credentials");
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to login. Please check your credentials.",
        variant: "destructive",
      });
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("jwt_token");
    setIsAuthenticated(false);
    setSightings([]);
    setSelectedPlate(null);
  };

  const searchPlate = async () => {
    if (!plateNumber.trim()) {
      toast({
        title: "Error",
        description: "Please enter a plate number",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    setError("");
    
    try {
      const token = localStorage.getItem("jwt_token");
      const response = await fetch(`/api/v1/plates/${plateNumber}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch plate data");
      }

      const data = await response.json();
      setSightings(data);
      setSelectedPlate(plateNumber);
      
      if (data.length === 0) {
        toast({
          title: "No Results",
          description: "No sightings found for this plate number",
        });
      } else {
        const uniqueCameras = new Set(data.map((s: PlateSighting) => s.camera_id)).size;
        const avgConfidence = data.reduce((sum: number, s: PlateSighting) => sum + s.confidence, 0) / data.length;
        setStats({
          totalSightings: data.length,
          avgConfidence,
          uniqueCameras,
          timeRange: {
            start: new Date(data[data.length - 1].timestamp).toLocaleString(),
            end: new Date(data[0].timestamp).toLocaleString()
          }
        });
      }
    } catch (err) {
      setError("Failed to fetch plate data. Please try again.");
      toast({
        title: "Error",
        description: "Failed to fetch plate data",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleImageClick = (imageUrl: string) => {
    setSelectedImage(imageUrl);
    setShowImageDialog(true);
  };

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen bg-gray-100">
        <div className="m-auto w-full max-w-md p-8">
          <Card>
            <CardHeader>
              <CardTitle>Login to ANPR Dashboard</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <Input
                    type="text"
                    placeholder="Username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
                <Button type="submit" className="w-full">
                  Login
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">ANPR Dashboard</h1>
          <Button variant="outline" onClick={handleLogout}>
            Logout
          </Button>
        </div>

        <Card className="mb-8 shadow-lg">
          <CardHeader>
            <CardTitle>Search License Plate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 items-center">
              <Input
                type="text"
                placeholder="Enter plate number"
                value={plateNumber}
                onChange={(e) => setPlateNumber(e.target.value)}
                className="flex-1"
              />
              <Button onClick={searchPlate} disabled={loading}>
                {loading ? "Searching..." : "Search"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {error && (
          <Alert variant="destructive" className="mb-8">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {selectedPlate && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="shadow-md hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">Total Sightings</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{stats.totalSightings}</p>
                </CardContent>
              </Card>
              <Card className="shadow-md hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">Unique Cameras</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">{stats.uniqueCameras}</p>
                </CardContent>
              </Card>
              <Card className="shadow-md hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">Avg. Confidence</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-3xl font-bold">
                    {(stats.avgConfidence * 100).toFixed(1)}%
                  </p>
                </CardContent>
              </Card>
              <Card className="shadow-md hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">Time Range</CardTitle>
                </CardHeader>
                <CardContent className="text-sm">
                  <p className="font-semibold">Start: {stats.timeRange.start}</p>
                  <p className="font-semibold">End: {stats.timeRange.end}</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <Card className="shadow-lg">
                <CardHeader>
                  <CardTitle>Vehicle Path Map</CardTitle>
                </CardHeader>
                <CardContent className="h-[600px]">
                  <VehiclePathMap plate={selectedPlate} />
                </CardContent>
              </Card>

              <Card className="shadow-lg">
                <CardHeader>
                  <CardTitle>Sighting History</CardTitle>
                  <p className="text-sm text-gray-500">
                    Click on 'View' to see the plate image
                  </p>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Time</TableHead>
                          <TableHead>Camera</TableHead>
                          <TableHead>Confidence</TableHead>
                          <TableHead>Speed</TableHead>
                          <TableHead>Direction</TableHead>
                          <TableHead>Image</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {sightings.map((sighting, index) => (
                          <TableRow key={index}>
                            <TableCell>
                              {new Date(sighting.timestamp).toLocaleString()}
                            </TableCell>
                            <TableCell>{sighting.camera_id}</TableCell>
                            <TableCell>
                              {(sighting.confidence * 100).toFixed(1)}%
                            </TableCell>
                            <TableCell>
                              {sighting.speed ? `${sighting.speed.toFixed(1)} km/h` : "-"}
                            </TableCell>
                            <TableCell>{sighting.direction || "-"}</TableCell>
                            <TableCell>
                              <Button
                                variant="ghost"
                                onClick={() => handleImageClick(sighting.image_url)}
                              >
                                View
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        <Dialog 
          open={showImageDialog} 
          onOpenChange={setShowImageDialog}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Plate Image</DialogTitle>
            </DialogHeader>
            <div className="relative aspect-video">
              <img
                src={selectedImage}
                alt="License Plate"
                className="rounded-lg object-contain"
              />
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
