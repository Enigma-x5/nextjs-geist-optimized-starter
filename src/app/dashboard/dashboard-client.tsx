'use client';

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import VehiclePathMap from "@/components/VehiclePathMap";
import { useToast } from "@/components/ui/use-toast";

interface Sighting {
  timestamp: string;
  camera_id: string;
  lat: number;
  lng: number;
  confidence: number;
  vehicle_id: string;
}

export default function DashboardClient() {
  const [plateNumber, setPlateNumber] = useState("");
  const [sightings, setSightings] = useState<Sighting[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchPerformed, setSearchPerformed] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [showSightingHistory, setShowSightingHistory] = useState(false);
  const [mapKey, setMapKey] = useState(0);
  const router = useRouter();
  const { toast } = useToast();

  const handleLogout = () => {
    localStorage.removeItem("jwt_token");
    toast({
      title: "Logged out",
      description: "You have been successfully logged out",
    });
    router.push("/login");
  };

  const handleSearch = async () => {
    if (!plateNumber.trim()) {
      toast({
        title: "Error",
        description: "Please enter a license plate number",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem("jwt_token");
      const response = await fetch(`/api/v1/plates/${plateNumber}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSightings(data);
        setSearchPerformed(true);
        setMapKey(prev => prev + 1);
        toast({
          title: "Search completed",
          description: `Found ${data.length} sightings for ${plateNumber}`,
        });
      } else {
        throw new Error("Failed to fetch data");
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to search for license plate",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = () => {
    if (sightings.length === 0) return null;

    const totalSightings = sightings.length;
    const uniqueCameras = new Set(sightings.map(s => s.camera_id)).size;
    const avgConfidence = (sightings.reduce((sum, s) => sum + s.confidence, 0) / sightings.length * 100).toFixed(1);
    const timeRange = {
      start: new Date(Math.min(...sightings.map(s => new Date(s.timestamp).getTime()))),
      end: new Date(Math.max(...sightings.map(s => new Date(s.timestamp).getTime())))
    };

    return { totalSightings, uniqueCameras, avgConfidence, timeRange };
  };

  const stats = calculateStats();

  const filteredSightings = sightings.filter(sighting => {
    const sightingDate = new Date(sighting.timestamp);
    const start = startDate ? new Date(startDate) : null;
    const end = endDate ? new Date(endDate) : null;
    
    if (start && end) {
      return sightingDate >= start && sightingDate <= end;
    } else if (start) {
      return sightingDate >= start;
    } else if (end) {
      return sightingDate <= end;
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      {/* Header */}
      <header className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-white">ANPR Dashboard</h1>
            </div>
            <Button 
              onClick={handleLogout}
              variant="outline"
              className="border-white/30 text-white hover:bg-red-500/20 hover:text-red-300 hover:border-red-300 transition-all duration-300 transform hover:scale-105"
            >
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search Section */}
        <Card className="mb-8 bg-white/10 backdrop-blur-sm border-white/20">
          <CardHeader>
            <CardTitle className="text-xl text-white">Search License Plate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <Input
                placeholder="Enter plate number (e.g., ABC123)"
                value={plateNumber}
                onChange={(e) => setPlateNumber(e.target.value.toUpperCase())}
                className="flex-1 bg-white/10 border-white/20 text-white placeholder:text-gray-300"
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              />
              <Button 
                onClick={handleSearch} 
                disabled={loading}
                className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 transition-all duration-300 transform hover:scale-105"
              >
                {loading ? "Searching..." : "Search"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Statistics Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
            <Card className="bg-white/10 backdrop-blur-sm border-white/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-300">Total Sightings</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-blue-400">{stats.totalSightings}</div>
              </CardContent>
            </Card>

            <Card className="bg-white/10 backdrop-blur-sm border-white/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-300">Unique Cameras</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-green-400">{stats.uniqueCameras}</div>
              </CardContent>
            </Card>

            <Card className="bg-white/10 backdrop-blur-sm border-white/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-300">Avg. Confidence</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-purple-400">{stats.avgConfidence}%</div>
              </CardContent>
            </Card>

            <Card className="bg-white/10 backdrop-blur-sm border-white/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-300">Time Range</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-gray-300">
                  <div>Start: {stats.timeRange.start.toLocaleDateString()}</div>
                  <div>End: {stats.timeRange.end.toLocaleDateString()}</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/10 backdrop-blur-sm border-white/20 col-span-2">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-300">Filter by Date Range</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="startDate" className="text-gray-400 mb-2 block">Start Date</Label>
                  <Input
                    id="startDate"
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                <div>
                  <Label htmlFor="endDate" className="text-gray-400 mb-2 block">End Date</Label>
                  <Input
                    id="endDate"
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Map Section */}
        {searchPerformed && (
          <Card className="mb-8 bg-white/10 backdrop-blur-sm border-white/20">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-xl text-white">Vehicle Path Map</CardTitle>
              <Dialog open={showSightingHistory} onOpenChange={setShowSightingHistory}>
                <DialogTrigger asChild>
                  <Button 
                    variant="outline"
                    className="border-white/30 text-white hover:bg-white/10 transition-all duration-300 transform hover:scale-105"
                  >
                    View Sighting History
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto bg-slate-900/95 backdrop-blur-sm border-white/20">
                  <DialogHeader>
                    <DialogTitle className="text-white">Sighting History for {plateNumber}</DialogTitle>
                  </DialogHeader>
                  <div className="mt-4">
                    {filteredSightings.length > 0 ? (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow className="border-white/20">
                              <TableHead className="text-gray-300">Timestamp</TableHead>
                              <TableHead className="text-gray-300">Camera</TableHead>
                              <TableHead className="text-gray-300">Confidence</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {filteredSightings.map((sighting, index) => (
                              <TableRow key={index} className="border-white/10">
                                <TableCell className="font-medium text-white">
                                  {new Date(sighting.timestamp).toLocaleString()}
                                </TableCell>
                                <TableCell>
                                  <Badge variant="outline" className="border-blue-400 text-blue-400">
                                    {sighting.camera_id}
                                  </Badge>
                                </TableCell>
                                <TableCell>
                                  <Badge 
                                    variant={sighting.confidence > 0.9 ? "default" : "secondary"}
                                    className={sighting.confidence > 0.9 ? "bg-green-500" : "bg-yellow-500"}
                                  >
                                    {(sighting.confidence * 100).toFixed(1)}%
                                  </Badge>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-400">
                        No sightings found for the selected criteria.
                      </div>
                    )}
                  </div>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <div className="h-96 w-full rounded-lg overflow-hidden relative bg-gray-100">
                <VehiclePathMap key={`${plateNumber}-${mapKey}`} plate={plateNumber} />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Welcome Message */}
        {!searchPerformed && (
          <Card className="bg-white/10 backdrop-blur-sm border-white/20">
            <CardContent className="text-center py-12">
              <h2 className="text-2xl font-semibold text-white mb-4">
                Welcome to ANPR Dashboard
              </h2>
              <p className="text-gray-300 mb-6">
                Enter a license plate number above to search for vehicle sightings and track movement patterns.
              </p>
              <div className="bg-blue-500/20 p-4 rounded-lg inline-block border border-blue-500/30">
                <p className="text-sm text-blue-300">
                  <strong>Try searching for:</strong> ABC123, XYZ789, or DEF456
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
