"use client";

import { useState, useEffect } from "react";
import { formatDistanceToNow } from "date-fns";
import {
  Clock, CheckCircle, AlertCircle, Loader2, RotateCw,
  TrendingUp, Users, Briefcase, Activity, X, Mail, Zap
} from "lucide-react";
import { fetchRunDetails, cancelPipeline } from "@/lib/api";

interface PipelineRun {
  id: string;
  status: string;
  jobs_found: number;
  jobs_matched: number;
  jobs_ranked: number;
  error_message?: string;
  started_at: string;
  completed_at?: string;
  updated_at: string;
  execution_count?: number;
  notification_email?: string;
  total_jobs_ranked?: number;
  active_duration_minutes?: number;
  is_scheduled?: boolean;
  interval_hours?: number;
}

interface PipelineHistoryProps {
  runs: PipelineRun[];
  token: string;
  activeRunId?: string | null;
  onRunCancelled?: () => void;
}

export default function PipelineHistory({ runs, token, activeRunId, onRunCancelled }: PipelineHistoryProps) {
  const [expandedRun, setExpandedRun] = useState<string | null>(activeRunId || null);
  const [runDetails, setRunDetails] = useState<{ [key: string]: PipelineRun }>({});
  const [pollingRunIds, setPollingRunIds] = useState<Set<string>>(new Set());
  const [cancelingRunId, setCancelingRunId] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<{ [key: string]: string }>({});

  useEffect(() => {
    const activeRun = runs.find(r => r.status === "running" || r.status === "pending");
    if (activeRun && !pollingRunIds.has(activeRun.id)) {
      setPollingRunIds(prev => new Set([...prev, activeRun.id]));
    }
  }, [runs.length]);

  useEffect(() => {
    const countdownInterval = setInterval(() => {
      const newCountdown: { [key: string]: string } = {};
      
      for (const run of runs) {
        if (run.is_scheduled && run.status === "running" && run.completed_at) {
          const interval = run.interval_hours || 3;
          
          const completedTime = new Date(run.completed_at).getTime();
          const nextExecutionTime = completedTime + (interval * 60 * 60 * 1000);
          const now = Date.now();
          const timeRemaining = nextExecutionTime - now;

          const absTimeRemaining = Math.abs(timeRemaining);
          const hours = Math.floor(absTimeRemaining / (60 * 60 * 1000));
          const minutes = Math.floor((absTimeRemaining % (60 * 60 * 1000)) / (60 * 1000));
          const seconds = Math.floor((absTimeRemaining % (60 * 1000)) / 1000);
          const timeString = `${hours}h ${minutes}m ${seconds}s`;
          
          if (timeRemaining > 0) {
            newCountdown[run.id] = timeString;
          } else {
            newCountdown[run.id] = `Overdue by ${timeString}`;
          }
        }
      }
      
      setCountdown(newCountdown);
    }, 1000);

    return () => clearInterval(countdownInterval);
  }, [runs]);

  useEffect(() => {
    if (pollingRunIds.size === 0) return;

    const pollInterval = setInterval(async () => {
      const stillActive: Set<string> = new Set();
      
      for (const runId of pollingRunIds) {
        try {
          const details = await fetchRunDetails(runId, token);
          setRunDetails(prev => ({ ...prev, [runId]: details }));

          if ((details.status === "running" || details.status === "pending") && !details.completed_at) {
            stillActive.add(runId);
          }
        } catch (error) {
          console.error(`Failed to poll run ${runId}:`, error);
          stillActive.add(runId);
        }
      }
      
      setPollingRunIds(stillActive);
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [pollingRunIds, token]);

  const getStatusIcon = (status: string, completed_at?: string) => {
    if (status === "running" && completed_at) {
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    
    switch (status) {
      case "running":
      case "pending":
        return <Loader2 className="w-5 h-5 animate-spin text-blue-500" />;
      case "failed":
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case "cancelled":
        return <X className="w-5 h-5 text-orange-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string, completed_at?: string) => {
    if (status === "running" && completed_at) {
      return "bg-green-50 border-green-200";
    }
    
    switch (status) {
      case "running":
      case "pending":
        return "bg-blue-50 border-blue-200";
      case "failed":
        return "bg-red-50 border-red-200";
      case "cancelled":
        return "bg-orange-50 border-orange-200";
      default:
        return "bg-gray-50 border-gray-200";
    }
  };

  const getStatusBadge = (status: string, completed_at?: string, is_scheduled?: boolean) => {
    const baseClass = "px-3 py-1 rounded-full text-sm font-medium";
    
    if (status === "running" && completed_at && is_scheduled) {
      return `${baseClass} bg-purple-100 text-purple-700`;
    }
    
    if (status === "done" || (status === "running" && completed_at && !is_scheduled)) {
      return `${baseClass} bg-green-100 text-green-700`;
    }
    
    switch (status) {
      case "running":
      case "pending":
        return `${baseClass} bg-blue-100 text-blue-700`;
      case "failed":
        return `${baseClass} bg-red-100 text-red-700`;
      case "cancelled":
        return `${baseClass} bg-orange-100 text-orange-700`;
      default:
        return `${baseClass} bg-gray-100 text-gray-700`;
    }
  };

  const formatTime = (dateString: string) => {
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return "Unknown";
    }
  };

  const formatLocalDateTime = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      });
    } catch {
      return "Unknown";
    }
  };

  const calculateDuration = (startedAt: string, completedAt?: string) => {
    try {
      const start = new Date(startedAt);
      const end = completedAt ? new Date(completedAt) : new Date();
      
      const diffMs = Math.abs(end.getTime() - start.getTime());
      const totalSeconds = Math.floor(diffMs / 1000);
      
      if (!completedAt && totalSeconds >= 5) {
        return "Running...";
      }
      
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const secs = totalSeconds % 60;
      
      if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
      } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
      } else {
        return `${secs}s`;
      }
    } catch {
      return "Unknown";
    }
  };

  const handleCancelRun = async (runId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to cancel this pipeline run?")) return;
    
    try {
      setCancelingRunId(runId);
      await cancelPipeline(runId, token);
      if (onRunCancelled) onRunCancelled();
    } catch (error) {
      alert("Failed to cancel pipeline: " + (error as Error).message);
    } finally {
      setCancelingRunId(null);
    }
  };

  if (!runs || runs.length === 0) {
    return (
      <div className="text-center py-12 bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg border border-gray-200">
        <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-600 font-medium">No pipeline runs yet</p>
        <p className="text-gray-500 text-sm">Trigger a job discovery to see history</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">Pipeline Execution History</h3>
      {runs.map((run, index) => {
        const isExpanded = expandedRun === run.id;
        const displayRun = runDetails[run.id] || run;
        const isRunning = displayRun.status === "running" || displayRun.status === "pending";

        return (
          <div
            key={run.id}
            className={`border rounded-lg transition-all cursor-pointer ${getStatusColor(displayRun.status, displayRun.completed_at)}`}
            onClick={() => setExpandedRun(isExpanded ? null : run.id)}
          >
            {/* Header */}
            <div className="p-4 flex items-start justify-between">
              <div className="flex items-start gap-3 flex-1">
                {getStatusIcon(displayRun.status, displayRun.completed_at)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-gray-800 truncate">
                      Pipeline {displayRun.id.substring(0, 8)} 
                      {displayRun.execution_count && displayRun.execution_count > 1 
                        ? ` - Execution #${displayRun.execution_count}`
                        : ` - Execution #1`
                      }
                    </span>
                    {displayRun.is_scheduled && (
                      <span className="text-xs bg-purple-200 text-purple-700 px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
                        <Zap size={12} /> Scheduled
                      </span>
                    )}
                    <span className={getStatusBadge(displayRun.status, displayRun.completed_at, displayRun.is_scheduled)}>
                      {displayRun.status === "pending" 
                        ? "Queued" 
                        : displayRun.status === "running" && displayRun.completed_at 
                          ? (displayRun.is_scheduled ? "Scheduled" : "Completed")
                          : displayRun.status === "done"
                            ? "Completed"
                            : displayRun.status}
                    </span>
                  </div>
                </div>
              </div>

              {/* Quick Stats and Cancel Button */}
              <div className="ml-4 flex items-center gap-3">
                <div className="text-right text-sm">
                  {displayRun.is_scheduled && displayRun.status === "running" && displayRun.completed_at && countdown[displayRun.id] ? (
                    <div className="flex items-center gap-2 bg-purple-100 px-3 py-2 rounded-lg border border-purple-300">
                      <Zap className="w-4 h-4 text-purple-600 flex-shrink-0" />
                      <div>
                        <p className="text-xs text-purple-700 font-medium">Next in</p>
                        <p className="font-bold text-purple-700 text-sm">{countdown[displayRun.id]}</p>
                      </div>
                    </div>
                  ) : displayRun.status === "running" && displayRun.completed_at ? (
                    <div className="text-xs text-emerald-600">
                      <p className="font-medium">Completed</p>
                    </div>
                  ) : displayRun.status === "done" ? (
                    <div className="text-xs text-emerald-600">
                      <p className="font-medium">Completed</p>
                    </div>
                  ) : (
                    <p className="font-medium text-gray-800">
                      {calculateDuration(displayRun.started_at, displayRun.completed_at)}
                    </p>
                  )}
                </div>
                
                {/* Cancel Button for Running/Pending Runs */}
                {isRunning && (
                  <button
                    onClick={(e) => handleCancelRun(displayRun.id, e)}
                    disabled={cancelingRunId === displayRun.id}
                    className="p-2 rounded-lg bg-red-100 hover:bg-red-200 text-red-600 transition-colors disabled:opacity-50"
                    title="Cancel this pipeline run"
                  >
                    {cancelingRunId === displayRun.id ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <X className="w-5 h-5" />
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Expanded Details */}
            {isExpanded && (
              <div className="border-t px-4 py-4 space-y-3 bg-opacity-5">
                {/* Status Indicator for Running Pipelines */}
                {isRunning && (
                  <div className="bg-blue-50 border border-blue-200 rounded p-3 flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                    <div>
                      <p className="text-sm font-medium text-blue-900">Pipeline is currently executing</p>
                      <p className="text-xs text-blue-700">Check back to see results as they're discovered</p>
                    </div>
                  </div>
                )}

                {/* Progress Indicators */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-white rounded p-3 border border-gray-200">
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingUp className="w-4 h-4 text-blue-500" />
                      <span className="text-xs font-medium text-gray-600">Discovered</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900">{displayRun.jobs_found}</p>
                  </div>

                  <div className="bg-white rounded p-3 border border-gray-200">
                    <div className="flex items-center gap-2 mb-1">
                      <Users className="w-4 h-4 text-purple-500" />
                      <span className="text-xs font-medium text-gray-600">Matched</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900">{displayRun.jobs_matched}</p>
                  </div>

                  <div className="bg-white rounded p-3 border border-gray-200">
                    <div className="flex items-center gap-2 mb-1">
                      <Briefcase className="w-4 h-4 text-green-500" />
                      <span className="text-xs font-medium text-gray-600">Ranked</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900">{displayRun.jobs_ranked}</p>
                  </div>
                </div>

                {/* Additional Statistics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <div className="bg-blue-50 rounded p-3 border border-blue-200">
                    <div className="flex items-center gap-2 mb-1">
                      <RotateCw className="w-4 h-4 text-blue-500" />
                      <span className="text-xs font-medium text-gray-600">Executed</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900">{displayRun.execution_count || 1}x</p>
                  </div>

                  <div className="bg-cyan-50 rounded p-3 border border-cyan-200">
                    <div className="flex items-center gap-2 mb-1">
                      <Clock className="w-4 h-4 text-cyan-500" />
                      <span className="text-xs font-medium text-gray-600">Active</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900">
                      {displayRun.active_duration_minutes !== undefined && displayRun.active_duration_minutes > 0
                        ? displayRun.active_duration_minutes >= 60
                          ? `${Math.floor(displayRun.active_duration_minutes / 60)}h ${displayRun.active_duration_minutes % 60}m`
                          : `${displayRun.active_duration_minutes}m`
                        : 'N/A'}
                    </p>
                  </div>

                  <div className="bg-indigo-50 rounded p-3 border border-indigo-200">
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingUp className="w-4 h-4 text-indigo-500" />
                      <span className="text-xs font-medium text-gray-600">Total Ranked</span>
                    </div>
                    <p className="text-xl font-bold text-gray-900">{displayRun.jobs_ranked || 0}</p>
                  </div>

                  <div className="bg-amber-50 rounded p-3 border border-amber-200">
                    <div className="flex items-center gap-2 mb-1">
                      <Mail className="w-4 h-4 text-amber-500" />
                      <span className="text-xs font-medium text-gray-600">Receiver</span>
                    </div>
                    <p className="text-xs font-bold text-gray-900 truncate">{displayRun.notification_email || 'N/A'}</p>
                  </div>
                </div>

                {/* Pipeline Progress Bar */}
                {isRunning ? (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-gray-600">Pipeline Progress</p>
                    <div className="flex gap-1">
                      <div className="flex-1">
                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all"
                            style={{
                              width: displayRun.jobs_found > 0 ? "100%" : "33%",
                            }}
                          />
                        </div>
                        <p className="text-xs text-gray-600 mt-1">Discovery</p>
                      </div>
                      <div className="flex-1">
                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-purple-500 rounded-full transition-all"
                            style={{
                              width: displayRun.jobs_matched > 0 ? "100%" : "0%",
                            }}
                          />
                        </div>
                        <p className="text-xs text-gray-600 mt-1">Matching</p>
                      </div>
                      <div className="flex-1">
                        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded-full transition-all"
                            style={{
                              width: displayRun.jobs_ranked > 0 ? "100%" : "0%",
                            }}
                          />
                        </div>
                        <p className="text-xs text-gray-600 mt-1">Ranking</p>
                      </div>
                    </div>
                  </div>
                ) : null}

                {/* Error Message - Prominent Display */}
                {displayRun.error_message && displayRun.status === "failed" && (
                  <div className="bg-red-50 border border-red-200 rounded p-4">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-semibold text-red-900 mb-1">Pipeline Failed</p>
                        <p className="text-sm text-red-800 break-words">{displayRun.error_message}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Timestamps */}
                <div className="text-xs text-gray-600 space-y-1 bg-gray-50 rounded p-3">
                  <p>
                    <span className="font-medium">Started (Local):</span> {formatLocalDateTime(displayRun.started_at)}
                  </p>
                  {displayRun.completed_at && (
                    <p>
                      <span className="font-medium">Completed (Local):</span> {formatLocalDateTime(displayRun.completed_at)}
                    </p>
                  )}
                </div>

                {/* Countdown Timer - Show if pipeline is completed */}
                {displayRun.status === "running" && displayRun.completed_at && countdown[displayRun.id] && (
                  <div className="bg-purple-50 border border-purple-200 rounded p-4 flex items-start gap-3">
                    <Zap className="w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-semibold text-purple-900 mb-1">Next Scheduled Execution</p>
                      <p className="text-blue-600 text-lg font-bold">{countdown[displayRun.id]}</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
