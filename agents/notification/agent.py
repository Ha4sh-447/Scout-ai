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
    """Send email via SMTP."""
    subject = f"{cfg.subject_prefix} {run_label}"
    
    try:
        if not cfg.smtp_host:
            raise ValueError("SMTP host is empty. Set EMAIL_SMTP_HOST in environment")
        if not cfg.sender_email:
            raise ValueError("Sender email is empty. Set EMAIL_SENDER in environment")
        if not cfg.sender_password:
            raise ValueError("Sender password is empty. Set EMAIL_PASSWORD in environment")
        if not cfg.recipient_email:
            raise ValueError("Recipient email is not configured")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.sender_email
        msg["To"] = cfg.recipient_email
        
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)
        
        logger.info(f"[_send_email] Connecting to SMTP server {cfg.smtp_host}:{cfg.smtp_port}")
        
        server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port)
        server.starttls()
        
        logger.info(f"[_send_email] Authenticating as {cfg.sender_email}")
        
        server.login(cfg.sender_email, cfg.sender_password)
        
        logger.info(f"[_send_email] Sending email to {cfg.recipient_email}")
        
        server.sendmail(cfg.sender_email, cfg.recipient_email, msg.as_string())
        
        server.quit()
        
        logger.info(f"[_send_email] Email sent successfully to {cfg.recipient_email}")
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"SMTP Authentication failed: {str(e)}. Check EMAIL_SENDER and EMAIL_PASSWORD"
        logger.error(f"[_send_email] {error_msg}")
        raise Exception(error_msg) from e
    except smtplib.SMTPException as e:
        error_msg = f"SMTP connection error: {str(e)}. Check EMAIL_SMTP_HOST ({cfg.smtp_host}) and EMAIL_SMTP_PORT ({cfg.smtp_port})"
        logger.error(f"[_send_email] {error_msg}")
        raise Exception(error_msg) from e
    except Exception as e:
        error_msg = f"Email send failed: {str(e)}"
        logger.error(f"[_send_email] {error_msg}")
        raise Exception(error_msg) from e

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
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background-color:#f8fafc;margin:0;padding:20px;color:#1e293b;-webkit-font-smoothing:antialiased;}}
  .container{{max-width:600px;margin:0 auto;background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1),0 2px 4px -1px rgba(0,0,0,0.06);border:1px solid #e2e8f0;}}
  .header{{background:linear-gradient(135deg, #1e293b 0%, #0f172a 100%);color:#ffffff;padding:32px 24px;text-align:center;}}
  .header h1{{margin:0;font-size:24px;font-weight:800;letter-spacing:-0.025em;}}
  .header p{{margin:8px 0 0;opacity:0.8;font-size:14px;font-weight:500;}}
  .stats{{background-color:#f1f5f9;padding:12px 24px;border-bottom:1px solid #e2e8f0;text-align:center;}}
  .stat{{font-size:12px;font-weight:600;color:#64748b;margin:0 12px;text-transform:uppercase;letter-spacing:0.05em;}}
  .stat b{{color:#0f172a;}}
  .content{{padding:20px;}}
  .card{{background-color:#ffffff;margin-bottom:24px;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden;transition:transform 0.2s ease;}}
  .card-header{{padding:16px 20px;background-color:#f8fafc;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;}}
  .rank{{font-size:12px;font-weight:700;color:#94a3b8;}}
  .score{{background-color:#f0fdf4;color:#15803d;font-size:12px;font-weight:700;padding:4px 12px;border-radius:9999px;border:1px solid #dcfce7;}}
  .score.low{{background-color:#fef2f2;color:#b91c1c;border-color:#fee2e2;}}
  .body{{padding:20px;}}
  .title{{font-size:18px;font-weight:700;color:#0f172a;margin:0 0 4px;line-height:1.4;}}
  .company{{font-size:14px;font-weight:600;color:#334155;margin-bottom:12px;}}
  .meta{{font-size:13px;color:#64748b;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:8px;}}
  .meta-item{{background-color:#f1f5f9;padding:2px 8px;border-radius:6px;white-space:nowrap;}}
  .skills{{margin-bottom:16px;}}
  .skill{{background-color:#eff6ff;color:#1d4ed8;font-size:11px;font-weight:600;padding:4px 10px;border-radius:6px;border:1px solid #dbeafe;display:inline-block;margin:0 4px 4px 0;}}
  .desc{{font-size:13px;color:#475569;line-height:1.6;margin-bottom:20px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}}
  .outreach{{background-color:#fffbeb;border:1px solid #fef3c7;border-radius:12px;padding:16px;margin-bottom:20px;}}
  .outreach-header{{display:flex;justify-content:space-between;margin-bottom:8px;}}
  .outreach-label{{font-size:11px;font-weight:700;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;}}
  .outreach-text{{font-size:13px;color:#78350f;white-space:pre-wrap;line-height:1.5;font-family:inherit;}}
  .apply-btn{{display:block;background-color:#0f172a;color:#ffffff !important;text-decoration:none;text-align:center;padding:14px;border-radius:10px;font-size:14px;font-weight:700;margin-top:10px;}}
  .footer{{text-align:center;padding:32px 24px;font-size:12px;color:#94a3b8;line-height:1.5;}}
  .platform-badge{{font-size:10px;font-weight:800;padding:2px 8px;border-radius:6px;text-transform:uppercase;color:#ffffff;display:inline-block;}}
  .platform-linkedin{{background-color:#0077b5;}}
  .platform-wellfound{{background-color:#fa5252;}}
  .platform-indeed{{background-color:#2164f3;}}
  .platform-generic{{background-color:#64748b;}}
  
  @media only screen and (max-width: 480px) {{
    body {{ padding: 10px; }}
    .container {{ border-radius: 0; }}
    .header {{ padding: 24px 16px; }}
    .title {{ font-size: 16px; }}
    .body {{ padding: 16px; }}
    .stat {{ margin: 4px 8px; display: block; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Job Digest</h1>
    <p>{run_label}</p>
  </div>
  <div class="stats">
    <span class="stat">MATCHED: <b>{total}</b></span>
    <span class="stat">DRAFTS: <b>{with_drafts}</b></span>
  </div>
  <div class="content">
    {job_cards}
  </div>
  <div class="footer">
    This digest was generated automatically. Jobs are ranked by match score,
    recency, and source quality.
  </div>
</div>
</body>
</html>"""
    return html

def _job_card(job: MatchedJob) -> str:
    score_class = "low" if job.final_score < 0.7 else ""
    score_pct   = f"{job.final_score:.0%}"

    meta_items = [f"📍 {job.location}"]
    if job.job_type:
        meta_items.append(" · ".join(job.job_type))
    if job.salary:
        meta_items.append(f"💰 {job.salary}")
    meta_html = "".join(f'<span class="meta-item">{m}</span>' for m in meta_items)

    all_skills = job.skills[:8]
    skills_html = "".join(
        f'<span class="skill">{s}</span>' for s in all_skills
    )

    desc_excerpt = (job.description or "")[:1000].rstrip()
    if len(job.description or "") > 1000:
        desc_excerpt += "…"

    outreach_html = ""

    if job.outreach_email_draft:
        recruiter_name = ""
        if job.recruiter:
            recruiter_name = job.recruiter.get("name", "")
        label = f"Email draft{' for ' + recruiter_name if recruiter_name else ''}"
        outreach_html += f"""
    <div class="outreach">
      <div class="outreach-header">
        <div class="outreach-label">✉ {label}</div>
      </div>
      <div class="outreach-text">{job.outreach_email_draft}</div>
    </div>"""

    if job.outreach_linkedin_draft:
        recruiter_name = ""
        if job.recruiter:
            recruiter_name = job.recruiter.get("name", "")
        linkedin_url = job.recruiter.get("linkedin_url") or job.recruiter.get("profile_url", "#") if job.recruiter else "#"
        label = f"LinkedIn draft{' for ' + recruiter_name if recruiter_name else ''}"
        outreach_html += f"""
    <div class="outreach" style="background-color:#f0fdf4;border-color:#dcfce7;">
      <div class="outreach-header">
        <div class="outreach-label" style="color:#166534;">💼 {label}</div>
        <a href="{linkedin_url}" style="font-size:10px;color:#15803d;font-weight:700;text-decoration:none;" target="_blank">PROFILE →</a>
      </div>
      <div class="outreach-text" style="color:#14532d;">{job.outreach_linkedin_draft}</div>
      <div style="font-size:10px;color:#166534;margin-top:8px;opacity:0.7;">{len(job.outreach_linkedin_draft)} / 300 characters</div>
    </div>"""

    platform = (job.source_platform or "generic").lower()
    platform_label = platform.capitalize()
    platform_badge = f'<span class="platform-badge platform-{platform}">{platform_label}</span>'

    recency_html = ""
    if job.posted_at_text:
        text = job.posted_at_text.replace("Posted", "").replace("posted", "").strip()
        recency_html = f'<span class="meta-item" style="color:#c2410c;font-weight:700;">🕒 {text}</span>'

    recruiter_html = ""
    if job.recruiter:
        r = job.recruiter
        name = getattr(r, "name", None) or (r.get("name") if isinstance(r, dict) else None)
        if name:
            recruiter_html = f'<div style="font-size:13px;color:#475569;margin-bottom:12px;">👤 <b>Recruiter:</b> {name}</div>'

    return f"""
  <div class="card">
    <div class="card-header">
      <div class="rank">#{job.rank} · {platform_badge}</div>
      <div class="score {score_class}">{score_pct} MATCH</div>
    </div>
    <div class="body">
      <h2 class="title">{job.title}</h2>
      <div class="company">{job.company}</div>
      <div class="meta">
        {meta_html}
        {recency_html}
      </div>
      {recruiter_html}
      <div class="skills">{skills_html}</div>
      <div class="desc">{desc_excerpt}</div>
      {outreach_html}
      <a class="apply-btn" href="{job.source_url}" target="_blank">VIEW &amp; APPLY ON {platform_label.upper()}</a>
    </div>
  </div>"""

def _default_run_label() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%-d %b %Y · %H:%M UTC")