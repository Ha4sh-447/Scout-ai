const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

export async function fetchRuns(token: string = "") {
  const res = await fetch(`${API_URL}/jobs/runs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch runs");
  return res.json();
}

export async function fetchRunDetails(runId: string, token: string = "") {
  const res = await fetch(`${API_URL}/jobs/runs/${runId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch run details");
  return res.json();
}

export async function fetchJobs(token: string = "") {
  const res = await fetch(`${API_URL}/jobs`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to fetch jobs");
  return res.json();
}

export async function triggerPipeline(
  params: { experience?: string, location?: string, queries?: string[], urls?: string[] } | null,
  schedulingOptions: { is_scheduled?: boolean, interval_hours?: number } = {},
  token: string = ""
) {
  const body = {
    queries: params?.queries || [],
    location: params?.location || undefined,
    experience: params?.experience || undefined,
    urls: params?.urls || [],
    is_scheduled: schedulingOptions.is_scheduled === true,  // Explicitly convert to boolean
    interval_hours: schedulingOptions.interval_hours || 3,
  };
  
  console.log("[API] triggerPipeline - enableScheduler state:", schedulingOptions.is_scheduled);
  console.log("[API] triggerPipeline - Sending body:", body);
  
  const res = await fetch(`${API_URL}/jobs/trigger`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to trigger pipeline");
  return res.json();
}

export async function cancelPipeline(runId: string, token: string) {
  const res = await fetch(`${API_URL}/jobs/${runId}/cancel`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to cancel pipeline");
  return res.json();
}

export async function updateSettings(settings: any, token: string) {
  const res = await fetch(`${API_URL}/users/settings`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error("Failed to update settings");
  return res.json();
}

export async function updateLinkedinCookie(cookie: string, token: string) {
  const res = await fetch(`${API_URL}/users/settings/linkedin-cookie`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ li_at_cookie: cookie }),
  });
  if (!res.ok) throw new Error("Failed to update LinkedIn cookie");
  return res.json();
}

export async function uploadResume(file: File, token: string) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/users/resume/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload resume");
  return res.json();
}

export async function fetchResumes(token: string) {
  const res = await fetch(`${API_URL}/users/resumes`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to fetch resumes");
  return res.json();
}
export async function fetchSettings(token: string) {
  const res = await fetch(`${API_URL}/users/settings`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}
export async function scrapeLinks(links: string[], token: string = "", schedulingOptions: { is_scheduled?: boolean, interval_hours?: number } = {}) {
  const body = {
    links,
    is_scheduled: schedulingOptions.is_scheduled === true,
    interval_hours: schedulingOptions.interval_hours || 3,
  };
  const res = await fetch(`${API_URL}/scrapers/scrape`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to trigger scraper");
  return res.json();
}

export async function saveSearchLinks(links: string[], token: string) {
  const res = await fetch(`${API_URL}/scrapers/save-search-links`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ links }),
  });
  if (!res.ok) throw new Error("Failed to save search links");
  return res.json();
}

export async function getSearchLinks(token: string) {
  const res = await fetch(`${API_URL}/scrapers/search-links`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to fetch search links");
  return res.json();
}

export async function deleteSearchLink(linkId: string, token: string) {
  const res = await fetch(`${API_URL}/scrapers/search-links/${linkId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to delete search link");
  return res.json();
}

export async function triggerBrowserAuthentication(token: string, platforms: string[] = ["linkedin", "wellfound"]) {
  const res = await fetch(`${API_URL}/scrapers/authenticate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ platforms }),
  });
  if (!res.ok) throw new Error("Failed to trigger browser authentication");
  return res.json();
}

export async function getAuthenticationStatus(token: string) {
  const res = await fetch(`${API_URL}/scrapers/authenticate/status`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to fetch authentication status");
  return res.json();
}

export async function clearBrowserSession(token: string) {
  const res = await fetch(`${API_URL}/scrapers/authenticate/session`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to clear browser session");
  return res.json();
}

export async function markPipelineFailed(runId: string, token: string) {
  const res = await fetch(`${API_URL}/jobs/${runId}/mark-failed`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) throw new Error("Failed to mark pipeline as failed");
  return res.json();
}
