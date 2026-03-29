from datetime import datetime
from datetime import timezone
from models.resume import MatchedJob
from models.config import EmailConfig
from agents.notification.state import NotificationState
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
logger = logging.getLogger(__name__)

async def notification_node(state: NotificationState) -> dict:
    jobs = state.get('jobs_with_drafts', [])
    cfg = state['email_cfg']
    run_label = state.get('run_label') or _default_run_label()
    user_id = state['user_id']

    logger.info(f"[notification_node] Building digest for user {user_id} {len(jobs)} jobs")

    if not jobs: 
        logger.info("[notification_node] No jobs to notify about - skipping email")
        return {
                "email_sent": False,
                "email_preview": "",
                "status": "notification_skipped"
                }

    html_body = _build_html(jobs, run_label)

    try:
        _send_email(cfg, run_label, html_body)
        logger.info(f"[notification_node] Email sent to {cfg.recipient_email}")
        return {
                "email_sent" : True,
                "email_preview" : html_body,
                "status": "notification_done"
                }
    except Exception as e:
        logger.error(f"[notification_node] Failed to send email: {e}")
        return {
                "email_sent": False,
                "email_preview": html_body,
                "errors": [f"SMTP error: {e}"],
                "status": "notification_failed"
                }
def _send_email(cfg: EmailConfig, run_label: str, html_body: str) -> None:
    subject = f"{cfg.subject_prefix} {run_label}"
    
    # Create MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.sender_email
    msg["To"] = cfg.recipient_email
    
    # Attach HTML content
    html_part = MIMEText(html_body, "html")
    msg.attach(html_part)
    
    # Connect to SMTP server with STARTTLS
    server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port)
    server.starttls()
    
    # Authenticate with sender email and password
    server.login(cfg.sender_email, cfg.sender_password)
    
    # Send the email
    server.sendmail(cfg.sender_email, cfg.recipient_email, msg.as_string())
    
    # Close connection
    server.quit()
 
def _build_html(jobs: list[MatchedJob], run_label: str) -> str:
    job_cards = "\n".join(_job_card(job) for job in jobs)
    total     = len(jobs)
    with_drafts = sum(1 for j in jobs if j.outreach_email_draft or j.outreach_linkedin_draft)
 
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;margin:0;padding:24px;color:#1a1a1a;}}
  .container{{max-width:680px;margin:0 auto;}}
  .header{{background:#1a1a2e;color:#fff;padding:24px 28px;border-radius:12px 12px 0 0;}}
  .header h1{{margin:0 0 4px;font-size:20px;font-weight:600;}}
  .header p{{margin:0;opacity:0.7;font-size:13px;}}
  .stats{{background:#16213e;color:#fff;padding:12px 28px;}}
  .stat{{font-size:13px;opacity:0.85;margin-right:24px;display:inline-block;}}
  .stat b{{color:#4f8ef7;}}
  .card{{background:#fff;margin:12px 0;border-radius:10px;border:1px solid #e8e8e8;overflow:hidden;}}
  .card-header{{padding:16px 20px 0;}}
  .rank{{font-size:11px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:0.5px;}}
  .score{{background:#f0f7ff;color:#1a5fb4;font-size:12px;font-weight:600;padding:3px 10px;border-radius:20px;border:1px solid #b6d4fe;float:right;}}
  .score.high{{background:#f0fdf4;color:#166534;border-color:#bbf7d0;}}
  .title{{padding:4px 20px 0;font-size:17px;font-weight:600;margin:0;clear:both;}}
  .company{{padding:2px 20px 0;font-size:13px;color:#555;}}
  .meta{{padding:8px 20px;font-size:12px;color:#777;}}
  .meta span{{background:#f5f5f5;padding:2px 8px;border-radius:4px;display:inline-block;margin:0 8px 4px 0;}}
  .skills{{padding:0 20px 10px;}}
  .skill{{background:#eff6ff;color:#2563eb;font-size:11px;font-weight:500;padding:2px 8px;border-radius:4px;border:1px solid #bfdbfe;display:inline-block;margin:0 6px 6px 0;}}
  .desc{{padding:10px 20px 12px;font-size:13px;color:#444;line-height:1.6;border-top:1px solid #f0f0f0;}}
  .outreach{{margin:0 20px 12px;background:#fefce8;border:1px solid #fef08a;border-radius:8px;padding:12px;}}
  .outreach-label{{font-size:11px;font-weight:600;color:#854d0e;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;}}
  .outreach pre{{font-family:inherit;font-size:12px;color:#713f12;white-space:pre-wrap;margin:0;line-height:1.5;}}
  .apply{{display:block;margin:0 20px 16px;background:#2563eb;color:#fff;text-decoration:none;text-align:center;padding:10px;border-radius:8px;font-size:13px;font-weight:500;}}
  .footer{{text-align:center;padding:20px;font-size:12px;color:#aaa;}}
  .platform-badge{{font-size:10px;font-weight:700;padding:2px 8px;border-radius:12px;text-transform:uppercase;letter-spacing:0.5px;color:#fff;display:inline-block;margin-left:8px;vertical-align:middle;}}
  .platform-linkedin{{background:#0a66c2;}}
  .platform-indeed{{background:#2557a7;}}
  .platform-wellfound{{background:#ff4d4f;}}
  .platform-glassdoor{{background:#0faa44;}}
  .platform-reddit{{background:#ff4500;}}
  .platform-generic{{background:#6b7280;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Job Digest</h1>
    <p>{run_label}</p>
  </div>
  <div class="stats">
    <span class="stat">Matched jobs: <b>{total}</b></span>
    <span class="stat">Outreach drafts ready: <b>{with_drafts}</b></span>
  </div>
  {job_cards}
  <div class="footer">
    This digest was generated automatically. Jobs are ranked by match score,
    recency, and source quality.
  </div>
</div>
</body>
</html>"""
    # Minify simple CSS: remove newlines and extra spaces inside the style block
    # and remove all newlines from the HTML to be extremely safe with email clients.
    return "".join(line.strip() for line in html.split("\n"))
 
 
def _job_card(job: MatchedJob) -> str:
    score_class = "high" if job.final_score >= 0.75 else ""
    score_pct   = f"{job.final_score:.0%}"
 
    # Meta pills: location, job_type, salary, experience
    meta_items = [f"📍 {job.location}"]
    if job.job_type:
        meta_items.append(" · ".join(job.job_type))
    if job.salary:
        meta_items.append(f"💰 {job.salary}")
    if job.experience:
        meta_items.append(f"⏱ {job.experience}")
    meta_html = "".join(f"<span>{m}</span>" for m in meta_items)
 
    # Skill chips — highlight top_matching_skills
    all_skills = job.skills[:8]
    skills_html = "".join(
        f'<span class="skill">{s}</span>' for s in all_skills
    )
 
    # Description excerpt - increased for better visibility
    desc_excerpt = (job.description or "")[:1200].rstrip()
    if len(job.description or "") > 1200:
        desc_excerpt += "…"
 
    # Outreach draft block (only if available)
    outreach_html = ""
 
    if job.outreach_email_draft:
        recruiter_name = ""
        if job.recruiter:
            recruiter_name = job.recruiter.get("name", "")
        label = f"Cold email draft{' for ' + recruiter_name if recruiter_name else ''}"
        outreach_html += f"""
    <div class="outreach">
      <div class="outreach-label">✉ {label}</div>
      <pre>{job.outreach_email_draft}</pre>
    </div>"""
 
    if job.outreach_linkedin_draft:
        recruiter_name = ""
        if job.recruiter:
            recruiter_name = job.recruiter.get("name", "")
        linkedin_url = job.recruiter.get("linkedin_url") or job.recruiter.get("profile_url", "#") if job.recruiter else "#"
        label = f"LinkedIn message draft{' for ' + recruiter_name if recruiter_name else ''}"
        outreach_html += f"""
    <div class="outreach" style="background:#f0fdf4;border-color:#bbf7d0;">
      <div class="outreach-label" style="color:#166534;">💼 {label} <a href="{linkedin_url}" style="font-size:10px;margin-left:6px;color:#166534;" target="_blank">Open profile →</a></div>
      <pre style="color:#14532d;">{job.outreach_linkedin_draft}</pre>
      <div style="font-size:10px;color:#166534;margin-top:4px;">⚠ {len(job.outreach_linkedin_draft)} / 280 chars</div>
    </div>"""
 
    # Poster type badge
    poster_note = ""
    if job.poster_type == "agency_recruiter":
        poster_note = '<span style="color:#b45309;font-size:11px;">⚠ Via recruiter</span>'
 
    resume_label = ""
    if job.resume_id and job.resume_id != "default":
        resume_label = f'<span style="background:#fef3c7;color:#92400e;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:8px;">Match: {job.resume_id}</span>'

    # Recency indicator
    recency_html = ""
    if job.posted_at_text:
        # Clean up if it contains "Posted at" or similar
        text = job.posted_at_text.replace("Posted", "").replace("posted", "").strip()
        recency_html = f'<span style="font-size:10px;color:#c2410c;font-weight:600;margin-left:8px;background:#fff7ed;padding:2px 6px;border-radius:4px;border:1px solid #ffedd5;">🕒 {text}</span>'

    # Platform Badge
    platform = (job.source_platform or "generic").lower()
    platform_label = platform.capitalize()
    if platform == "wellfound": platform_label = "Wellfound"
    
    platform_badge = f'<span class="platform-badge platform-{platform}">{platform_label}</span>'

    # Recruiter Info
    recruiter_html = ""
    if job.recruiter:
        # Handle both object (RecruiterInfo) and dict (from JSON/Qdrant)
        r = job.recruiter
        name = getattr(r, "name", None) or (r.get("name") if isinstance(r, dict) else None)
        link = getattr(r, "profile_url", None) or getattr(r, "linkedin_url", None) or \
               (r.get("profile_url") or r.get("linkedin_url") if isinstance(r, dict) else None)
        
        if name:
            if link:
                recruiter_html = f'<div style="font-size:12px;color:#666;margin-top:4px;">👤 Recruiter: <a href="{link}" target="_blank" style="color:#2563eb;text-decoration:none;">{name}</a></div>'
            else:
                recruiter_html = f'<div style="font-size:12px;color:#666;margin-top:4px;">👤 Recruiter: {name}</div>'

    # Experience Detail (if string is rich)
    exp_detail_html = ""
    if job.experience:
        exp_detail_html = f'<div style="font-size:12px;color:#c2410c;margin-top:4px;font-weight:600;">⏱ Experience: {job.experience}</div>'

    return f"""
  <div class="card">
    <div class="card-header">
      <span class="score {score_class}">{score_pct} match</span>
      <span class="rank">#{job.rank}</span>
      {platform_badge}
      {recency_html}
    </div>
    <h2 class="title">{job.title}</h2>
    <div class="company">{job.company} {poster_note} {resume_label}</div>
    <div class="meta">{meta_html}</div>
    {recruiter_html}
    {exp_detail_html}
    <div class="skills">{skills_html}</div>
    <div class="desc">{desc_excerpt}</div>
    {outreach_html}
    <a class="apply" href="{job.source_url}" target="_blank">View &amp; Apply →</a>
  </div>"""
 
 
def _default_run_label() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%-d %b %Y · %H:%M UTC")
 
