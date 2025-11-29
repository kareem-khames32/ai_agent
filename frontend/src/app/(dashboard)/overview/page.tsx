"use client";

import * as React from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/loading";
import {
  Phone,
  Clock,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Calendar,
  RefreshCw,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from "recharts";

// Mock data for demonstration
const mockMetrics = {
  totalCallMinutes: 1247,
  totalCallMinutesTrend: 12.5,
  numberOfCalls: 342,
  numberOfCallsTrend: 8.2,
  totalSpent: 156.78,
  totalSpentTrend: -3.4,
  averageCostPerCall: 0.46,
  averageCostPerCallTrend: -5.1,
};

const endedReasonData = [
  { reason: "Customer Ended", count: 145 },
  { reason: "Assistant Ended", count: 98 },
  { reason: "Timeout", count: 42 },
  { reason: "Voicemail", count: 35 },
  { reason: "Error", count: 22 },
];

const assistantDurationData = [
  { name: "Sales Agent", avgDuration: 4.2 },
  { name: "Support Agent", avgDuration: 6.8 },
  { name: "Booking Agent", avgDuration: 3.5 },
  { name: "Collection Agent", avgDuration: 5.1 },
];

const costBreakdownData = [
  { date: "Mon", llm: 12, stt: 8, tts: 15 },
  { date: "Tue", llm: 15, stt: 10, tts: 18 },
  { date: "Wed", llm: 18, stt: 12, tts: 22 },
  { date: "Thu", llm: 14, stt: 9, tts: 17 },
  { date: "Fri", llm: 20, stt: 14, tts: 25 },
  { date: "Sat", llm: 8, stt: 5, tts: 10 },
  { date: "Sun", llm: 6, stt: 4, tts: 8 },
];

const callVolumeData = [
  { time: "00:00", calls: 5 },
  { time: "04:00", calls: 3 },
  { time: "08:00", calls: 25 },
  { time: "12:00", calls: 45 },
  { time: "16:00", calls: 38 },
  { time: "20:00", calls: 22 },
];

const COLORS = ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"];

interface StatCardProps {
  title: string;
  value: string | number;
  trend?: number;
  icon: React.ReactNode;
  prefix?: string;
}

function StatCard({ title, value, trend, icon, prefix }: StatCardProps) {
  const isPositive = trend && trend > 0;
  const TrendIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <Card className="hover:bg-[var(--card)]">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-[var(--muted-foreground)]">
          {title}
        </CardTitle>
        <div className="text-[var(--muted-foreground)]">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">
          {prefix}
          {typeof value === "number" ? value.toLocaleString() : value}
        </div>
        {trend !== undefined && (
          <div className="flex items-center mt-1">
            <TrendIcon
              className={`h-4 w-4 mr-1 ${
                isPositive ? "text-[var(--success)]" : "text-[var(--error)]"
              }`}
            />
            <span
              className={`text-xs ${
                isPositive ? "text-[var(--success)]" : "text-[var(--error)]"
              }`}
            >
              {Math.abs(trend)}% from last period
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  const [dateRange, setDateRange] = React.useState("7d");
  const [assistantFilter, setAssistantFilter] = React.useState("all");
  const [isLoading, setIsLoading] = React.useState(false);

  const handleRefresh = () => {
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 1000);
  };

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Select
            value={dateRange}
            onChange={setDateRange}
            options={[
              { value: "24h", label: "Last 24 Hours" },
              { value: "7d", label: "Last 7 Days" },
              { value: "30d", label: "Last 30 Days" },
              { value: "90d", label: "Last 90 Days" },
            ]}
          />
          <Select
            value={assistantFilter}
            onChange={setAssistantFilter}
            options={[
              { value: "all", label: "All Assistants" },
              { value: "sales", label: "Sales Agent" },
              { value: "support", label: "Support Agent" },
              { value: "booking", label: "Booking Agent" },
            ]}
          />
        </div>
        <Button variant="outline" onClick={handleRefresh} isLoading={isLoading}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Call Minutes"
          value={mockMetrics.totalCallMinutes}
          trend={mockMetrics.totalCallMinutesTrend}
          icon={<Clock className="h-5 w-5" />}
        />
        <StatCard
          title="Number of Calls"
          value={mockMetrics.numberOfCalls}
          trend={mockMetrics.numberOfCallsTrend}
          icon={<Phone className="h-5 w-5" />}
        />
        <StatCard
          title="Total Spent"
          value={mockMetrics.totalSpent.toFixed(2)}
          trend={mockMetrics.totalSpentTrend}
          icon={<DollarSign className="h-5 w-5" />}
          prefix="$"
        />
        <StatCard
          title="Avg Cost per Call"
          value={mockMetrics.averageCostPerCall.toFixed(2)}
          trend={mockMetrics.averageCostPerCallTrend}
          icon={<DollarSign className="h-5 w-5" />}
          prefix="$"
        />
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Call Volume Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Call Volume</CardTitle>
            <CardDescription>Calls over time</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={callVolumeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="time"
                    stroke="var(--muted-foreground)"
                    fontSize={12}
                  />
                  <YAxis stroke="var(--muted-foreground)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "8px",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="calls"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    dot={{ fill: "var(--primary)" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Ended Reason Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Reason Call Ended</CardTitle>
            <CardDescription>Distribution of call end reasons</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={endedReasonData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="count"
                    nameKey="reason"
                    label={({ reason, percent }) =>
                      `${reason} (${(percent * 100).toFixed(0)}%)`
                    }
                    labelLine={false}
                  >
                    {endedReasonData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "8px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Average Duration by Assistant */}
        <Card>
          <CardHeader>
            <CardTitle>Average Call Duration by Assistant</CardTitle>
            <CardDescription>Minutes per call</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={assistantDurationData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" stroke="var(--muted-foreground)" fontSize={12} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    stroke="var(--muted-foreground)"
                    fontSize={12}
                    width={100}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "8px",
                    }}
                    formatter={(value: number) => [`${value} min`, "Avg Duration"]}
                  />
                  <Bar dataKey="avgDuration" fill="var(--primary)" radius={4} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Cost Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle>Cost Breakdown</CardTitle>
            <CardDescription>LLM, STT, and TTS costs</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={costBreakdownData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="date"
                    stroke="var(--muted-foreground)"
                    fontSize={12}
                  />
                  <YAxis stroke="var(--muted-foreground)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "8px",
                    }}
                    formatter={(value: number) => [`$${value}`, ""]}
                  />
                  <Bar dataKey="llm" stackId="a" fill="#10b981" name="LLM" />
                  <Bar dataKey="stt" stackId="a" fill="#3b82f6" name="STT" />
                  <Bar dataKey="tts" stackId="a" fill="#8b5cf6" name="TTS" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-[#10b981]" />
                <span className="text-sm text-[var(--muted-foreground)]">LLM</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-[#3b82f6]" />
                <span className="text-sm text-[var(--muted-foreground)]">STT</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-[#8b5cf6]" />
                <span className="text-sm text-[var(--muted-foreground)]">TTS</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Calls</CardTitle>
          <CardDescription>Last 5 calls</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 rounded-lg bg-[var(--secondary)]"
              >
                <div className="flex items-center gap-4">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--primary)]/10">
                    <Phone className="h-5 w-5 text-[var(--primary)]" />
                  </div>
                  <div>
                    <p className="font-medium">+966 5xx xxx xxx</p>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      Sales Agent • 3:42
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <Badge variant={i % 2 === 0 ? "success" : "secondary"}>
                    {i % 2 === 0 ? "Success" : "Completed"}
                  </Badge>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    2 min ago
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
